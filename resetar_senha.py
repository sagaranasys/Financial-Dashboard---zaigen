"""
Script para resetar a senha de acesso do Dashboard
"""
import sqlite3
import bcrypt
import os

# Caminho do banco de dados
DB_PATH = os.path.join('database', 'finance.db')

def resetar_senha():
    """Reseta a senha para 'admin123'"""
    
    # Gerar novo hash para 'admin123'
    senha = 'admin123'
    password_hash = bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt())
    
    # Conectar ao banco
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Atualizar senha
    cursor.execute('''
        INSERT OR REPLACE INTO configuracoes (chave, valor) 
        VALUES ('password_hash', ?)
    ''', (password_hash.decode('utf-8'),))
    
    conn.commit()
    conn.close()
    
    print("=" * 60)
    print("✓ Senha resetada com sucesso!")
    print("=" * 60)
    print("Nova senha: admin123")
    print("=" * 60)
    print("\nAgora você pode:")
    print("1. Rodar o sistema: python app.py")
    print("2. Acessar: http://localhost:5000")
    print("3. Login com senha: admin123")
    print("=" * 60)

if __name__ == '__main__':
    if not os.path.exists(DB_PATH):
        print("❌ ERRO: Banco de dados não encontrado!")
        print("Execute primeiro: python database/db.py")
    else:
        resetar_senha()
