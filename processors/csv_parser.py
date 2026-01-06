"""
Parser de arquivos CSV do C6 Bank (Fatura e Conta Corrente)
"""
import csv
import re
from datetime import datetime
from processors.categorizer import normalizar_descricao

def parse_c6_csv(filepath):
    """
    Função roteadora que detecta o tipo de arquivo e chama o parser correto
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read(2048) # Lê os primeiros 2KB
            
            # Detectar assinatura de Extrato de Conta
            if "EXTRATO DE CONTA CORRENTE C6 BANK" in content or "Agência:" in content and "Conta:" in content:
                print("DEBUG: Detectado Extrato de Conta Corrente")
                return parse_extrato_conta_c6(filepath)
            
            # Detectar assinatura de Fatura de Cartão (colunas típicas)
            if "Nome no Cartão" in content or "Final do Cartão" in content:
                print("DEBUG: Detectado Fatura de Cartão")
                return parse_fatura_cartao_c6(filepath)
                
            # Fallback (tenta como cartão, que é o padrão antigo)
            print("DEBUG: Formato desconhecido, tentando como Fatura de Cartão")
            return parse_fatura_cartao_c6(filepath)
            
    except Exception as e:
        print(f"Erro ao detectar tipo de arquivo: {e}")
        return []

def parse_fatura_cartao_c6(filepath):
    """
    Faz parse do CSV de FATURA DE CARTÃO do C6 Bank
    """
    transacoes = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        # Detectar delimitador
        primeira_linha = f.readline()
        f.seek(0)
        
        delimiter = ';' if ';' in primeira_linha else ','
        
        reader = csv.DictReader(f, delimiter=delimiter)
        
        for row in reader:
            try:
                # Extrair e limpar descrição
                descricao = row.get('Descrição', '').strip().strip('"').upper()

                # Pular APENAS linhas de pagamento de fatura (não são transações reais)
                if 'INCLUSAO DE PAGAMENTO' in descricao or 'PAGAMENTO EFETUADO' in descricao:
                    continue

                # Extrair dados
                valor_str = row.get('Valor (em R$)', '0')
                valor = parse_valor_monetario(valor_str)

                # Ignorar valores zero
                if valor == 0:
                    continue
                
                # Parsear data
                data_str = row.get('Data de Compra', '')
                data_compra = parse_data(data_str)
                
                # Criar transação
                transacao = {
                    'data_compra': data_compra,
                    'descricao': row.get('Descrição', ''),
                    'descricao_normalizada': normalizar_descricao(row.get('Descrição', '')),
                    'valor': valor,
                    'parcela': row.get('Parcela', 'Única'),
                    'cartao': row.get('Final do Cartão', 'Desconhecido'),
                    'categoria_original': row.get('Categoria', ''),
                    'mes_referencia': data_compra.strftime('%Y-%m') if data_compra else None,
                    'tipo': 'cartao' # Explicita que é cartão
                }
                
                transacoes.append(transacao)
                
            except Exception as e:
                print(f"Erro ao processar linha FATURA: {e}")
                continue
    
    return transacoes

def parse_valor_monetario(valor_str):
    """
    Converte string de valor monetário (BR ou US) para float com segurança.
    Exemplos:
    - "1.000,00" -> 1000.0
    - "1000,00"  -> 1000.0
    - "1000.00"  -> 1000.0 (Assume US se só tiver ponto e parecer decimal)
    - "1,000.00" -> 1000.0
    - "-50,00"   -> -50.0
    """
    if not valor_str:
        return 0.0
    
    v = valor_str.strip()
    
    # Remover R$ e espaços
    v = v.replace('R$', '').replace(' ', '')
    
    if not v:
        return 0.0

    # LIMPEZA CRÍTICA PARA NUMEROS COM PONTO E SINAL
    # Ex: "-550.00" -> "-550.00"
    
    # 1. Se tem múltiplos pontos (Ex: 1.000.000,00), removemos todos menos o último?
    # Melhor detecção hardcoded para C6 que sabemos usar BR (1.000,00)
    
    # Se terminar com ,XX (duas casas decimais após vírgula)
    if re.search(r',\d{2}$', v):
        # É formato BR: remove todos os pontos e substitui a vírgula final por ponto
        v = v.replace('.', '').replace(',', '.')
    
    # Se terminar com .XX (formato US ou Python nativo)
    elif re.search(r'\.\d{2}$', v):
        # É formato US: remove vírgulas (se houver) e mantém ponto
        v = v.replace(',', '')
        
    # Se não tiver separador decimal explícito (ex: 1000)
    # ou se for algo bizarro, tenta fallback padrão
    else:
        # Fallback original melhorado
        if ',' in v and '.' in v:
            last_comma = v.rfind(',')
            last_dot = v.rfind('.')
            if last_comma > last_dot: # BR
                v = v.replace('.', '').replace(',', '.')
            else: # US
                v = v.replace(',', '')
        elif ',' in v: 
            v = v.replace(',', '.')

    try:
        return float(v)
    except ValueError:
        return 0.0

def parse_extrato_conta_c6(filepath):
    """
    Faz parse do CSV de EXTRATO CONTA CORRENTE do C6 Bank
    
    Estrutura: Cabeçalho sujo nas primeiras ~8 linhas
    Colunas típicas: Data, Descrição, Valor (com sinal ou colunas separadas)
    """
    transacoes = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
        # 1. Tentar encontrar a linha de cabeçalho
        start_index = 0
        header_line = ""
        header_map = {}
        
        # Possíveis nomes de colunas para mapear
        colunas_possiveis = {
            'data': ['Data Lançamento', 'Data', 'Data Movimento'],
            'descricao': ['Descrição', 'Histórico', 'Título'],
            'entrada': ['Entrada(R$)', 'Crédito', 'Valor (Crédito)'],
            'saida': ['Saída(R$)', 'Débito', 'Valor (Débito)'],
            'valor_unico': ['Valor', 'Valor (R$)', 'Saldo']
        }
        
        for i, line in enumerate(lines):
            # Procura por linha que tenha pelo menos Data e Descrição
            line_upper = line.upper()
            if ("DATA" in line_upper and "DESCRI" in line_upper) or \
               ("DATA LANÇAMENTO" in line_upper):
                start_index = i + 1
                header_line = line.strip()
                break
        
        if not header_line:
            # Fallback: Tentar ler como CSV normal desde o início
            print("Aviso: Cabeçalho explícito não encontrado, tentando ler do início")
            start_index = 1 # Assume linha 0 como header
            header_line = lines[0].strip()

        # Detectar delimitador
        delimiter = ';' if ';' in header_line else ','
        
        # Preparar conteúdo para CSV Reader
        import io
        csv_content = header_line + '\n' + ''.join(lines[start_index:])
        reader = csv.DictReader(io.StringIO(csv_content), delimiter=delimiter)
        
        # Normalizar nomes das colunas (remove espaços, lower)
        fieldnames_norm = {f: f.strip().upper() for f in reader.fieldnames} if reader.fieldnames else {}
        
        # Encontrar as chaves corretas no CSV atual
        col_data = next((k for k, v in fieldnames_norm.items() if any(x.upper() in v for x in colunas_possiveis['data'])), None)
        col_desc = next((k for k, v in fieldnames_norm.items() if any(x.upper() in v for x in colunas_possiveis['descricao'])), None)
        col_entrada = next((k for k, v in fieldnames_norm.items() if any(x.upper() in v for x in colunas_possiveis['entrada'])), None)
        col_saida = next((k for k, v in fieldnames_norm.items() if any(x.upper() in v for x in colunas_possiveis['saida'])), None)
        col_valor = next((k for k, v in fieldnames_norm.items() if any(x.upper() in v for x in colunas_possiveis['valor_unico'])), None)
        
        # Coluna Título (específico C6)
        col_titulo = next((k for k in fieldnames_norm.keys() if 'TÍTULO' in fieldnames_norm[k]), None)

        for row in reader:
            try:
                # Obter Descrição
                descricao = row.get(col_desc, row.get('Descrição', '')).strip() if col_desc else ''
                if col_titulo:
                    titulo = row.get(col_titulo, '').strip()
                    if titulo:
                        descricao = f"{titulo} - {descricao}".strip(" -")
                
                if not descricao: 
                    continue # Linha vazia

                # Obter Data
                data_str = row.get(col_data, '').strip() if col_data else ''
                data_compra = parse_data(data_str)
                if not data_compra:
                    continue

                # Obter Valor
                valor = 0.0
                tipo = 'conta_credito'
                
                # Caso 1: Colunas separadas Entrada/Saída (Padrão C6 novo)
                if col_entrada and col_saida:
                    val_entrada = parse_valor_monetario(row.get(col_entrada, '0'))
                    val_saida = parse_valor_monetario(row.get(col_saida, '0'))
                    
                    if val_saida > 0: # É uma saída
                        valor = abs(val_saida) * -1
                        tipo = 'conta_debito'
                    elif val_entrada > 0: # É uma entrada
                        valor = abs(val_entrada)
                        tipo = 'conta_credito'
                    else:
                        continue # Zerado
                
                # Caso 2: Coluna única de Valor (com sinal negativo para saída)
                elif col_valor:
                    val_raw = parse_valor_monetario(row.get(col_valor, '0'))
                    if val_raw < 0:
                        valor = val_raw
                        tipo = 'conta_debito'
                    elif val_raw > 0:
                        valor = val_raw
                        tipo = 'conta_credito'
                    else:
                        continue
                
                else:
                    # Tentar fallback hardcoded para C6 antigo se colunas não baterem
                    try:
                         # Tenta pegar Entrada(R$) hardcoded
                         e = parse_valor_monetario(row.get('Entrada(R$)', '0'))
                         s = parse_valor_monetario(row.get('Saída(R$)', '0'))
                         if s > 0:
                             valor = -abs(s)
                             tipo = 'conta_debito'
                         elif e > 0:
                             valor = abs(e)
                             tipo = 'conta_credito'
                         else:
                             continue
                    except:
                        continue

                # Montar objeto
                transacao = {
                    'data_compra': data_compra,
                    'descricao': descricao,
                    'descricao_normalizada': normalizar_descricao(descricao),
                    'valor': valor,
                    'parcela': 'Única', 
                    'cartao': 'CONTA',
                    'categoria_original': 'Extrato',
                    'mes_referencia': data_compra.strftime('%Y-%m') if data_compra else None,
                    'tipo': tipo
                }
                
                transacoes.append(transacao)
                
            except Exception as e:
                print(f"Erro linha extrato: {e}")
                continue

    return transacoes

def parse_data(data_str):
    """
    Parseia string de data em diversos formatos
    
    Formatos suportados:
    - DD/MM/YYYY
    - DD-MM-YYYY
    - YYYY-MM-DD
    """
    if not data_str:
        return None
    
    # Tentar formatos comuns
    formatos = [
        '%d/%m/%Y',
        '%d-%m-%Y',
        '%Y-%m-%d',
        '%d/%m/%y',
        '%d-%m-%y'
    ]
    
    for formato in formatos:
        try:
            return datetime.strptime(data_str, formato)
        except ValueError:
            continue
    
    print(f"Aviso: Não foi possível parsear data: {data_str}")
    return None

def detectar_tipo_arquivo(filepath):
    """
    Detecta se o arquivo é de cartão ou extrato bancário
    baseado nas colunas
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        primeira_linha = f.readline().upper()
        
        # Arquivo de cartão C6 tem estas colunas características
        if 'FINAL DO CARTÃO' in primeira_linha or 'FINAL DO CARTAO' in primeira_linha:
            return 'cartao'
        
        # Extrato bancário (implementar depois se necessário)
        if 'SALDO' in primeira_linha or 'EXTRATO' in primeira_linha:
            return 'conta'
        
        # Padrão: assumir cartão
        return 'cartao'

def validar_csv(filepath):
    """
    Valida se o CSV tem a estrutura esperada
    
    Returns:
        tuple: (valido, mensagem_erro)
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            primeira_linha = f.readline()
            
            # Verificar colunas essenciais
            colunas_necessarias = ['Descrição', 'Valor']
            
            for coluna in colunas_necessarias:
                if coluna.lower() not in primeira_linha.lower():
                    return False, f"Coluna '{coluna}' não encontrada"
            
            return True, "Arquivo válido"
            
    except Exception as e:
        return False, f"Erro ao ler arquivo: {str(e)}"

if __name__ == '__main__':
    # Teste com arquivo de exemplo
    import sys
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
        valido, msg = validar_csv(filepath)
        print(f"Validação: {msg}")
        
        if valido:
            transacoes = parse_c6_csv(filepath)
            print(f"✓ {len(transacoes)} transações encontradas")
            
            if transacoes:
                print("\nPrimeiras 3 transações:")
                for t in transacoes[:3]:
                    print(f"  {t['data_compra'].strftime('%d/%m/%Y')}: {t['descricao'][:40]} - R$ {t['valor']:.2f}")
