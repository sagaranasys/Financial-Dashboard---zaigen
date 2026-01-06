"""
Dashboard Financeiro Pessoal
Aplicação Flask principal
"""
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import bcrypt
import os
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename

import config
from database import db, db_conta
from processors import upload_handler

# Inicializar Flask
app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = config.MAX_FILE_SIZE
app.config['PERMANENT_SESSION_LIFETIME'] = config.SESSION_TIMEOUT

# Criar diretórios e inicializar banco
config.create_directories()
db.init_database()

# Remover CSP restritivo para desenvolvimento
@app.after_request
def add_security_headers(response):
    # Remove qualquer CSP existente e permite tudo
    response.headers.pop('Content-Security-Policy', None)
    response.headers.pop('X-Content-Security-Policy', None)
    return response

# ============================================================================
# AUTENTICAÇÃO
# ============================================================================

def verificar_senha(senha):
    """Verifica se a senha está correta"""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT valor FROM configuracoes WHERE chave = ?', ('password_hash',))
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        return False
    
    password_hash = result['valor'].encode('utf-8')
    return bcrypt.checkpw(senha.encode('utf-8'), password_hash)

def login_requerido(f):
    """Decorator para páginas que requerem login"""
    def decorated_function(*args, **kwargs):
        if 'logado' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# ============================================================================
# ROTAS - AUTENTICAÇÃO
# ============================================================================

@app.route('/')
def index():
    """Redireciona para login ou dashboard"""
    if 'logado' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Página de login"""
    if request.method == 'POST':
        senha = request.form.get('senha')
        
        if verificar_senha(senha):
            session['logado'] = True
            session.permanent = True
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Senha incorreta!', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Faz logout"""
    session.pop('logado', None)
    flash('Logout realizado com sucesso!', 'success')
    return redirect(url_for('login'))

# ============================================================================
# ROTAS - DASHBOARD
# ============================================================================

@app.route('/dashboard')
@login_requerido
def dashboard():
    """Dashboard principal"""
    # Pegar meses disponíveis
    meses = db.get_meses_disponiveis()
    
    # Mês selecionado (mais recente por padrão)
    mes_selecionado = request.args.get('mes', meses[0] if meses else None)
    
    # Dados do dashboard
    dados = {}
    
    if mes_selecionado:
        # Total do mês
        dados['total_mes'] = db.get_total_mes(mes_selecionado)

        # Resumo por categoria (apenas despesas positivas para o gráfico)
        resumo_raw = db.get_resumo_mensal(mes_selecionado, apenas_despesas=True)
        dados['resumo_categorias'] = [
            {
                'categoria': r['categoria'],
                'quantidade': r['quantidade'],
                'total': r['total'],
                'media': r['media']
            } for r in resumo_raw
        ]

        # Estornos como categoria agrupada
        total_estornos = db.get_total_estornos_mes(mes_selecionado)
        estornos_raw = db.get_estornos_mes(mes_selecionado)
        if estornos_raw:
            dados['resumo_categorias'].append({
                'categoria': 'Estornos',
                'quantidade': len(estornos_raw),
                'total': -total_estornos,  # Valor negativo para mostrar como crédito
                'media': -total_estornos / len(estornos_raw) if estornos_raw else 0,
                'is_estorno': True  # Flag para estilização especial
            })

        # Mês anterior para comparação
        mes_anterior = calcular_mes_anterior(mes_selecionado)
        dados['total_mes_anterior'] = db.get_total_mes(mes_anterior) if mes_anterior in meses else 0

        # Calcular variação
        if dados['total_mes_anterior'] > 0:
            variacao = ((dados['total_mes'] - dados['total_mes_anterior']) / dados['total_mes_anterior']) * 100
            dados['variacao_pct'] = variacao
        else:
            dados['variacao_pct'] = 0

        # Calcular variação por categoria
        variacoes_cat = db.get_variacao_categorias_mes(mes_selecionado)
        
        # Injetar variação no resumo de categorias
        for cat in dados['resumo_categorias']:
            nome_cat = cat['categoria']
            if nome_cat in variacoes_cat:
                cat['variacao_pct'] = variacoes_cat[nome_cat]['variacao_pct']
                cat['diferenca'] = variacoes_cat[nome_cat]['diferenca']
            else:
                cat['variacao_pct'] = 0
                cat['diferenca'] = 0

        # Meta do mês
        meta_mes = db.get_meta(mes_selecionado)
        meta_padrao = db.get_meta_padrao()
        dados['meta'] = meta_mes or meta_padrao or 0
        if dados['meta'] > 0:
            dados['meta_percentual'] = (dados['total_mes'] / dados['meta']) * 100
            dados['meta_restante'] = dados['meta'] - dados['total_mes']
        else:
            dados['meta_percentual'] = 0
            dados['meta_restante'] = 0

        # Tendências (Sparklines)
        dados['tendencias'] = db.get_tendencia_categorias(mes_selecionado)

        # ANÁLISE DE ANOMALIAS (NOVO)
        # Calcula média histórica e identifica picos de gastos
        for cat in dados['resumo_categorias']:
            categoria_nome = cat['categoria']
            if cat.get('is_estorno'):
                continue

            historico = dados['tendencias'].get(categoria_nome, [])
            
            # O histórico retorna lista cronológica terminando no mês atual (se houver dados)
            # Queremos comparar o mês atual com a média dos meses ANTERIORES
            valores_passados = historico[:-1] if len(historico) > 1 else []
            
            cat['media_historica'] = 0
            cat['is_alerta_media'] = False
            cat['diff_media'] = 0
            
            if valores_passados:
                media_hist = sum(valores_passados) / len(valores_passados)
                cat['media_historica'] = media_hist
                
                # Critério de alerta:
                # 1. Gasto atual > 50% acima da média histórica
                # 2. Valor relevante (> R$ 100) para evitar alertas em valores irrisórios
                if cat['total'] > (media_hist * 1.5) and cat['total'] > 100:
                    cat['is_alerta_media'] = True
                    cat['diff_media'] = cat['total'] - media_hist

    return render_template('dashboard.html',
                         meses=meses,
                         mes_selecionado=mes_selecionado,
                         dados=dados)

# ============================================================================
# ROTAS - CONTA CORRENTE (NOVO)
# ============================================================================

@app.route('/conta')
@login_requerido
def conta():
    """Página de Extrato Bancário"""
    meses = db.get_meses_disponiveis()
    mes_selecionado = request.args.get('mes', meses[0] if meses else None)
    
    dados = {
        'resumo': {'entradas': 0, 'saidas': 0, 'saldo': 0},
        'transacoes': []
    }
    
    if mes_selecionado:
        dados['resumo'] = db_conta.get_resumo_conta(mes_selecionado)
        dados['transacoes'] = db_conta.get_transacoes_conta(mes_selecionado)
    
    return render_template('conta.html',
                         meses=meses,
                         mes_selecionado=mes_selecionado,
                         dados=dados)

# ============================================================================
# ROTAS - UPLOAD
# ============================================================================

@app.route('/upload', methods=['GET', 'POST'])
@login_requerido
def upload():
    """Página de upload de arquivos"""
    if request.method == 'POST':
        # Verificar se arquivo foi enviado
        if 'arquivo' not in request.files:
            flash('Nenhum arquivo selecionado', 'warning')
            return redirect(request.url)
        
        files = request.files.getlist('arquivo')
        
        if not files or files[0].filename == '':
            flash('Nenhum arquivo selecionado', 'warning')
            return redirect(request.url)
        
        # Processar cada arquivo
        sucessos = 0
        erros = []
        
        for file in files:
            if file and file.filename.endswith('.zip'):
                resultado = upload_handler.processar_upload(file)
                
                if resultado['sucesso']:
                    sucessos += 1
                    flash(resultado['mensagem'], 'success')
                else:
                    erros.append(f"{file.filename}: {resultado['mensagem']}")
        
        if erros:
            for erro in erros:
                flash(erro, 'danger')
        
        if sucessos > 0:
            return redirect(url_for('dashboard'))
    
    # GET - mostrar página de upload
    historico = upload_handler.get_historico_uploads()
    return render_template('upload.html', historico=historico)

# ============================================================================
# ROTAS - METAS
# ============================================================================

@app.route('/metas')
@login_requerido
def metas():
    """Página de configuração de metas"""
    meses = db.get_meses_disponiveis()
    meta_padrao = db.get_meta_padrao()

    # Carregar metas existentes para cada mês
    metas_por_mes = {}
    for mes in meses:
        meta_mes = db.get_meta(mes)
        meta_efetiva = meta_mes or meta_padrao or 0
        total = db.get_total_mes(mes)
        metas_por_mes[mes] = {
            'meta': meta_efetiva,
            'total': total,
            'percentual': (total / meta_efetiva * 100) if meta_efetiva > 0 else 0
        }

    return render_template('metas.html',
                          meses=meses,
                          meta_padrao=meta_padrao or 0,
                          metas_por_mes=metas_por_mes)


@app.route('/metas/salvar', methods=['POST'])
@login_requerido
def salvar_meta():
    """Salva meta (padrão ou específica do mês)"""
    data = request.get_json()

    tipo = data.get('tipo')  # 'padrao' ou 'mes'
    valor = float(data.get('valor', 0))

    if tipo == 'padrao':
        db.salvar_meta_padrao(valor)
        return jsonify({'success': True, 'message': 'Meta padrão salva!'})
    elif tipo == 'mes':
        mes = data.get('mes')
        if mes:
            db.salvar_meta(mes, valor)
            return jsonify({'success': True, 'message': f'Meta para {mes} salva!'})

    return jsonify({'success': False, 'message': 'Dados inválidos'}), 400


# ============================================================================
# API - JSON
# ============================================================================

@app.route('/api/transacoes/<mes>')
@login_requerido
def api_transacoes(mes):
    """Retorna transações do mês em JSON"""
    categoria = request.args.get('categoria')

    # Se for categoria de estornos, buscar valores negativos
    if categoria == 'Estornos':
        transacoes = db.get_estornos_mes(mes)
        transacoes_dict = []
        for t in transacoes:
            data_formatada = formatar_data(t['data_compra'])
            transacoes_dict.append({
                'id': None,
                'data': data_formatada,
                'descricao': t['descricao'],
                'valor': t['valor'],
                'categoria': t['categoria'] or 'Estorno',
                'subcategoria': None,
                'parcela': None,
                'alerta': None
            })
        return jsonify(transacoes_dict)

    transacoes = db.get_transacoes(mes_referencia=mes, categoria=categoria)

    # Buscar alertas do mês para enriquecer as transações
    alertas = db.get_alertas_atipicos(mes)
    alertas_por_descricao = {}
    for a in alertas:
        if a['tipo'] in ('valor_alto', 'fornecedor_novo'):
            alertas_por_descricao[a['descricao']] = {
                'tipo': a['tipo'],
                'mensagem': a['mensagem']
            }

    # Buscar variações de recorrentes (>20%)
    variacoes_recorrentes = db.get_variacoes_recorrentes(mes)

    # Converter para dict
    transacoes_dict = []
    for t in transacoes:
        # Formatar data para DD/MM/YYYY
        data_formatada = formatar_data(t['data_compra'])

        # Verificar se há alerta para esta transação
        alerta = alertas_por_descricao.get(t['descricao'])

        # Verificar se há variação de recorrente (com tratamento seguro)
        try:
            descricao_norm = t['descricao_normalizada']
            variacao = variacoes_recorrentes.get(descricao_norm) if descricao_norm else None
        except (KeyError, TypeError):
            variacao = None

        transacoes_dict.append({
            'id': t['id'],
            'data': data_formatada,
            'descricao': t['descricao'],
            'valor': t['valor'],
            'categoria': t['categoria'],
            'subcategoria': t['subcategoria'],
            'parcela': t['parcela'],
            'alerta': alerta,
            'variacao': variacao
        })

    # Aplicar mapeamentos de descrição
    transacoes_dict = db.aplicar_mapeamentos_descricao(transacoes_dict)

    return jsonify(transacoes_dict)


@app.route('/api/variacao-subcategorias/<mes>')
@login_requerido
def api_variacao_subcategorias(mes):
    """Retorna variação de gastos por subcategoria vs mês anterior"""
    categoria = request.args.get('categoria')
    if not categoria:
        return jsonify({}), 400
    # Usar a nova função que compara com mês anterior
    variacoes = db.get_variacao_subcategorias_mes_anterior(mes, categoria)
    return jsonify(variacoes)


@app.route('/api/variacao-categoria/<mes>')
@login_requerido
def api_variacao_categoria(mes):
    """Retorna variação de gastos da categoria vs média histórica"""
    categoria = request.args.get('categoria')
    if not categoria:
        return jsonify({}), 400
    variacao = db.get_variacao_categoria(mes, categoria)
    return jsonify(variacao)


@app.route('/api/mapeamento-descricao', methods=['POST'])
@login_requerido
def api_salvar_mapeamento():
    """Salva um mapeamento de descrição"""
    data = request.get_json()

    descricao_original = data.get('descricao_original')
    descricao_customizada = data.get('descricao_customizada')

    if not descricao_original or not descricao_customizada:
        return jsonify({'success': False, 'error': 'Descrição original e customizada são obrigatórias'}), 400

    resultado = db.salvar_mapeamento_descricao(descricao_original, descricao_customizada)

    if resultado['success']:
        return jsonify(resultado)
    else:
        return jsonify(resultado), 500


@app.route('/api/mapeamento-descricao', methods=['DELETE'])
@login_requerido
def api_deletar_mapeamento():
    """Remove um mapeamento de descrição"""
    data = request.get_json()

    descricao_original = data.get('descricao_original')

    if not descricao_original:
        return jsonify({'success': False, 'error': 'Descrição original é obrigatória'}), 400

    resultado = db.deletar_mapeamento_descricao(descricao_original)
    return jsonify(resultado)


@app.route('/api/mapeamentos')
@login_requerido
def api_listar_mapeamentos():
    """Lista todos os mapeamentos de descrição"""
    mapeamentos = db.get_mapeamentos_descricao()
    return jsonify(mapeamentos)


@app.route('/api/transacoes/<int:transacao_id>/categoria', methods=['POST'])
@login_requerido
def api_atualizar_categoria(transacao_id):
    """Atualiza a categoria de uma transação"""
    data = request.get_json()

    categoria = data.get('categoria')
    subcategoria = data.get('subcategoria')
    salvar_regra = data.get('salvar_regra', False)

    if not categoria:
        return jsonify({'success': False, 'error': 'Categoria é obrigatória'}), 400

    resultado = db.atualizar_categoria_transacao(
        transacao_id=transacao_id,
        categoria=categoria,
        subcategoria=subcategoria,
        salvar_regra=salvar_regra
    )

    if resultado['success']:
        return jsonify(resultado)
    else:
        return jsonify(resultado), 404


@app.route('/api/transacoes/atualizar-por-descricao', methods=['POST'])
@login_requerido
def api_atualizar_categoria_por_descricao():
    """Atualiza a categoria de todas as transações com mesma descrição (via drag and drop)"""
    data = request.get_json()

    descricao = data.get('descricao')
    categoria = data.get('categoria')
    subcategoria = data.get('subcategoria')

    if not descricao or not categoria:
        return jsonify({'success': False, 'error': 'Descrição e categoria são obrigatórios'}), 400

    resultado = db.atualizar_categoria_por_descricao(
        descricao=descricao,
        categoria=categoria,
        subcategoria=subcategoria
    )

    if resultado['success']:
        return jsonify(resultado)
    else:
        return jsonify(resultado), 400


@app.route('/api/categorias')
@login_requerido
def api_categorias():
    """Retorna lista de categorias disponíveis (padrão + personalizadas)"""
    return jsonify(db.get_categorias_personalizadas())


@app.route('/api/categorias/<int:categoria_id>')
@login_requerido
def api_categoria_detalhe(categoria_id):
    """Retorna detalhes de uma categoria específica"""
    categorias = db.get_lista_categorias()
    for cat in categorias:
        if cat['id'] == categoria_id:
            return jsonify(cat)
    return jsonify({'error': 'Categoria não encontrada'}), 404


@app.route('/api/categorias', methods=['POST'])
@login_requerido
def api_categoria_criar():
    """Cria uma nova categoria"""
    data = request.get_json()
    nome = data.get('nome', '').strip()
    subcategorias = data.get('subcategorias', [])

    if not nome:
        return jsonify({'success': False, 'error': 'Nome é obrigatório'}), 400

    resultado = db.add_categoria(nome, subcategorias)
    return jsonify(resultado)


@app.route('/api/categorias/<int:categoria_id>', methods=['PUT'])
@login_requerido
def api_categoria_atualizar(categoria_id):
    """Atualiza uma categoria existente"""
    data = request.get_json()
    resultado = db.update_categoria(
        categoria_id,
        nome=data.get('nome'),
        subcategorias=data.get('subcategorias')
    )
    return jsonify(resultado)


@app.route('/api/categorias/<int:categoria_id>', methods=['DELETE'])
@login_requerido
def api_categoria_excluir(categoria_id):
    """Exclui uma categoria"""
    resultado = db.delete_categoria(categoria_id)
    return jsonify(resultado)


@app.route('/api/categorias/padrao', methods=['POST'])
@login_requerido
def api_categoria_padrao_editar():
    """Edita uma categoria padrão (cria/atualiza como personalizada)"""
    data = request.get_json()
    nome_original = data.get('nome_original', '').strip()
    nome = data.get('nome', '').strip()
    subcategorias = data.get('subcategorias', [])

    if not nome:
        return jsonify({'success': False, 'error': 'Nome é obrigatório'}), 400

    resultado = db.editar_categoria_padrao(nome_original, nome, subcategorias)
    return jsonify(resultado)


@app.route('/configuracoes')
@login_requerido
def configuracoes():
    """Página de configurações"""
    from config import CATEGORIAS

    # Obter categorias personalizadas
    personalizadas = db.get_lista_categorias()
    nomes_personalizados = {cat['nome'] for cat in personalizadas}

    # Construir lista unificada
    todas_categorias = []

    # Adicionar categorias padrão (exceto as que foram sobrescritas)
    for nome, subcats in CATEGORIAS.items():
        if nome not in nomes_personalizados:
            todas_categorias.append({
                'id': None,
                'nome': nome,
                'subcategorias': subcats,
                'personalizada': False
            })

    # Adicionar categorias personalizadas
    todas_categorias.extend(personalizadas)

    # Ordenar alfabeticamente
    todas_categorias.sort(key=lambda x: x['nome'])

    return render_template('configuracoes.html',
        todas_categorias=todas_categorias
    )


def formatar_data(data_str):
    """Formata data para exibição DD/MM/YYYY"""
    if not data_str:
        return '--'

    # Se já está no formato correto
    if isinstance(data_str, str):
        # Tentar parsear diferentes formatos
        formatos = ['%Y-%m-%d', '%d/%m/%Y', '%Y-%m-%d %H:%M:%S']
        for fmt in formatos:
            try:
                data = datetime.strptime(data_str.split(' ')[0], fmt.split(' ')[0])
                return data.strftime('%d/%m/%Y')
            except:
                continue
        return data_str[:10] if len(data_str) >= 10 else data_str

    return '--'

@app.route('/api/resumo/<mes>')
@login_requerido
def api_resumo(mes):
    """Retorna resumo do mês em JSON"""
    resumo = db.get_resumo_mensal(mes)

    resumo_dict = []
    for r in resumo:
        resumo_dict.append({
            'categoria': r['categoria'] or 'Não Classificado',
            'quantidade': r['quantidade'],
            'total': r['total'],
            'media': r['media']
        })

    return jsonify(resumo_dict)


@app.route('/api/historico-mensal')
@login_requerido
def api_historico_mensal():
    """Retorna histórico de gastos por mês (últimos 6 meses)"""
    meses = db.get_meses_disponiveis()[:6]  # Últimos 6 meses

    historico = []
    for mes in reversed(meses):  # Ordem cronológica
        total = db.get_total_mes(mes)
        historico.append({
            'mes': mes,
            'mes_label': formatar_mes_label(mes),
            'total': total
        })

    return jsonify(historico)


@app.route('/api/historico-recorrencia')
@login_requerido
def api_historico_recorrencia():
    """Retorna histórico de recorrentes vs variáveis"""
    historico = db.get_historico_recorrencia()
    
    # Formatar labels
    for h in historico:
        h['mes_label'] = formatar_mes_label(h['mes'])
        
    return jsonify(historico)


@app.route('/api/evolucao-diaria/<mes>')
@login_requerido
def api_evolucao_diaria(mes):
    """Retorna evolução diária acumulada (atual vs anterior)"""
    # Dados do mês atual
    atual = db.get_evolucao_diaria(mes)
    
    # Dados do mês anterior
    mes_anterior = calcular_mes_anterior(mes)
    anterior = db.get_evolucao_diaria(mes_anterior) if mes_anterior else []
    
    return jsonify({
        'atual': atual,
        'anterior': anterior,
        'mes_atual_label': formatar_mes_label(mes),
        'mes_anterior_label': formatar_mes_label(mes_anterior) if mes_anterior else 'Anterior'
    })


@app.route('/api/recorrentes/<mes>')
@login_requerido
def api_recorrentes(mes):
    """Retorna gastos recorrentes do mês especificado"""
    recorrentes = db.get_recorrentes_do_mes(mes)
    total_despesas = db.get_total_despesas_mes(mes)  # Apenas despesas, sem estornos

    # Buscar valores do mês anterior para comparação
    mes_anterior = calcular_mes_anterior(mes)
    valores_anterior = db.get_valores_recorrentes_mes(mes_anterior) if mes_anterior else {}

    # Calcular total dos recorrentes e montar lista
    total_recorrentes = 0
    recorrentes_dict = []
    parcelas = []
    mensais = []

    for r in recorrentes:
        total_recorrentes += r['valor']

        # Calcular variação vs mês anterior
        desc_norm = r['descricao_normalizada']
        valor_anterior = valores_anterior.get(desc_norm)
        variacao = None
        variacao_pct = None

        if valor_anterior is not None and valor_anterior > 0:
            variacao = r['valor'] - valor_anterior
            variacao_pct = (variacao / valor_anterior) * 100

        item = {
            'descricao': r['descricao_normalizada'],
            'descricao_original': r['descricao'],
            'categoria': r['categoria'] or 'Não Classificado',
            'valor': r['valor'],
            'frequencia': r['frequencia'],
            'data': r['data_compra'],
            'parcela': r.get('parcela'),
            'valor_anterior': valor_anterior,
            'variacao': variacao,
            'variacao_pct': variacao_pct
        }

        recorrentes_dict.append(item)

        # Verificar se é parcela (tem formato X/Y)
        is_parcela = False
        if item['parcela'] and '/' in str(item['parcela']):
             is_parcela = True

        if is_parcela:
            parcelas.append(item)
        else:
            mensais.append(item)

    # Calcular percentual do total (usando apenas despesas, sem estornos)
    percentual = (total_recorrentes / total_despesas * 100) if total_despesas > 0 else 0

    return jsonify({
        'recorrentes': recorrentes_dict,
        'parcelas': parcelas,
        'mensais': mensais,
        'total_recorrentes': total_recorrentes,
        'total_despesas': total_despesas,
        'percentual': percentual,
        'quantidade': len(recorrentes_dict)
    })


@app.route('/api/recorrentes/toggle', methods=['POST'])
@login_requerido
def api_toggle_recorrente():
    """Ativa ou desativa um gasto recorrente"""
    data = request.get_json()
    descricao = data.get('descricao')
    ativo = data.get('ativo', True)

    db.toggle_recorrente(descricao, ativo)

    return jsonify({'success': True})


# ============================================================================
# REGRAS DE CATEGORIZAÇÃO
# ============================================================================

@app.route('/api/regras-categorizacao')
@login_requerido
def api_listar_regras():
    """Lista todas as regras de categorização"""
    regras = db.get_regras_categorizacao()
    return jsonify(regras)


@app.route('/api/regras-categorizacao', methods=['POST'])
@login_requerido
def api_adicionar_regra():
    """Adiciona uma nova regra de categorização"""
    data = request.get_json()
    padrao = data.get('padrao', '').strip()
    categoria = data.get('categoria', '').strip()
    subcategoria = data.get('subcategoria', '').strip() or None

    if not padrao or not categoria:
        return jsonify({'success': False, 'error': 'Padrão e categoria são obrigatórios'}), 400

    resultado = db.adicionar_regra_categorizacao(padrao, categoria, subcategoria)
    return jsonify(resultado)


@app.route('/api/regras-categorizacao/<int:regra_id>', methods=['PUT'])
@login_requerido
def api_atualizar_regra(regra_id):
    """Atualiza uma regra de categorização existente"""
    data = request.get_json()
    padrao = data.get('padrao')
    categoria = data.get('categoria')
    subcategoria = data.get('subcategoria')

    resultado = db.atualizar_regra_categorizacao(regra_id, padrao, categoria, subcategoria)
    return jsonify(resultado)


@app.route('/api/regras-categorizacao/<int:regra_id>', methods=['DELETE'])
@login_requerido
def api_excluir_regra(regra_id):
    """Exclui uma regra de categorização"""
    resultado = db.excluir_regra_categorizacao(regra_id)
    return jsonify(resultado)


@app.route('/api/recorrentes/ignorar', methods=['POST'])
@login_requerido
def api_ignorar_recorrente():
    """Ignora um gasto recorrente (não aparece mais na lista)"""
    data = request.get_json()
    descricao = data.get('descricao', '').strip()

    if not descricao:
        return jsonify({'success': False, 'error': 'Descrição é obrigatória'}), 400

    resultado = db.ignorar_recorrente(descricao)
    return jsonify(resultado)


@app.route('/api/recorrentes/restaurar', methods=['POST'])
@login_requerido
def api_restaurar_recorrente():
    """Restaura um gasto recorrente que foi ignorado"""
    data = request.get_json()
    descricao = data.get('descricao', '').strip()

    if not descricao:
        return jsonify({'success': False, 'error': 'Descrição é obrigatória'}), 400

    resultado = db.restaurar_recorrente(descricao)
    return jsonify(resultado)


@app.route('/api/recorrentes/adicionar', methods=['POST'])
@login_requerido
def api_adicionar_recorrente():
    """Adiciona um gasto recorrente manualmente"""
    data = request.get_json()
    descricao = data.get('descricao', '').strip()
    categoria = data.get('categoria', '').strip() or None
    valor = data.get('valor')
    tipo = data.get('tipo', 'mensal')

    if not descricao:
        return jsonify({'success': False, 'error': 'Descrição é obrigatória'}), 400

    resultado = db.adicionar_recorrente_manual(descricao, categoria, valor, tipo)
    return jsonify(resultado)


@app.route('/api/recorrentes/manual/<int:id>', methods=['DELETE'])
@login_requerido
def api_excluir_recorrente_manual(id):
    """Exclui um recorrente adicionado manualmente"""
    resultado = db.excluir_recorrente_manual(id)
    return jsonify(resultado)


@app.route('/api/recorrentes/manuais')
@login_requerido
def api_recorrentes_manuais_lista():
    """Retorna lista de recorrentes manuais ativos"""
    manuais = db.get_recorrentes_manuais()
    return jsonify(manuais)


@app.route('/api/recorrentes/ignorados')
@login_requerido
def api_recorrentes_ignorados():
    """Retorna lista de recorrentes ignorados"""
    ignorados = db.get_recorrentes_ignorados()
    return jsonify({'ignorados': list(ignorados)})


@app.route('/api/parcelamentos/adicionar', methods=['POST'])
@login_requerido
def api_adicionar_parcelamento():
    """Adiciona um parcelamento manual"""
    data = request.get_json()
    descricao = data.get('descricao', '').strip()
    categoria = data.get('categoria', '').strip() or None
    valor_total = float(data.get('valor_total', 0))
    qtd_parcelas = int(data.get('qtd_parcelas', 1))
    data_inicio = data.get('data_inicio') # YYYY-MM-DD

    if not descricao or not data_inicio or valor_total <= 0 or qtd_parcelas <= 0:
        return jsonify({'success': False, 'error': 'Dados inválidos'}), 400

    resultado = db.adicionar_parcelamento_manual(
        descricao, categoria, valor_total, qtd_parcelas, data_inicio
    )
    return jsonify(resultado)


@app.route('/api/parcelamentos/<int:id>', methods=['DELETE'])
@login_requerido
def api_excluir_parcelamento(id):
    """Exclui um parcelamento manual"""
    resultado = db.excluir_parcelamento_manual(id)
    return jsonify(resultado)


@app.route('/api/parcelamentos')
@login_requerido
def api_parcelamentos():
    """Retorna lista de parcelamentos manuais"""
    parcelamentos = db.get_parcelamentos_manuais()
    return jsonify(parcelamentos)


@app.route('/api/descricoes')
@login_requerido
def api_descricoes():
    """Retorna lista de descrições únicas para autocomplete"""
    descricoes = db.get_descricoes_unicas()
    return jsonify(descricoes)


def formatar_mes_label(mes_str):
    """Formata YYYY-MM para Mmm/YY (ex: Nov/24)"""
    try:
        data = datetime.strptime(mes_str, '%Y-%m')
        meses_pt = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
                    'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
        return f"{meses_pt[data.month - 1]}/{str(data.year)[2:]}"
    except:
        return mes_str

# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

def calcular_mes_anterior(mes_str):
    """
    Calcula o mês anterior a partir de string YYYY-MM
    """
    try:
        data = datetime.strptime(mes_str, '%Y-%m')
        mes_anterior = data - timedelta(days=1)
        return mes_anterior.strftime('%Y-%m')
    except:
        return None

# ============================================================================
# FILTROS JINJA
# ============================================================================

@app.template_filter('moeda')
def filtro_moeda(valor):
    """Formata valor como moeda brasileira"""
    if valor is None:
        return 'R$ 0,00'
    return f'R$ {valor:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')

@app.template_filter('abs')
def filtro_abs(valor):
    """Retorna valor absoluto"""
    if valor is None:
        return 0
    return abs(valor)

@app.template_filter('data')
@app.template_filter('format_data')
def filtro_data(data_str):
    """Formata data"""
    try:
        # Se já for objeto datetime
        if isinstance(data_str, datetime):
            return data_str.strftime('%d/%m/%Y')
        # Se for string
        data = datetime.strptime(str(data_str).split()[0], '%Y-%m-%d')
        return data.strftime('%d/%m/%Y')
    except:
        return str(data_str)

@app.template_filter('format_mes')
def filtro_format_mes(mes_str):
    """Formata YYYY-MM para Mês/Ano (ex: Jan/24)"""
    return formatar_mes_label(mes_str)

# ============================================================================
# EXECUTAR
# ============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("Dashboard Financeiro Pessoal")
    print("=" * 60)
    print(f"Acesse: http://localhost:5000")
    print(f"Senha padrão: admin123")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
