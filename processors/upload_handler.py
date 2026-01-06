"""
Processador de uploads de arquivos ZIP com senha
"""
import os
import re
import zipfile
import hashlib
import tempfile
import shutil
from datetime import datetime
from werkzeug.utils import secure_filename
import config
from processors import csv_parser, categorizer
from database import db


def extrair_mes_referencia_do_arquivo(nome_arquivo):
    """
    Extrai o mês de referência do nome do arquivo CSV do C6 Bank.

    Formatos suportados:
    - Fatura_2025-11-10.csv -> 2025-11
    - Fatura_2025-11.csv -> 2025-11
    - fatura-2025-11.csv -> 2025-11

    Returns:
        str: Mês no formato YYYY-MM ou None se não encontrar
    """
    # Padrão: busca YYYY-MM no nome do arquivo
    match = re.search(r'(\d{4})-(\d{2})', nome_arquivo)
    if match:
        return f"{match.group(1)}-{match.group(2)}"

    # Padrão alternativo: DD-MM-YYYY ou DD/MM/YYYY
    match = re.search(r'(\d{2})[-/](\d{2})[-/](\d{4})', nome_arquivo)
    if match:
        return f"{match.group(3)}-{match.group(2)}"

    return None

def processar_upload(file, senha=None):
    """
    Processa um arquivo ZIP enviado
    
    Args:
        file: Arquivo do upload (werkzeug FileStorage)
        senha: Senha do ZIP (usa config.ZIP_PASSWORD se não fornecida)
    
    Returns:
        dict: {
            'sucesso': bool,
            'mensagem': str,
            'num_transacoes': int,
            'mes_referencia': str
        }
    """
    if not senha:
        senha = config.ZIP_PASSWORD
    
    # Verificar extensão
    if not file.filename.endswith('.zip'):
        return {
            'sucesso': False,
            'mensagem': 'Arquivo deve ser .zip',
            'num_transacoes': 0
        }
    
    # Salvar temporariamente
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, secure_filename(file.filename))
    file.save(zip_path)
    
    try:
        # Calcular hash do arquivo
        file_hash = calcular_hash(zip_path)
        
        # Verificar se já foi processado
        if arquivo_ja_processado(file_hash):
            shutil.rmtree(temp_dir)
            return {
                'sucesso': False,
                'mensagem': 'Arquivo já foi processado anteriormente',
                'num_transacoes': 0
            }
        
        # Extrair ZIP
        csv_path = extrair_zip(zip_path, senha, temp_dir)
        
        if not csv_path:
            shutil.rmtree(temp_dir)
            return {
                'sucesso': False,
                'mensagem': 'Senha incorreta ou arquivo corrompido',
                'num_transacoes': 0
            }
        
        # Validar CSV (Flexível para aceitar Extratos e Faturas)
        # O parser irá falhar se não encontrar formato válido, então podemos pular validação estrita aqui
        # valido, msg_validacao = csv_parser.validar_csv(csv_path)
        # if not valido:
        #     shutil.rmtree(temp_dir)
        #     return {
        #         'sucesso': False,
        #         'mensagem': f'CSV inválido: {msg_validacao}',
        #         'num_transacoes': 0
        #     }
        
        # Extrair mês de referência do nome do arquivo CSV
        # Ex: Fatura_2025-11-10.csv -> 2025-11
        nome_csv = os.path.basename(csv_path)
        mes_referencia_arquivo = extrair_mes_referencia_do_arquivo(nome_csv)

        # Parsear transações
        transacoes = csv_parser.parse_c6_csv(csv_path)

        if not transacoes:
            shutil.rmtree(temp_dir)
            return {
                'sucesso': False,
                'mensagem': 'Nenhuma transação válida encontrada (formato irreconhecível?)',
                'num_transacoes': 0
            }

        # Categorizar transações
        transacoes = categorizer.categorizar_lote(transacoes)

        # Usar mês do arquivo se encontrado, senão usar da primeira transação
        mes_referencia = mes_referencia_arquivo or (transacoes[0]['mes_referencia'] if transacoes else None)
        num_inseridas = 0

        for transacao in transacoes:
            try:
                # IMPORTANTE: Usar o mês da FATURA, não da compra original
                db.insert_transacao(
                    data_compra=transacao['data_compra'],
                    descricao=transacao['descricao'],
                    valor=transacao['valor'],
                    categoria=transacao.get('categoria'),
                    subcategoria=transacao.get('subcategoria'),
                    parcela=transacao['parcela'],
                    cartao=transacao['cartao'],
                    mes_referencia=mes_referencia,  # Mês da fatura, não da compra
                    fonte_arquivo=file.filename,
                    tipo=transacao.get('tipo', 'cartao')
                )
                num_inseridas += 1
            except Exception as e:
                print(f"Erro ao inserir transação: {e}")
        
        # Registrar upload
        registrar_upload(file.filename, 'cartao', mes_referencia, num_inseridas, file_hash)
        
        # Limpar temporários
        shutil.rmtree(temp_dir)
        
        return {
            'sucesso': True,
            'mensagem': f'{num_inseridas} transações importadas com sucesso!',
            'num_transacoes': num_inseridas,
            'mes_referencia': mes_referencia
        }
        
    except Exception as e:
        # Limpar em caso de erro
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        
        return {
            'sucesso': False,
            'mensagem': f'Erro ao processar arquivo: {str(e)}',
            'num_transacoes': 0
        }

def extrair_zip(zip_path, senha, dest_dir):
    """
    Extrai arquivo ZIP com senha
    
    Returns:
        str: Caminho do CSV extraído ou None se falhar
    """
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Listar arquivos
            file_list = zip_ref.namelist()
            
            # Procurar CSV
            csv_file = None
            for filename in file_list:
                if filename.endswith('.csv'):
                    csv_file = filename
                    break
            
            if not csv_file:
                return None
            
            # Extrair com senha
            zip_ref.extract(csv_file, dest_dir, pwd=senha.encode('utf-8'))
            
            return os.path.join(dest_dir, csv_file)
            
    except Exception as e:
        print(f"Erro ao extrair ZIP: {e}")
        return None

def calcular_hash(filepath):
    """
    Calcula hash SHA256 do arquivo
    """
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def arquivo_ja_processado(file_hash):
    """
    Verifica se arquivo com este hash já foi processado
    """
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) as count FROM uploads WHERE hash = ?', (file_hash,))
    result = cursor.fetchone()
    conn.close()
    
    return result['count'] > 0

def registrar_upload(nome_arquivo, tipo, mes_referencia, num_transacoes, file_hash):
    """
    Registra upload no histórico
    """
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO uploads (nome_arquivo, tipo, mes_referencia, num_transacoes, hash)
        VALUES (?, ?, ?, ?, ?)
    ''', (nome_arquivo, tipo, mes_referencia, num_transacoes, file_hash))
    
    conn.commit()
    conn.close()

def get_historico_uploads(limit=10):
    """
    Retorna histórico de uploads
    """
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM uploads
        ORDER BY data_upload DESC
        LIMIT ?
    ''', (limit,))
    
    uploads = cursor.fetchall()
    conn.close()
    
    return uploads

if __name__ == '__main__':
    # Teste
    print("Módulo de upload pronto!")
    print(f"Pasta de uploads: {config.UPLOAD_FOLDER}")
