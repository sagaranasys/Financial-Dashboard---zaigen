"""
Sistema de categorização automática de transações
"""
import re
import config
from database import db

def normalizar_descricao(descricao):
    """
    Normaliza descrição para padronização
    - Remove espaços extras
    - Converte para maiúsculas
    - Remove caracteres especiais (mantém * para padrões)
    """
    if not descricao:
        return ''
    
    desc = descricao.upper().strip()
    desc = re.sub(r'\s+', ' ', desc)
    desc = re.sub(r'[^A-Z0-9\s\*]', '', desc)
    
    return desc

def categorizar_transacao(descricao):
    """
    Categoriza uma transação baseado na descrição
    
    Ordem de prioridade:
    1. Regras aprendidas pelo usuário
    2. Palavras-chave configuradas
    3. Retorna None (não classificado)
    
    Returns:
        tuple: (categoria, subcategoria, confianca)
    """
    desc_norm = normalizar_descricao(descricao)
    
    # 1. Verificar regras aprendidas
    categoria, subcategoria = verificar_regras_aprendidas(desc_norm)
    if categoria:
        return categoria, subcategoria, 1.0
    
    # 2. Verificar palavras-chave
    categoria, subcategoria = categorizar_por_keywords(desc_norm)
    if categoria:
        return categoria, subcategoria, 0.8
    
    # 3. Não classificado
    return None, None, 0.0

def verificar_regras_aprendidas(descricao_normalizada):
    """
    Verifica se existe regra aprendida para esta descrição
    """
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # Buscar match exato
    cursor.execute('''
        SELECT categoria, subcategoria 
        FROM regras_categorizacao
        WHERE padrao = ?
        ORDER BY confianca DESC, uso_count DESC
        LIMIT 1
    ''', (descricao_normalizada,))
    
    result = cursor.fetchone()
    
    if result:
        conn.close()
        return result['categoria'], result['subcategoria']
    
    # Buscar match parcial (contém)
    cursor.execute('''
        SELECT categoria, subcategoria, padrao
        FROM regras_categorizacao
        WHERE ? LIKE '%' || padrao || '%'
        ORDER BY LENGTH(padrao) DESC, confianca DESC
        LIMIT 1
    ''', (descricao_normalizada,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return result['categoria'], result['subcategoria']
    
    return None, None

def categorizar_por_keywords(descricao_normalizada):
    """
    Categoriza baseado em palavras-chave configuradas
    """
    for categoria, keywords in config.KEYWORDS_CATEGORIAS.items():
        for keyword in keywords:
            if keyword.upper() in descricao_normalizada:
                # Determinar subcategoria baseado na categoria
                subcategoria = determinar_subcategoria(categoria, descricao_normalizada)
                return categoria, subcategoria
    
    return None, None

def determinar_subcategoria(categoria, descricao):
    """
    Determina subcategoria baseado na categoria e descrição
    """
    subcategorias = config.CATEGORIAS.get(categoria, [])
    
    if not subcategorias:
        return None
    
    # Mapeamento de keywords para subcategorias
    subcategoria_keywords = {
        'Alimentação': {
            'Supermercado': ['ZAFFARI', 'CARREFOUR', 'MERCADO', 'SUPERMERCADO'],
            'Delivery': ['IFOOD', 'IFD', 'UBER EATS', 'RAPPI', 'MARKET4U', 'AIQFOME', 'GOOMER'],
            'Restaurante': ['RESTAURANTE', 'LANCHONETE', 'BAR', 'CAFE', 'DELITZZI']
        },
        'Transporte': {
            'Uber/99': ['UBER', 'PG 99', 'PG *99', '99 ', '99APP', '99POP', 'CABIFY'],
            'Passagens': ['GOL', 'AZUL', 'LATAM', 'AIRBNB', 'DECOLAR', 'BOOKING'],
            'Estacionamento': ['PARKING', 'STOP', 'ESTACIONAMENTO'],
            'Combustível': ['POSTO', 'COMBUSTIVEL', 'SHELL', 'IPIRANGA', 'BR DISTRIBUI', 'PETROB']
        },
        'Streaming/Assinaturas': {
            'Netflix/Spotify': ['NETFLIX', 'SPOTIFY', 'DEEZER'],
            'Microsoft': ['MICROSOFT'],
            'Apple': ['APPLE'],
            'Outros': ['GOOGLE', 'YOUTUBE', 'PRIME', 'HBO', 'DISNEY', 'GLOBOPLAY', 'PARAMOUNT']
        },
        'Telecom': {
            'Internet': ['NET', 'CLARO', 'INTERNET', 'LAVOTECH'],
            'Celular': ['TIM', 'VIVO', 'OI'],
            'TV': ['SKY', 'TV']
        },
        'Saúde': {
            'Farmácia': ['FARMACIA', 'DROGARIA', 'PANVEL', 'RAIA', 'PACHECO', 'DROGASIL', 'PAGUE MENOS']
        },
        'Casa/Móveis': {
            'Pet Shop': ['PETLOVE', 'COBASI', 'PETZ'],
            'Eletrônicos': ['AMAZON', 'MERCADOLIVRE', 'MAGAZINE', 'MAGALU', 'CASAS BAHIA', 'SHOPEE', 'ALIEXPRESS', 'SHEIN'],
            'Móveis': ['LEROY', 'MADEIRA']
        },
        'Educação/Profissional': {
            'Ferramentas': ['NELOGICA', 'SMARTTBOT', 'QUANTUM', 'AUGMENT', 'IUGU'],
            'Contabilidade': ['CONTAB'],
            'Cursos': ['HUBLA', 'UDEMY', 'COURSERA', 'HOTMART', 'EDUZZ', 'KIWIFY']
        },
        'Serviços Pessoais': {
            'Academia': ['SMARTFIT', 'GYMPASS', 'TOTALPASS', 'ACADEMIA'],
            'Estética': ['BARBEARIA', 'BARBER', 'ESTETICA', 'SALAO', 'TRUSS', 'BOX688']
        }
    }
    
    # Verificar keywords de subcategoria
    if categoria in subcategoria_keywords:
        for subcat, keywords in subcategoria_keywords[categoria].items():
            for keyword in keywords:
                if keyword in descricao:
                    return subcat
    
    # Retornar primeira subcategoria como padrão
    return subcategorias[0] if subcategorias else None

def salvar_regra_categorizacao(padrao, categoria, subcategoria=None):
    """
    Salva uma regra de categorização aprendida
    """
    conn = db.get_connection()
    cursor = conn.cursor()
    
    padrao_norm = normalizar_descricao(padrao)
    
    try:
        cursor.execute('''
            INSERT INTO regras_categorizacao (padrao, categoria, subcategoria)
            VALUES (?, ?, ?)
            ON CONFLICT(padrao) DO UPDATE SET
                categoria = excluded.categoria,
                subcategoria = excluded.subcategoria,
                uso_count = uso_count + 1,
                atualizado_em = CURRENT_TIMESTAMP
        ''', (padrao_norm, categoria, subcategoria))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Erro ao salvar regra: {e}")
        conn.close()
        return False

def categorizar_lote(transacoes):
    """
    Categoriza um lote de transações
    
    Args:
        transacoes: Lista de dicts com pelo menos 'descricao'
    
    Returns:
        Lista de transações com 'categoria' e 'subcategoria' adicionados
    """
    for transacao in transacoes:
        categoria, subcategoria, confianca = categorizar_transacao(transacao['descricao'])
        transacao['categoria'] = categoria
        transacao['subcategoria'] = subcategoria
        transacao['confianca_categorizacao'] = confianca
    
    return transacoes

if __name__ == '__main__':
    # Testes
    testes = [
        "IFOOD       *IFOOD",
        "UBER UBER *TRIP HELP.U",
        "NETFLIX.COM",
        "NELOGICA SISTEMAS DE S",
        "ZAFFARI IPIRANGA",
        "PETLOVE*PL*ORDER 2114"
    ]
    
    print("Testes de categorização:\n")
    for descricao in testes:
        cat, subcat, conf = categorizar_transacao(descricao)
        print(f"{descricao[:30]:30} → {cat:20} / {subcat:15} (conf: {conf:.1f})")
