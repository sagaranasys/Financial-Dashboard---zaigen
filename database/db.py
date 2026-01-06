"""
Gerenciamento do banco de dados SQLite
"""
import sqlite3
import os
from datetime import datetime, timedelta
import config

def get_connection():
    """Retorna conexão com o banco de dados"""
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Permite acessar colunas por nome
    return conn

def init_database():
    """Inicializa o banco de dados com todas as tabelas"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Tabela de transações
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_compra DATE NOT NULL,
            data_processamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            descricao TEXT NOT NULL,
            descricao_normalizada TEXT,
            valor REAL NOT NULL,
            categoria TEXT,
            subcategoria TEXT,
            parcela TEXT,
            cartao TEXT,
            tipo TEXT DEFAULT 'cartao',
            recorrente INTEGER DEFAULT 0,
            quase_recorrente INTEGER DEFAULT 0,
            mes_referencia TEXT,
            fonte_arquivo TEXT
        )
    ''')
    
    # Índices para performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_data ON transacoes(data_compra)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_mes ON transacoes(mes_referencia)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_categoria ON transacoes(categoria)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_descricao ON transacoes(descricao_normalizada)')
    
    # Tabela de regras de categorização
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS regras_categorizacao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            padrao TEXT UNIQUE NOT NULL,
            categoria TEXT NOT NULL,
            subcategoria TEXT,
            confianca REAL DEFAULT 1.0,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            uso_count INTEGER DEFAULT 1
        )
    ''')
    
    # Tabela de metas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS metas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mes_referencia TEXT NOT NULL,
            meta_total REAL NOT NULL,
            meta_por_categoria TEXT,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabela de recorrentes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recorrentes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descricao_normalizada TEXT UNIQUE NOT NULL,
            categoria TEXT,
            subcategoria TEXT,
            valor_medio REAL,
            ultimo_valor REAL,
            variacao_pct REAL,
            primeira_ocorrencia DATE,
            ultima_ocorrencia DATE,
            frequencia INTEGER DEFAULT 1,
            ativo INTEGER DEFAULT 1
        )
    ''')
    
    # Tabela de uploads
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_arquivo TEXT NOT NULL,
            tipo TEXT NOT NULL,
            mes_referencia TEXT,
            num_transacoes INTEGER,
            data_upload TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            hash TEXT UNIQUE
        )
    ''')
    
    # Tabela de alertas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alertas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,
            mensagem TEXT NOT NULL,
            severidade TEXT DEFAULT 'info',
            dados TEXT,
            lido INTEGER DEFAULT 0,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabela de configurações (para senha)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS configuracoes (
            chave TEXT PRIMARY KEY,
            valor TEXT NOT NULL,
            atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Tabela de categorias personalizadas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            subcategorias TEXT,
            icone TEXT,
            cor TEXT,
            ordem INTEGER DEFAULT 0,
            ativo INTEGER DEFAULT 1,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Tabela de recorrentes manuais (adicionados/ignorados pelo usuário)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recorrentes_manuais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descricao TEXT NOT NULL,
            descricao_normalizada TEXT,
            categoria TEXT,
            valor_estimado REAL,
            tipo TEXT DEFAULT 'mensal',
            ignorado INTEGER DEFAULT 0,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(descricao_normalizada, ignorado)
        )
    ''')

    # Tabela de parcelamentos manuais
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS parcelamentos_manuais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descricao TEXT NOT NULL,
            categoria TEXT,
            valor_total REAL NOT NULL,
            qtd_parcelas INTEGER NOT NULL,
            data_inicio DATE NOT NULL,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Tabela de mapeamento de descrições (descrição original → descrição customizada)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mapeamento_descricoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descricao_original TEXT UNIQUE NOT NULL,
            descricao_customizada TEXT NOT NULL,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Índice para busca rápida
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_mapeamento_original ON mapeamento_descricoes(descricao_original)')

    # Inserir senha padrão se não existir
    cursor.execute('''
        INSERT OR IGNORE INTO configuracoes (chave, valor)
        VALUES ('password_hash', ?)
    ''', (config.DEFAULT_PASSWORD_HASH.decode('utf-8'),))

    conn.commit()
    conn.close()

    print("✓ Banco de dados inicializado com sucesso!")

def insert_transacao(data_compra, descricao, valor, categoria=None, subcategoria=None,
                     parcela='Única', cartao=None, mes_referencia=None, fonte_arquivo=None, tipo='cartao'):
    """Insere uma transação no banco com verificação de duplicidade"""
    from processors.categorizer import normalizar_descricao
    
    conn = get_connection()
    cursor = conn.cursor()
    
    desc_norm = normalizar_descricao(descricao)
    
    # 1. Verificar Duplicidade Exata
    cursor.execute('''
        SELECT id FROM transacoes 
        WHERE data_compra = ? 
          AND descricao_normalizada = ? 
          AND ABS(valor - ?) < 0.01
          AND (parcela = ? OR parcela IS NULL)
          AND mes_referencia = ?
    ''', (data_compra, desc_norm, valor, parcela, mes_referencia))
    
    existente = cursor.fetchone()
    if existente:
        conn.close()
        return existente['id'] # Já existe, retorna ID sem duplicar

    # 2. Inserir nova
    cursor.execute('''
        INSERT INTO transacoes 
        (data_compra, descricao, descricao_normalizada, valor, categoria, 
         subcategoria, parcela, cartao, mes_referencia, fonte_arquivo, tipo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (data_compra, descricao, desc_norm, valor, categoria, subcategoria,
          parcela, cartao, mes_referencia, fonte_arquivo, tipo))

    conn.commit()
    transacao_id = cursor.lastrowid
    conn.close()

    return transacao_id


def atualizar_categoria_transacao(transacao_id, categoria, subcategoria=None, salvar_regra=False):
    """
    Atualiza a categoria de uma transação E de todas as transações similares.
    Também salva automaticamente a regra para futuras importações.

    Args:
        transacao_id: ID da transação
        categoria: Nova categoria
        subcategoria: Nova subcategoria (opcional)
        salvar_regra: Ignorado - sempre salva regra automaticamente

    Returns:
        dict com sucesso, descrição normalizada e quantidade de transações atualizadas
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Buscar descrição normalizada
    cursor.execute('SELECT descricao_normalizada FROM transacoes WHERE id = ?', (transacao_id,))
    result = cursor.fetchone()

    if not result:
        conn.close()
        return {'success': False, 'error': 'Transação não encontrada'}

    descricao_normalizada = result['descricao_normalizada']

    # Atualizar TODAS as transações com a mesma descrição normalizada
    cursor.execute('''
        UPDATE transacoes
        SET categoria = ?, subcategoria = ?
        WHERE descricao_normalizada = ?
    ''', (categoria, subcategoria, descricao_normalizada))

    transacoes_atualizadas = cursor.rowcount

    conn.commit()
    conn.close()

    # Sempre salvar a regra para futuras importações
    if descricao_normalizada:
        from processors.categorizer import salvar_regra_categorizacao
        salvar_regra_categorizacao(descricao_normalizada, categoria, subcategoria)

    return {
        'success': True,
        'descricao_normalizada': descricao_normalizada,
        'transacoes_atualizadas': transacoes_atualizadas
    }


def atualizar_categoria_por_descricao(descricao, categoria, subcategoria=None):
    """
    Atualiza a categoria de todas as transações com a mesma descrição (normalizada).
    Usado pelo drag and drop de categorização.

    Args:
        descricao: Descrição original da transação
        categoria: Nova categoria
        subcategoria: Nova subcategoria (opcional)

    Returns:
        dict com sucesso e quantidade de transações atualizadas
    """
    from processors.categorizer import normalizar_descricao, salvar_regra_categorizacao

    # Normalizar a descrição para matching
    descricao_normalizada = normalizar_descricao(descricao)

    conn = get_connection()
    cursor = conn.cursor()

    # Atualizar todas as transações com a mesma descrição normalizada
    cursor.execute('''
        UPDATE transacoes
        SET categoria = ?, subcategoria = ?
        WHERE descricao_normalizada = ?
    ''', (categoria, subcategoria, descricao_normalizada))

    transacoes_atualizadas = cursor.rowcount

    conn.commit()
    conn.close()

    # Salvar regra para futuras importações
    if descricao_normalizada and transacoes_atualizadas > 0:
        salvar_regra_categorizacao(descricao_normalizada, categoria, subcategoria)

    return {
        'success': True,
        'descricao_normalizada': descricao_normalizada,
        'transacoes_atualizadas': transacoes_atualizadas
    }


def get_transacoes_conta(mes_referencia):
    """Retorna transações da conta corrente (Extrato)"""
    return get_transacoes(mes_referencia, tipo='conta') # Helper simplificado

def get_transacoes(mes_referencia=None, categoria=None, limit=None, incluir_estornos=False, tipo='cartao'):
    """
    Retorna transações com filtros opcionais.
    Default: Apenas transações de CARTÃO.
    """
    conn = get_connection()
    cursor = conn.cursor()

    query = 'SELECT * FROM transacoes WHERE 1=1'
    params = []

    if tipo == 'cartao':
        # Retrocompatibilidade: Aceita 'cartao' ou NULL
        query += ' AND (tipo = ? OR tipo IS NULL)'
        params.append(tipo)
    elif tipo:
        # Para outros tipos (conta, etc), busca exata
        # Nota: O parser salva como 'conta_credito' ou 'conta_debito', então se buscarmos 'conta'
        # precisamos usar LIKE ou listar ambos.
        if tipo == 'conta':
            query += " AND (tipo = 'conta_credito' OR tipo = 'conta_debito')"
        else:
            query += ' AND tipo = ?'
            params.append(tipo)

    if mes_referencia:
        query += ' AND mes_referencia = ?'
        params.append(mes_referencia)

    if categoria is not None:
        if categoria == '':
            # Categoria vazia = "Não Classificado"
            query += ' AND (categoria IS NULL OR categoria = "")'
        else:
            query += ' AND categoria = ?'
            params.append(categoria)

    # Excluir estornos (valores negativos) apenas se for CARTÃO
    # Se for Conta, valores negativos são Despesas (Saída), então não excluímos
    if not incluir_estornos and tipo == 'cartao':
        query += ' AND valor > 0'
    
    query += ' ORDER BY data_compra DESC'

    if limit:
        query += ' LIMIT ?'
        params.append(limit)

    cursor.execute(query, params)
    transacoes = cursor.fetchall()
    conn.close()

    return transacoes

def get_resumo_mensal(mes_referencia, apenas_despesas=True):
    """
    Retorna resumo de gastos do mês (Apenas Cartão).

    Por padrão, retorna apenas despesas (valores positivos).
    """
    conn = get_connection()
    cursor = conn.cursor()

    query = '''
        SELECT
            categoria,
            COUNT(*) as quantidade,
            SUM(valor) as total,
            AVG(valor) as media
        FROM transacoes
        WHERE mes_referencia = ? 
          AND (tipo = 'cartao' OR tipo IS NULL)
    '''

    # Por padrão, excluir estornos das categorias normais
    if apenas_despesas:
        query += ' AND valor > 0'

    query += ' GROUP BY categoria ORDER BY total DESC'

    cursor.execute(query, (mes_referencia,))

    resumo = cursor.fetchall()
    conn.close()

    return resumo


def get_estornos_mes(mes_referencia):
    """
    Retorna estornos (valores negativos) do mês, agrupados por categoria
    Apenas para transações de CARTÃO.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT
            categoria,
            descricao,
            valor,
            data_compra
        FROM transacoes
        WHERE mes_referencia = ? AND valor < 0 AND (tipo = 'cartao' OR tipo IS NULL)
        ORDER BY valor ASC
    ''', (mes_referencia,))

    estornos = cursor.fetchall()
    conn.close()

    return estornos


def get_total_estornos_mes(mes_referencia):
    """Retorna total de estornos (valores negativos) do mês (apenas Cartão)"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT COALESCE(SUM(valor), 0) as total
        FROM transacoes
        WHERE mes_referencia = ? AND valor < 0 AND (tipo = 'cartao' OR tipo IS NULL)
    ''', (mes_referencia,))

    result = cursor.fetchone()
    conn.close()

    return abs(result['total']) if result['total'] else 0

def get_total_mes(mes_referencia):
    """Retorna total gasto no mês (Apenas Cartão)"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT SUM(valor) as total
        FROM transacoes
        WHERE mes_referencia = ? AND (tipo = 'cartao' OR tipo IS NULL)
    ''', (mes_referencia,))

    result = cursor.fetchone()
    conn.close()

    return result['total'] if result['total'] else 0


def get_total_despesas_mes(mes_referencia):
    """Retorna total de despesas do mês (apenas valores positivos, sem estornos, Apenas Cartão)"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT SUM(valor) as total
        FROM transacoes
        WHERE mes_referencia = ? AND valor > 0 AND (tipo = 'cartao' OR tipo IS NULL)
    ''', (mes_referencia,))

    result = cursor.fetchone()
    conn.close()

    return result['total'] if result['total'] else 0

def get_meses_disponiveis():
    """Retorna lista de meses com dados"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT DISTINCT mes_referencia
        FROM transacoes
        WHERE mes_referencia IS NOT NULL
        ORDER BY mes_referencia DESC
    ''')
    
    meses = [row['mes_referencia'] for row in cursor.fetchall()]
    conn.close()
    
    return meses

def criar_alerta(tipo, mensagem, severidade='info', dados=None):
    """Cria um alerta no sistema"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO alertas (tipo, mensagem, severidade, dados)
        VALUES (?, ?, ?, ?)
    ''', (tipo, mensagem, severidade, dados))
    
    conn.commit()
    conn.close()

def get_alertas_nao_lidos():
    """Retorna alertas não lidos"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM alertas
        WHERE lido = 0
        ORDER BY criado_em DESC
        LIMIT 10
    ''')

    alertas = cursor.fetchall()
    conn.close()

    return alertas


def marcar_alerta_lido(alerta_id):
    """Marca um alerta como lido"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('UPDATE alertas SET lido = 1 WHERE id = ?', (alerta_id,))
    conn.commit()
    conn.close()

    return {'success': True}


def marcar_todos_alertas_lidos():
    """Marca todos os alertas como lidos"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('UPDATE alertas SET lido = 1 WHERE lido = 0')
    conn.commit()
    conn.close()

    return {'success': True}


def contar_alertas_nao_lidos():
    """Conta quantos alertas não lidos existem"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) as count FROM alertas WHERE lido = 0')
    result = cursor.fetchone()
    conn.close()

    return result['count'] if result else 0


# ============================================================================
# METAS
# ============================================================================

def salvar_meta(mes_referencia, meta_total):
    """Salva ou atualiza a meta para um mês"""
    conn = get_connection()
    cursor = conn.cursor()

    # Verificar se já existe meta para o mês
    cursor.execute('SELECT id FROM metas WHERE mes_referencia = ?', (mes_referencia,))
    existing = cursor.fetchone()

    if existing:
        cursor.execute('''
            UPDATE metas SET meta_total = ?, criado_em = CURRENT_TIMESTAMP
            WHERE mes_referencia = ?
        ''', (meta_total, mes_referencia))
    else:
        cursor.execute('''
            INSERT INTO metas (mes_referencia, meta_total)
            VALUES (?, ?)
        ''', (mes_referencia, meta_total))

    conn.commit()
    conn.close()


def get_meta(mes_referencia):
    """Retorna a meta para um mês específico"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT meta_total FROM metas WHERE mes_referencia = ?
    ''', (mes_referencia,))

    result = cursor.fetchone()
    conn.close()

    return result['meta_total'] if result else None


def get_meta_padrao():
    """Retorna a meta padrão (configuração global)"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT valor FROM configuracoes WHERE chave = 'meta_padrao'
    ''')

    result = cursor.fetchone()
    conn.close()

    return float(result['valor']) if result else None


def salvar_meta_padrao(valor):
    """Salva a meta padrão global"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT OR REPLACE INTO configuracoes (chave, valor, atualizado_em)
        VALUES ('meta_padrao', ?, CURRENT_TIMESTAMP)
    ''', (str(valor),))

    conn.commit()
    conn.close()


# ============================================================================
# GASTOS RECORRENTES
# ============================================================================

def detectar_recorrentes(min_ocorrencias=2):
    """
    Detecta gastos recorrentes analisando transações de CARTÃO que aparecem em múltiplos meses.
    Considera recorrente se aparece em pelo menos min_ocorrencias meses diferentes.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Buscar descrições que aparecem em múltiplos meses (Apenas Cartão)
    cursor.execute('''
        SELECT
            descricao_normalizada,
            categoria,
            COUNT(DISTINCT mes_referencia) as meses_count,
            COUNT(*) as total_ocorrencias,
            AVG(valor) as valor_medio,
            MAX(valor) as ultimo_valor,
            MIN(data_compra) as primeira_ocorrencia,
            MAX(data_compra) as ultima_ocorrencia
        FROM transacoes
        WHERE descricao_normalizada IS NOT NULL
          AND descricao_normalizada != ''
          AND valor > 0
          AND tipo = 'cartao'
        GROUP BY descricao_normalizada
        HAVING COUNT(DISTINCT mes_referencia) >= ?
        ORDER BY meses_count DESC, valor_medio DESC
    ''', (min_ocorrencias,))

    recorrentes = cursor.fetchall()

    # Atualizar tabela de recorrentes
    for r in recorrentes:
        # Calcular variação percentual
        variacao = 0
        if r['valor_medio'] > 0:
            variacao = ((r['ultimo_valor'] - r['valor_medio']) / r['valor_medio']) * 100

        cursor.execute('''
            INSERT OR REPLACE INTO recorrentes
            (descricao_normalizada, categoria, valor_medio, ultimo_valor, variacao_pct,
             primeira_ocorrencia, ultima_ocorrencia, frequencia, ativo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        ''', (r['descricao_normalizada'], r['categoria'], r['valor_medio'],
              r['ultimo_valor'], variacao, r['primeira_ocorrencia'],
              r['ultima_ocorrencia'], r['meses_count']))

    conn.commit()
    conn.close()

    return len(recorrentes)


def get_recorrentes_do_mes(mes_referencia):
    """
    Retorna gastos recorrentes que aparecem no mês especificado.
    Inclui:
    1. Recorrentes detectados automaticamente (presentes nas transações)
    2. Recorrentes manuais (presentes nas transações)
    3. Recorrentes manuais virtuais (NÃO presentes nas transações)
    4. Parcelamentos manuais (calculados para o mês)
    """
    from datetime import datetime
    
    conn = get_connection()
    cursor = conn.cursor()

    # Buscar lista de ignorados
    ignorados = get_recorrentes_ignorados()

    # Passo 1: Buscar descrições que aparecem em 2+ meses (Auto-detecção)
    cursor.execute('''
        SELECT descricao_normalizada, COUNT(DISTINCT mes_referencia) as freq
        FROM transacoes
        WHERE descricao_normalizada IS NOT NULL AND descricao_normalizada != ''
        GROUP BY descricao_normalizada
        HAVING COUNT(DISTINCT mes_referencia) >= 2
    ''')

    frequencias = {row['descricao_normalizada']: row['freq'] for row in cursor.fetchall()}

    # Passo 2: Buscar transações do mês
    cursor.execute('''
        SELECT descricao_normalizada, descricao, categoria, valor, data_compra, parcela
        FROM transacoes
        WHERE mes_referencia = ?
          AND descricao_normalizada IS NOT NULL
          AND valor > 0
        ORDER BY valor DESC
    ''', (mes_referencia,))

    transacoes = cursor.fetchall()

    # Passo 3: Buscar recorrentes manuais completos
    cursor.execute('''
        SELECT * FROM recorrentes_manuais WHERE ignorado = 0
    ''')
    manuais_rows = cursor.fetchall()
    manuais_dict = {row['descricao_normalizada']: dict(row) for row in manuais_rows}
    manuais_set = set(manuais_dict.keys())

    # Passo 4: Buscar parcelamentos manuais
    cursor.execute('SELECT * FROM parcelamentos_manuais')
    parcelamentos_manuais = [dict(row) for row in cursor.fetchall()]

    conn.close()

    recorrentes = []
    descricoes_adicionadas = set()

    # A. Processar Transações Reais
    for t in transacoes:
        desc_norm = t['descricao_normalizada']

        # Pular se foi ignorado pelo usuário
        if desc_norm in ignorados:
            continue

        # Incluir se é detectado automaticamente OU se foi adicionado manualmente
        is_recorrente = desc_norm in frequencias
        is_manual = desc_norm in manuais_set

        if (is_recorrente or is_manual) and desc_norm not in descricoes_adicionadas:
            recorrentes.append({
                'descricao_normalizada': desc_norm,
                'descricao': t['descricao'],
                'categoria': t['categoria'],
                'valor': t['valor'],
                'data_compra': t['data_compra'],
                'parcela': t['parcela'],
                'frequencia': frequencias.get(desc_norm, 1),
                'manual': is_manual and not is_recorrente,
                'virtual': False
            })
            descricoes_adicionadas.add(desc_norm)

    # B. Processar Recorrentes Manuais Virtuais (que não apareceram nas transações)
    # Data base para virtuais: dia 1 do mês de referência
    try:
        data_ref = datetime.strptime(mes_referencia + '-01', '%Y-%m-%d').date()
    except:
        # Fallback se mes_referencia for inválido
        return recorrentes

    for desc_norm, dados in manuais_dict.items():
        if desc_norm not in descricoes_adicionadas and desc_norm not in ignorados:
            # Adicionar como virtual
            recorrentes.append({
                'descricao_normalizada': desc_norm,
                'descricao': dados['descricao'],
                'categoria': dados['categoria'],
                'valor': dados['valor_estimado'] or 0,
                'data_compra': data_ref.strftime('%Y-%m-%d'),
                'parcela': None,
                'frequencia': 12, # Assumir mensal
                'manual': True,
                'virtual': True
            })
            descricoes_adicionadas.add(desc_norm)

    # C. Processar Parcelamentos Manuais
    for p in parcelamentos_manuais:
        try:
            # Calcular se o parcelamento está ativo neste mês
            data_inicio = datetime.strptime(p['data_inicio'], '%Y-%m-%d').date()
            # Normalizar para dia 1 para facilitar contas de meses
            data_inicio_mes = data_inicio.replace(day=1)
            data_ref_mes = data_ref.replace(day=1)
            
            # Diferença em meses
            diff_meses = (data_ref_mes.year - data_inicio_mes.year) * 12 + (data_ref_mes.month - data_inicio_mes.month)
            
            # Se diff_meses for 0, é a parcela 1. Se for 1, é a parcela 2.
            num_parcela = diff_meses + 1
            
            if 1 <= num_parcela <= p['qtd_parcelas']:
                valor_parcela = p['valor_total'] / p['qtd_parcelas']
                desc_parcela = f"{p['descricao']} {num_parcela}/{p['qtd_parcelas']}"
                
                recorrentes.append({
                    'descricao_normalizada': p['descricao'], # Usar descrição base
                    'descricao': desc_parcela,
                    'categoria': p['categoria'],
                    'valor': valor_parcela,
                    'data_compra': data_ref.strftime('%Y-%m-%d'), # Dia 1 do mês
                    'parcela': f"{num_parcela}/{p['qtd_parcelas']}",
                    'frequencia': p['qtd_parcelas'],
                    'manual': True,
                    'virtual': True,
                    'is_parcelamento_manual': True,
                    'id_parcelamento': p['id']
                })
        except Exception as e:
            print(f"Erro ao processar parcelamento manual {p['id']}: {e}")
            continue

    return recorrentes


def get_total_recorrentes_mes(mes_referencia):
    """Retorna o total de gastos recorrentes no mês especificado"""
    recorrentes = get_recorrentes_do_mes(mes_referencia)
    return sum(r['valor'] for r in recorrentes)


def get_valores_recorrentes_mes(mes_referencia):
    """
    Retorna um dicionário com os valores de cada recorrente no mês especificado.
    Chave: descricao_normalizada, Valor: valor da transação
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT descricao_normalizada, valor
        FROM transacoes
        WHERE mes_referencia = ?
          AND descricao_normalizada IS NOT NULL
          AND valor > 0
    ''', (mes_referencia,))

    valores = {row['descricao_normalizada']: row['valor'] for row in cursor.fetchall()}
    conn.close()

    return valores


def get_recorrentes(apenas_ativos=True):
    """Retorna lista de gastos recorrentes (visão geral)"""
    conn = get_connection()
    cursor = conn.cursor()

    query = '''
        SELECT * FROM recorrentes
        {}
        ORDER BY valor_medio DESC
    '''.format('WHERE ativo = 1' if apenas_ativos else '')

    cursor.execute(query)
    recorrentes = cursor.fetchall()
    conn.close()

    return recorrentes


def get_alertas_atipicos(mes_referencia):
    """
    Detecta gastos atípicos do mês:
    1. Transações com valor > 2x a média da categoria
    2. Fornecedores novos (primeira ocorrência)
    3. Categorias com aumento > 50% vs mês anterior
    """
    from datetime import datetime

    conn = get_connection()
    cursor = conn.cursor()

    alertas = []

    try:
        # 1. Transações com valor muito acima da média da categoria
        cursor.execute('''
            WITH MediaCategoria AS (
                SELECT categoria, AVG(valor) as media
                FROM transacoes
                WHERE valor > 0 AND categoria IS NOT NULL AND categoria != ''
                GROUP BY categoria
            )
            SELECT t.descricao, t.categoria, t.valor, m.media,
                   CASE WHEN m.media > 0 THEN (t.valor / m.media) ELSE 0 END as multiplicador
            FROM transacoes t
            JOIN MediaCategoria m ON t.categoria = m.categoria
            WHERE t.mes_referencia = ?
              AND t.valor > 0
              AND t.valor > m.media * 2
            ORDER BY multiplicador DESC
            LIMIT 10
        ''', (mes_referencia,))

        for row in cursor.fetchall():
            alertas.append({
                'tipo': 'valor_alto',
                'descricao': row['descricao'],
                'categoria': row['categoria'],
                'valor': row['valor'],
                'media': row['media'],
                'multiplicador': row['multiplicador'],
                'mensagem': f"Valor {row['multiplicador']:.1f}x acima da média da categoria"
            })

        # 2. Fornecedores novos (primeira ocorrência neste mês)
        cursor.execute('''
            SELECT t.descricao_normalizada, t.descricao, t.categoria, t.valor
            FROM transacoes t
            WHERE t.mes_referencia = ?
              AND t.valor > 0
              AND t.descricao_normalizada IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM transacoes t2
                  WHERE t2.descricao_normalizada = t.descricao_normalizada
                    AND t2.mes_referencia < ?
              )
            ORDER BY t.valor DESC
            LIMIT 10
        ''', (mes_referencia, mes_referencia))

        for row in cursor.fetchall():
            alertas.append({
                'tipo': 'fornecedor_novo',
                'descricao': row['descricao'],
                'categoria': row['categoria'],
                'valor': row['valor'],
                'mensagem': 'Novo fornecedor detectado'
            })

        # 3. Categorias com aumento > 50% vs mês anterior
        # Calcular mês anterior
        try:
            ano, mes = mes_referencia.split('-')
            ano, mes = int(ano), int(mes)
            if mes == 1:
                mes_ant = f"{ano-1}-12"
            else:
                mes_ant = f"{ano}-{mes-1:02d}"
        except:
            mes_ant = None

        if mes_ant:
            cursor.execute('''
                WITH TotalAtual AS (
                    SELECT categoria, SUM(valor) as total
                    FROM transacoes
                    WHERE mes_referencia = ? AND valor > 0 AND categoria IS NOT NULL AND categoria != ''
                    GROUP BY categoria
                ),
                TotalAnterior AS (
                    SELECT categoria, SUM(valor) as total
                    FROM transacoes
                    WHERE mes_referencia = ? AND valor > 0 AND categoria IS NOT NULL AND categoria != ''
                    GROUP BY categoria
                )
                SELECT a.categoria, a.total as total_atual,
                       COALESCE(ant.total, 0) as total_anterior,
                       CASE WHEN ant.total > 0 THEN ((a.total - ant.total) / ant.total * 100) ELSE 0 END as variacao_pct
                FROM TotalAtual a
                LEFT JOIN TotalAnterior ant ON a.categoria = ant.categoria
                WHERE ant.total > 0 AND ((a.total - ant.total) / ant.total * 100) > 50
                ORDER BY variacao_pct DESC
                LIMIT 5
            ''', (mes_referencia, mes_ant))

            for row in cursor.fetchall():
                alertas.append({
                    'tipo': 'categoria_aumento',
                    'categoria': row['categoria'],
                    'total_atual': row['total_atual'],
                    'total_anterior': row['total_anterior'],
                    'variacao_pct': row['variacao_pct'],
                    'mensagem': f"Aumentou {row['variacao_pct']:.0f}% vs mês anterior"
                })

    except Exception as e:
        print(f"Aviso: Erro ao buscar alertas atípicos: {e}")

    conn.close()

    return alertas


def get_variacoes_recorrentes(mes_referencia, limiar_pct=20):
    """
    Detecta variações significativas em transações recorrentes.
    Retorna um dicionário:
        chave: descricao_normalizada
        valor: {variacao_pct, valor_atual, valor_medio, tipo: 'aumento'|'reducao'}

    Args:
        mes_referencia: Mês atual (YYYY-MM)
        limiar_pct: Percentual mínimo de variação para alertar (default: 20%)
    """
    conn = get_connection()
    cursor = conn.cursor()

    variacoes = {}

    try:
        # Buscar recorrentes ativos com histórico de valor médio
        cursor.execute('''
            SELECT r.descricao_normalizada, r.valor_medio,
                   t.valor as valor_atual, t.descricao
            FROM recorrentes r
            JOIN transacoes t ON t.descricao_normalizada = r.descricao_normalizada
            WHERE r.ativo = 1
              AND r.valor_medio > 0
              AND t.mes_referencia = ?
              AND t.valor > 0
        ''', (mes_referencia,))

        for row in cursor.fetchall():
            valor_atual = row['valor_atual']
            valor_medio = row['valor_medio']

            if valor_medio and valor_medio > 0:
                variacao_pct = ((valor_atual - valor_medio) / valor_medio) * 100

                if abs(variacao_pct) >= limiar_pct:
                    tipo = 'aumento' if variacao_pct > 0 else 'reducao'
                    variacoes[row['descricao_normalizada']] = {
                        'descricao': row['descricao'],
                        'variacao_pct': variacao_pct,
                        'valor_atual': valor_atual,
                        'valor_medio': valor_medio,
                        'tipo': tipo,
                        'mensagem': f"{'Aumentou' if tipo == 'aumento' else 'Reduziu'} {abs(variacao_pct):.0f}% vs média de R$ {valor_medio:.2f}"
                    }
    except Exception as e:
        # Se houver erro (ex: tabela não existe), retorna dicionário vazio
        print(f"Aviso: Erro ao buscar variações de recorrentes: {e}")

    conn.close()

    return variacoes


def get_total_recorrentes():
    """Retorna o total mensal estimado de gastos recorrentes"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT COALESCE(SUM(valor_medio), 0) as total
        FROM recorrentes
        WHERE ativo = 1
    ''')

    result = cursor.fetchone()
    conn.close()

    return result['total'] if result else 0


def toggle_recorrente(descricao_normalizada, ativo):
    """Ativa ou desativa um gasto recorrente"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE recorrentes SET ativo = ? WHERE descricao_normalizada = ?
    ''', (1 if ativo else 0, descricao_normalizada))

    conn.commit()
    conn.close()


def get_historico_recorrencia(limit=6):
    """
    Retorna histórico de gastos recorrentes vs variáveis dos últimos meses.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Pegar últimos meses
    # Precisamos importar a função ou reimplementar a query simples
    cursor.execute('SELECT DISTINCT mes_referencia FROM transacoes ORDER BY mes_referencia DESC')
    meses = [row['mes_referencia'] for row in cursor.fetchall()]
    meses = meses[:limit]
    meses.reverse() # Ordem cronológica
    
    historico = []
    
    for mes in meses:
        # Total do mês
        cursor.execute('SELECT SUM(valor) as total FROM transacoes WHERE mes_referencia = ? AND valor > 0', (mes,))
        row_total = cursor.fetchone()
        total = row_total['total'] if row_total and row_total['total'] else 0
        
        # Total recorrente (transações cuja descrição está na tabela de recorrentes ativos)
        cursor.execute('''
            SELECT SUM(t.valor) as total
            FROM transacoes t
            JOIN recorrentes r ON t.descricao_normalizada = r.descricao_normalizada
            WHERE t.mes_referencia = ? 
              AND t.valor > 0
              AND r.ativo = 1
        ''', (mes,))
        
        row_rec = cursor.fetchone()
        recorrente = row_rec['total'] if row_rec and row_rec['total'] else 0
        
        variavel = total - recorrente
        if variavel < 0: variavel = 0 # Safety check
        
        historico.append({
            'mes': mes,
            'total': total,
            'recorrente': recorrente,
            'variavel': variavel
        })
        
    conn.close()
    return historico


# ============================================================================
# RECORRENTES MANUAIS (ADICIONADOS/IGNORADOS PELO USUÁRIO)
# ============================================================================

def get_recorrentes_ignorados():
    """Retorna lista de descrições normalizadas que foram ignoradas pelo usuário"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT descricao_normalizada FROM recorrentes_manuais WHERE ignorado = 1
    ''')

    ignorados = {row['descricao_normalizada'] for row in cursor.fetchall()}
    conn.close()

    return ignorados


def get_recorrentes_manuais():
    """Retorna lista de recorrentes adicionados manualmente pelo usuário"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM recorrentes_manuais WHERE ignorado = 0
        ORDER BY descricao
    ''')

    manuais = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return manuais


def ignorar_recorrente(descricao_normalizada):
    """Marca um gasto recorrente como ignorado"""
    from processors.categorizer import normalizar_descricao

    conn = get_connection()
    cursor = conn.cursor()

    # Normalizar a descrição se não estiver já normalizada
    desc_norm = normalizar_descricao(descricao_normalizada) if ' ' in descricao_normalizada else descricao_normalizada

    try:
        cursor.execute('''
            INSERT INTO recorrentes_manuais (descricao, descricao_normalizada, ignorado)
            VALUES (?, ?, 1)
        ''', (descricao_normalizada, desc_norm))
        conn.commit()
        conn.close()
        return {'success': True}
    except Exception as e:
        conn.close()
        return {'success': False, 'error': str(e)}


def restaurar_recorrente(descricao_normalizada):
    """Remove um gasto da lista de ignorados"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        DELETE FROM recorrentes_manuais
        WHERE descricao_normalizada = ? AND ignorado = 1
    ''', (descricao_normalizada,))

    conn.commit()
    conn.close()
    return {'success': True}


def adicionar_recorrente_manual(descricao, categoria=None, valor_estimado=None, tipo='mensal'):
    """Adiciona um gasto recorrente manualmente"""
    from processors.categorizer import normalizar_descricao

    conn = get_connection()
    cursor = conn.cursor()

    desc_norm = normalizar_descricao(descricao)

    try:
        cursor.execute('''
            INSERT INTO recorrentes_manuais (descricao, descricao_normalizada, categoria, valor_estimado, tipo, ignorado)
            VALUES (?, ?, ?, ?, ?, 0)
        ''', (descricao, desc_norm, categoria, valor_estimado, tipo))
        conn.commit()
        conn.close()
        return {'success': True, 'id': cursor.lastrowid}
    except Exception as e:
        conn.close()
        return {'success': False, 'error': str(e)}


def excluir_recorrente_manual(id):
    """Exclui um recorrente manual"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('DELETE FROM recorrentes_manuais WHERE id = ? AND ignorado = 0', (id,))
    conn.commit()
    conn.close()

    return {'success': True}


def adicionar_parcelamento_manual(descricao, categoria, valor_total, qtd_parcelas, data_inicio):
    """Adiciona um parcelamento manual"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO parcelamentos_manuais 
            (descricao, categoria, valor_total, qtd_parcelas, data_inicio)
            VALUES (?, ?, ?, ?, ?)
        ''', (descricao, categoria, valor_total, qtd_parcelas, data_inicio))
        conn.commit()
        conn.close()
        return {'success': True, 'id': cursor.lastrowid}
    except Exception as e:
        conn.close()
        return {'success': False, 'error': str(e)}


def excluir_parcelamento_manual(id):
    """Exclui um parcelamento manual"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM parcelamentos_manuais WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return {'success': True}


def get_parcelamentos_manuais():
    """Retorna todos os parcelamentos manuais"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM parcelamentos_manuais ORDER BY data_inicio DESC')
    parcelamentos = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return parcelamentos


def get_evolucao_diaria(mes_referencia):
    """
    Retorna a evolução diária acumulada dos gastos no mês.
    Retorna lista de dias (1-31) e valor acumulado.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Buscar gastos diários
    cursor.execute('''
        SELECT strftime('%d', data_compra) as dia, SUM(valor) as total
        FROM transacoes
        WHERE mes_referencia = ? AND valor > 0
        GROUP BY data_compra
        ORDER BY data_compra
    ''', (mes_referencia,))
    
    gastos_diarios = {int(row['dia']): row['total'] for row in cursor.fetchall()}
    conn.close()
    
    # Construir acumulado
    acumulado = []
    total_acumulado = 0
    
    # Determinar último dia do mês (ou hoje se for mês atual)
    # Simplificação: vamos até dia 31 sempre, preenchendo com o último valor
    for dia in range(1, 32):
        if dia in gastos_diarios:
            total_acumulado += gastos_diarios[dia]
        
        acumulado.append({
            'dia': dia,
            'valor': total_acumulado
        })
        
    return acumulado


def get_tendencia_categorias(mes_referencia, num_meses=6):
    """
    Retorna o histórico de gastos por categoria para sparklines (Apenas Cartão).
    Retorna dict: { 'Categoria': [val1, val2, val3, val4, val5, val6] }
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Identificar os meses
    cursor.execute('''
        SELECT DISTINCT mes_referencia 
        FROM transacoes 
        WHERE mes_referencia <= ? 
        ORDER BY mes_referencia DESC 
        LIMIT ?
    ''', (mes_referencia, num_meses))
    
    meses = [row['mes_referencia'] for row in cursor.fetchall()]
    meses.reverse() # Ordem cronológica
    
    if not meses:
        conn.close()
        return {}

    # 2. Buscar totais por categoria nesses meses (Filter Cartão)
    placeholders = ','.join(['?'] * len(meses))
    cursor.execute(f'''
        SELECT categoria, mes_referencia, SUM(valor) as total
        FROM transacoes
        WHERE mes_referencia IN ({placeholders})
          AND valor > 0
          AND tipo = 'cartao'
        GROUP BY categoria, mes_referencia
    ''', meses)
    
    resultados = cursor.fetchall()
    conn.close()
    
    # 3. Organizar dados
    tendencias = {}
    
    # Inicializar categorias encontradas
    categorias_set = set(r['categoria'] for r in resultados if r['categoria'])
    
    for cat in categorias_set:
        valores = []
        for mes in meses:
            # Encontrar valor para este mês e categoria
            val = next((r['total'] for r in resultados 
                       if r['categoria'] == cat and r['mes_referencia'] == mes), 0)
            valores.append(val)
        tendencias[cat] = valores

    return tendencias


def get_variacao_categorias_mes(mes_atual):
    """
    Calcula a variação percentual de cada categoria em relação ao mês anterior.
    Retorna dict: { 'Categoria': { 'valor_anterior': 100, 'variacao_pct': 15.5, 'diferenca': 15.0 } }
    """
    # Calcular mês anterior
    try:
        ano, mes = map(int, mes_atual.split('-'))
        data_atual = datetime(ano, mes, 1)
        data_anterior = data_atual - timedelta(days=1)
        mes_anterior = data_anterior.strftime('%Y-%m')
    except ValueError:
        return {}

    conn = get_connection()
    cursor = conn.cursor()

    # Buscar totais do mês atual e anterior
    cursor.execute('''
        SELECT categoria, mes_referencia, SUM(valor) as total
        FROM transacoes
        WHERE mes_referencia IN (?, ?)
          AND valor > 0
        GROUP BY categoria, mes_referencia
    ''', (mes_atual, mes_anterior))
    
    resultados = cursor.fetchall()
    conn.close()

    # Organizar dados
    dados_mes = {}
    dados_anterior = {}
    
    for r in resultados:
        cat = r['categoria']
        if r['mes_referencia'] == mes_atual:
            dados_mes[cat] = r['total']
        else:
            dados_anterior[cat] = r['total']
            
    variacoes = {}
    
    # Calcular para todas as categorias que têm gastos no mês atual
    for cat, valor_atual in dados_mes.items():
        valor_anterior = dados_anterior.get(cat, 0)
        
        if valor_anterior > 0:
            variacao_pct = ((valor_atual - valor_anterior) / valor_anterior) * 100
            diferenca = valor_atual - valor_anterior
        elif valor_atual > 0:
            variacao_pct = 100.0 # Novo gasto (era 0)
            diferenca = valor_atual
        else:
            variacao_pct = 0.0
            diferenca = 0.0
            
        variacoes[cat] = {
            'valor_anterior': valor_anterior,
            'variacao_pct': variacao_pct,
            'diferenca': diferenca
        }
        
    return variacoes


# ============================================================================
# GERENCIAMENTO DE CATEGORIAS
# ============================================================================

def get_categorias_personalizadas():
    """
    Retorna todas as categorias (padrão + personalizadas).
    Categorias personalizadas sobrescrevem as padrão.
    """
    import json

    # Começar com categorias padrão
    categorias = dict(config.CATEGORIAS)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT nome, subcategorias FROM categorias
        WHERE ativo = 1
        ORDER BY ordem, nome
    ''')

    for row in cursor.fetchall():
        subcats = json.loads(row['subcategorias']) if row['subcategorias'] else []
        categorias[row['nome']] = subcats

    conn.close()
    return categorias


def get_lista_categorias():
    """
    Retorna lista de categorias personalizadas (apenas do banco).
    """
    import json

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, nome, subcategorias, icone, cor, ordem, ativo
        FROM categorias
        ORDER BY ordem, nome
    ''')

    categorias = []
    for row in cursor.fetchall():
        categorias.append({
            'id': row['id'],
            'nome': row['nome'],
            'subcategorias': json.loads(row['subcategorias']) if row['subcategorias'] else [],
            'icone': row['icone'],
            'cor': row['cor'],
            'ordem': row['ordem'],
            'ativo': bool(row['ativo']),
            'personalizada': True
        })

    conn.close()
    return categorias


def add_categoria(nome, subcategorias=None, icone=None, cor=None):
    """
    Adiciona uma nova categoria personalizada.
    """
    import json

    conn = get_connection()
    cursor = conn.cursor()

    # Verificar se já existe (no banco ou padrão)
    cursor.execute('SELECT id FROM categorias WHERE nome = ?', (nome,))
    if cursor.fetchone():
        conn.close()
        return {'success': False, 'error': 'Categoria já existe'}

    if nome in config.CATEGORIAS:
        conn.close()
        return {'success': False, 'error': 'Categoria padrão com este nome já existe'}

    subcats_json = json.dumps(subcategorias) if subcategorias else '[]'

    # Pegar próxima ordem
    cursor.execute('SELECT MAX(ordem) as max_ordem FROM categorias')
    result = cursor.fetchone()
    proxima_ordem = (result['max_ordem'] or 0) + 1

    cursor.execute('''
        INSERT INTO categorias (nome, subcategorias, icone, cor, ordem)
        VALUES (?, ?, ?, ?, ?)
    ''', (nome, subcats_json, icone, cor, proxima_ordem))

    conn.commit()
    categoria_id = cursor.lastrowid
    conn.close()

    return {'success': True, 'id': categoria_id}


def update_categoria(categoria_id, nome=None, subcategorias=None, icone=None, cor=None, ativo=None):
    """
    Atualiza uma categoria existente.
    """
    import json

    conn = get_connection()
    cursor = conn.cursor()

    # Verificar se existe
    cursor.execute('SELECT nome FROM categorias WHERE id = ?', (categoria_id,))
    atual = cursor.fetchone()
    if not atual:
        conn.close()
        return {'success': False, 'error': 'Categoria não encontrada'}

    # Construir update dinâmico
    updates = []
    params = []

    if nome is not None:
        # Verificar nome duplicado
        cursor.execute('SELECT id FROM categorias WHERE nome = ? AND id != ?', (nome, categoria_id))
        if cursor.fetchone() or (nome in config.CATEGORIAS and nome != atual['nome']):
            conn.close()
            return {'success': False, 'error': 'Já existe categoria com este nome'}
        updates.append('nome = ?')
        params.append(nome)

    if subcategorias is not None:
        updates.append('subcategorias = ?')
        params.append(json.dumps(subcategorias))

    if icone is not None:
        updates.append('icone = ?')
        params.append(icone)

    if cor is not None:
        updates.append('cor = ?')
        params.append(cor)

    if ativo is not None:
        updates.append('ativo = ?')
        params.append(1 if ativo else 0)

    if not updates:
        conn.close()
        return {'success': True}

    params.append(categoria_id)
    query = f"UPDATE categorias SET {', '.join(updates)} WHERE id = ?"
    cursor.execute(query, params)

    conn.commit()
    conn.close()

    return {'success': True}


def delete_categoria(categoria_id):
    """
    Remove uma categoria personalizada.
    Não permite remover se houver transações vinculadas.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Verificar se existe
    cursor.execute('SELECT nome FROM categorias WHERE id = ?', (categoria_id,))
    categoria = cursor.fetchone()
    if not categoria:
        conn.close()
        return {'success': False, 'error': 'Categoria não encontrada'}

    # Verificar se há transações
    cursor.execute('SELECT COUNT(*) as count FROM transacoes WHERE categoria = ?', (categoria['nome'],))
    count = cursor.fetchone()['count']

    if count > 0:
        conn.close()
        return {'success': False, 'error': f'Não é possível excluir: {count} transações usam esta categoria'}

    cursor.execute('DELETE FROM categorias WHERE id = ?', (categoria_id,))
    conn.commit()
    conn.close()

    return {'success': True}


def editar_categoria_padrao(nome_original, nome_novo, subcategorias):
    """
    Edita uma categoria padrão criando uma versão personalizada.
    Se o nome mudar, também atualiza as transações existentes.
    """
    import json

    conn = get_connection()
    cursor = conn.cursor()

    # Verificar se já existe uma personalização desta categoria
    cursor.execute('SELECT id FROM categorias WHERE nome = ?', (nome_original,))
    existente = cursor.fetchone()

    subcats_json = json.dumps(subcategorias) if subcategorias else '[]'

    if existente:
        # Atualizar existente
        cursor.execute('''
            UPDATE categorias
            SET nome = ?, subcategorias = ?
            WHERE id = ?
        ''', (nome_novo, subcats_json, existente['id']))
    else:
        # Criar nova entrada
        cursor.execute('SELECT MAX(ordem) as max_ordem FROM categorias')
        result = cursor.fetchone()
        proxima_ordem = (result['max_ordem'] or 0) + 1

        cursor.execute('''
            INSERT INTO categorias (nome, subcategorias, ordem)
            VALUES (?, ?, ?)
        ''', (nome_novo, subcats_json, proxima_ordem))

    # Se o nome mudou, atualizar transações existentes
    if nome_original != nome_novo:
        cursor.execute('''
            UPDATE transacoes
            SET categoria = ?
            WHERE categoria = ?
        ''', (nome_novo, nome_original))

        # Atualizar também regras de categorização
        cursor.execute('''
            UPDATE regras_categorizacao
            SET categoria = ?
            WHERE categoria = ?
        ''', (nome_novo, nome_original))

    conn.commit()
    conn.close()

    return {'success': True}


def get_descricoes_unicas():
    """
    Retorna lista de descrições únicas das transações para autocomplete.
    Inclui tanto descrições originais quanto normalizadas.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT DISTINCT descricao, descricao_normalizada, categoria, valor
        FROM transacoes
        WHERE descricao IS NOT NULL AND descricao != ''
        ORDER BY descricao
    ''')

    resultados = cursor.fetchall()
    conn.close()

    # Criar lista com descrições únicas e suas informações
    descricoes = {}
    for row in resultados:
        desc_norm = row['descricao_normalizada'] or row['descricao']
        if desc_norm not in descricoes:
            descricoes[desc_norm] = {
                'descricao': row['descricao'],
                'descricao_normalizada': desc_norm,
                'categoria': row['categoria'],
                'valor_exemplo': row['valor']
            }

    return list(descricoes.values())


# ============================================================================
# MAPEAMENTO DE DESCRIÇÕES
# ============================================================================

def salvar_mapeamento_descricao(descricao_original, descricao_customizada):
    """Salva ou atualiza um mapeamento de descrição"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT INTO mapeamento_descricoes (descricao_original, descricao_customizada)
            VALUES (?, ?)
            ON CONFLICT(descricao_original) DO UPDATE SET
                descricao_customizada = excluded.descricao_customizada,
                atualizado_em = CURRENT_TIMESTAMP
        ''', (descricao_original, descricao_customizada))

        conn.commit()
        return {'success': True, 'descricao_original': descricao_original, 'descricao_customizada': descricao_customizada}
    except Exception as e:
        return {'success': False, 'error': str(e)}
    finally:
        conn.close()


def get_mapeamentos_descricao():
    """Retorna todos os mapeamentos de descrição"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, descricao_original, descricao_customizada, criado_em, atualizado_em
        FROM mapeamento_descricoes
        ORDER BY descricao_customizada
    ''')

    mapeamentos = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return mapeamentos


def get_mapeamento_por_descricao(descricao_original):
    """Busca mapeamento para uma descrição específica"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT descricao_customizada
        FROM mapeamento_descricoes
        WHERE descricao_original = ?
    ''', (descricao_original,))

    row = cursor.fetchone()
    conn.close()

    return row['descricao_customizada'] if row else None


def deletar_mapeamento_descricao(descricao_original):
    """Remove um mapeamento de descrição"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('DELETE FROM mapeamento_descricoes WHERE descricao_original = ?', (descricao_original,))
    deleted = cursor.rowcount > 0

    conn.commit()
    conn.close()

    return {'success': deleted}


def aplicar_mapeamentos_descricao(transacoes):
    """Aplica os mapeamentos de descrição a uma lista de transações"""
    # Buscar todos os mapeamentos uma vez
    mapeamentos = {m['descricao_original']: m['descricao_customizada'] for m in get_mapeamentos_descricao()}

    if not mapeamentos:
        return transacoes

    # Aplicar mapeamentos
    for tx in transacoes:
        desc_original = tx.get('descricao') or tx.get('descricao_original', '')
        if desc_original in mapeamentos:
            tx['descricao_original'] = desc_original
            tx['descricao'] = mapeamentos[desc_original]
            tx['tem_mapeamento'] = True
        else:
            tx['tem_mapeamento'] = False

    return transacoes


def get_regras_categorizacao():
    """
    Retorna todas as regras de categorização cadastradas.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, padrao, categoria, subcategoria, confianca, uso_count,
               criado_em, atualizado_em
        FROM regras_categorizacao
        ORDER BY categoria, padrao
    ''')

    regras = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return regras


def adicionar_regra_categorizacao(padrao, categoria, subcategoria=None):
    """
    Adiciona ou atualiza uma regra de categorização.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT INTO regras_categorizacao (padrao, categoria, subcategoria)
            VALUES (?, ?, ?)
            ON CONFLICT(padrao) DO UPDATE SET
                categoria = excluded.categoria,
                subcategoria = excluded.subcategoria,
                uso_count = uso_count + 1,
                atualizado_em = CURRENT_TIMESTAMP
        ''', (padrao.upper().strip(), categoria, subcategoria))

        conn.commit()
        conn.close()
        return {'success': True}

    except Exception as e:
        conn.close()
        return {'success': False, 'error': str(e)}


def excluir_regra_categorizacao(regra_id):
    """
    Exclui uma regra de categorização pelo ID.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('DELETE FROM regras_categorizacao WHERE id = ?', (regra_id,))

    if cursor.rowcount == 0:
        conn.close()
        return {'success': False, 'error': 'Regra não encontrada'}

    conn.commit()
    conn.close()
    return {'success': True}


def atualizar_regra_categorizacao(regra_id, padrao=None, categoria=None, subcategoria=None):
    """
    Atualiza uma regra de categorização existente.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Buscar regra atual
    cursor.execute('SELECT * FROM regras_categorizacao WHERE id = ?', (regra_id,))
    regra = cursor.fetchone()

    if not regra:
        conn.close()
        return {'success': False, 'error': 'Regra não encontrada'}

    # Usar valores atuais se não fornecidos
    novo_padrao = padrao.upper().strip() if padrao else regra['padrao']
    nova_categoria = categoria if categoria else regra['categoria']
    nova_subcategoria = subcategoria if subcategoria is not None else regra['subcategoria']

    try:
        cursor.execute('''
            UPDATE regras_categorizacao
            SET padrao = ?, categoria = ?, subcategoria = ?, atualizado_em = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (novo_padrao, nova_categoria, nova_subcategoria, regra_id))

        conn.commit()
        conn.close()
        return {'success': True}

    except Exception as e:
        conn.close()
        return {'success': False, 'error': str(e)}


def get_variacao_subcategorias(mes_referencia, categoria, num_meses=6):
    """
    Calcula a variação de gastos por subcategoria comparado à média histórica.

    Returns:
        dict: { 'subcategoria': { 'total_atual': x, 'media_historica': y, 'variacao_pct': z } }
    """
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Identificar meses anteriores (excluindo o atual)
    cursor.execute('''
        SELECT DISTINCT mes_referencia
        FROM transacoes
        WHERE mes_referencia < ?
        ORDER BY mes_referencia DESC
        LIMIT ?
    ''', (mes_referencia, num_meses))

    meses_anteriores = [row['mes_referencia'] for row in cursor.fetchall()]

    # 2. Buscar total atual por subcategoria
    cursor.execute('''
        SELECT subcategoria, SUM(valor) as total
        FROM transacoes
        WHERE mes_referencia = ? AND categoria = ? AND valor > 0
        GROUP BY subcategoria
    ''', (mes_referencia, categoria))

    totais_atuais = {row['subcategoria'] or 'Sem subcategoria': row['total']
                     for row in cursor.fetchall()}

    # 3. Buscar média histórica por subcategoria
    variacoes = {}

    if meses_anteriores:
        placeholders = ','.join(['?'] * len(meses_anteriores))
        cursor.execute(f'''
            SELECT subcategoria, AVG(total_mes) as media
            FROM (
                SELECT subcategoria, mes_referencia, SUM(valor) as total_mes
                FROM transacoes
                WHERE mes_referencia IN ({placeholders})
                  AND categoria = ?
                  AND valor > 0
                GROUP BY subcategoria, mes_referencia
            )
            GROUP BY subcategoria
        ''', meses_anteriores + [categoria])

        medias = {row['subcategoria'] or 'Sem subcategoria': row['media']
                  for row in cursor.fetchall()}
    else:
        medias = {}

    conn.close()

    # 4. Calcular variação para cada subcategoria
    todas_subcats = set(totais_atuais.keys()) | set(medias.keys())

    for subcat in todas_subcats:
        total_atual = totais_atuais.get(subcat, 0)
        media = medias.get(subcat, 0)

        if media > 0:
            variacao_pct = ((total_atual - media) / media) * 100
        else:
            variacao_pct = 100 if total_atual > 0 else 0  # Novo gasto

        variacoes[subcat] = {
            'total_atual': total_atual,
            'media_historica': media,
            'variacao_pct': variacao_pct
        }

    return variacoes


def get_variacao_categoria(mes_referencia, categoria, num_meses=6):
    """
    Calcula a variação de gastos de uma categoria comparado à média histórica.

    Returns:
        dict: { 'total_atual': x, 'media_historica': y, 'variacao_pct': z }
    """
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Total atual
    cursor.execute('''
        SELECT SUM(valor) as total
        FROM transacoes
        WHERE mes_referencia = ? AND categoria = ? AND valor > 0
    ''', (mes_referencia, categoria))

    row = cursor.fetchone()
    total_atual = row['total'] if row and row['total'] else 0

    # 2. Identificar meses anteriores
    cursor.execute('''
        SELECT DISTINCT mes_referencia
        FROM transacoes
        WHERE mes_referencia < ?
        ORDER BY mes_referencia DESC
        LIMIT ?
    ''', (mes_referencia, num_meses))

    meses_anteriores = [row['mes_referencia'] for row in cursor.fetchall()]

    # 3. Calcular média histórica
    if meses_anteriores:
        placeholders = ','.join(['?'] * len(meses_anteriores))
        cursor.execute(f'''
            SELECT AVG(total_mes) as media
            FROM (
                SELECT mes_referencia, SUM(valor) as total_mes
                FROM transacoes
                WHERE mes_referencia IN ({placeholders})
                  AND categoria = ?
                  AND valor > 0
                GROUP BY mes_referencia
            )
        ''', meses_anteriores + [categoria])

        row = cursor.fetchone()
        media = row['media'] if row and row['media'] else 0
    else:
        media = 0

    conn.close()

    # 4. Calcular variação
    if media > 0:
        variacao_pct = ((total_atual - media) / media) * 100
    else:
        variacao_pct = 100 if total_atual > 0 else 0

    return {
        'total_atual': total_atual,
        'media_historica': media,
        'variacao_pct': variacao_pct
    }


def get_variacao_subcategorias_mes_anterior(mes_referencia, categoria):
    """
    Calcula a variação de gastos por subcategoria comparado ao mês anterior.
    Returns:
        dict: { 'subcategoria': { 'total_atual': x, 'media_historica': y, 'variacao_pct': z } }
    """
    # Calcular mês anterior
    try:
        ano, mes = map(int, mes_referencia.split('-'))
        data_atual = datetime(ano, mes, 1)
        data_anterior = data_atual - timedelta(days=1)
        mes_anterior = data_anterior.strftime('%Y-%m')
    except ValueError:
        return {}

    conn = get_connection()
    cursor = conn.cursor()

    # Buscar totais do mês atual e anterior para a categoria específica
    cursor.execute('''
        SELECT subcategoria, mes_referencia, SUM(valor) as total
        FROM transacoes
        WHERE mes_referencia IN (?, ?)
          AND categoria = ?
          AND valor > 0
        GROUP BY subcategoria, mes_referencia
    ''', (mes_referencia, mes_anterior, categoria))
    
    resultados = cursor.fetchall()
    conn.close()

    # Organizar dados
    dados_mes = {}
    dados_anterior = {}
    
    for r in resultados:
        subcat = r['subcategoria'] or 'Sem subcategoria'
        if r['mes_referencia'] == mes_referencia:
            dados_mes[subcat] = r['total']
        else:
            dados_anterior[subcat] = r['total']
            
    variacoes = {}
    
    # Calcular para todas as subcategorias que têm gastos no mês atual
    for subcat, valor_atual in dados_mes.items():
        valor_anterior = dados_anterior.get(subcat, 0)
        
        if valor_anterior > 0:
            variacao_pct = ((valor_atual - valor_anterior) / valor_anterior) * 100
        elif valor_atual > 0:
            variacao_pct = 100.0 # Novo gasto
        else:
            variacao_pct = 0.0
            
        variacoes[subcat] = {
            'total_atual': valor_atual,
            'media_historica': valor_anterior, # Mantendo nome da chave para compatibilidade com frontend
            'variacao_pct': variacao_pct
        }
        
    return variacoes


if __name__ == '__main__':
    # Criar diretórios e inicializar banco
    config.create_directories()
    init_database()
