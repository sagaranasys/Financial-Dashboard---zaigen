
from database.db import get_connection

# ============================================================================
# MÓDULO CONTA CORRENTE (SISTEMA 2)
# ============================================================================

def get_transacoes_conta(mes_referencia):
    """Retorna transações da conta corrente (Extrato)"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM transacoes
        WHERE mes_referencia = ? AND (tipo = 'conta_credito' OR tipo = 'conta_debito')
        ORDER BY data_compra DESC
    ''', (mes_referencia,))

    transacoes = cursor.fetchall()
    conn.close()
    return transacoes

def get_resumo_conta(mes_referencia):
    """
    Retorna resumo da conta:
    - Saldo do mês (Entradas - Saídas)
    - Total de Entradas
    - Total de Saídas
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Total Entradas (Positivo)
    cursor.execute('''
        SELECT SUM(valor) as total FROM transacoes
        WHERE mes_referencia = ? AND tipo = 'conta_credito'
    ''', (mes_referencia,))
    entradas = cursor.fetchone()['total'] or 0

    # Total Saídas (Negativo)
    cursor.execute('''
        SELECT SUM(valor) as total FROM transacoes
        WHERE mes_referencia = ? AND tipo = 'conta_debito'
    ''', (mes_referencia,))
    saidas = cursor.fetchone()['total'] or 0

    conn.close()

    return {
        'entradas': entradas,
        'saidas': saidas, # Já vem negativo do banco
        'saldo': entradas + saidas
    }
