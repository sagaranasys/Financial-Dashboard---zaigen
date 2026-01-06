"""
Configurações do Dashboard Financeiro
"""
import os
from datetime import timedelta

# Diretórios base
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, 'database', 'finance.db')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
BACKUP_FOLDER = os.path.join(BASE_DIR, 'backups')

# Configurações Flask
SECRET_KEY = 'dev-key-change-in-production-2025'  # Trocar em produção
SESSION_TIMEOUT = timedelta(minutes=60)

# Configurações de upload
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_EXTENSIONS = {'zip'}
ZIP_PASSWORD = '399838'  # Senha padrão dos ZIPs C6 Bank

# Configurações do banco
MAX_HISTORY_YEARS = 2  # Manter apenas 2 anos de histórico

# Senha de acesso (hash bcrypt)
# Padrão: 'admin123' - TROCAR na primeira execução
DEFAULT_PASSWORD_HASH = b'$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYqNXkYKu8u'

# Categorias padrão
CATEGORIAS = {
    'Alimentação': ['Supermercado', 'Delivery', 'Restaurante'],
    'Transporte': ['Uber/99', 'Combustível', 'Estacionamento', 'Passagens'],
    'Streaming/Assinaturas': ['Netflix/Spotify', 'Microsoft', 'Apple', 'Outros'],
    'Telecom': ['Internet', 'Celular', 'TV'],
    'Saúde': ['Farmácia', 'Consultas', 'Exames'],
    'Vestuário': ['Roupas', 'Calçados', 'Acessórios'],
    'Casa/Móveis': ['Móveis', 'Decoração', 'Eletrônicos', 'Pet Shop'],
    'Serviços Pessoais': ['Barbearia', 'Estética', 'Academia'],
    'Educação/Profissional': ['Cursos', 'Livros', 'Ferramentas', 'Contabilidade'],
    'Lazer': ['Games', 'Eventos', 'Hobbies'],
    'Empresarial': ['Fornecedores', 'Equipamentos'],
    'Outros': ['Diversos', 'Seguros', 'Taxas']
}

# Palavras-chave para categorização automática
KEYWORDS_CATEGORIAS = {
    'Alimentação': ['IFOOD', 'IFD*', 'IFD ', 'UBER EATS', 'RAPPI', 'ZAFFARI', 'CARREFOUR',
                    'MERCADO', 'SUPERMERCADO', 'PADARIA', 'RESTAURANTE', 'LANCHONETE', 'BAR',
                    'MARKET4U', 'DELITZZI', 'CAFE', 'AIQFOME', 'GOOMER'],
    'Transporte': ['UBER', 'PG 99', 'PG *99', '99 ', '99APP', '99POP', 'CABIFY', 'GOL LINHAS',
                   'AZUL', 'LATAM', 'TOP STOP', 'PARKING', 'POSTO', 'COMBUSTIVEL', 'AIRBNB',
                   'DECOLAR', 'BOOKING', 'SHELL', 'IPIRANGA', 'BR DISTRIBUI', 'PETROB'],
    'Streaming/Assinaturas': ['NETFLIX', 'SPOTIFY', 'APPLE.COM', 'MICROSOFT',
                               'GOOGLE ONE', 'YOUTUBE', 'PRIME VIDEO', 'DISNEY', 'HBO',
                               'GLOBOPLAY', 'PARAMOUNT', 'DEEZER', 'AMAZON PRIME'],
    'Telecom': ['CLARO', 'TIM', 'VIVO', 'OI', 'NET', 'TELEFONE', 'INTERNET',
                'LAVOTECH'],
    'Saúde': ['FARMACIA', 'DROGARIA', 'PANVEL', 'RAIA', 'PACHECO', 'HOSPITAL',
              'CLINICA', 'LABORATORIO', 'DROGASIL', 'PAGUE MENOS'],
    'Vestuário': ['RIACHUELO', 'RENNER', 'C&A', 'ZARA', 'NIKE', 'ADIDAS',
                  'VICENZA', 'IGUATEMI', 'SHOPPING', 'CENTAURO', 'NETSHOES'],
    'Casa/Móveis': ['LEROY', 'MADEIRA', 'AMAZON', 'MERCADOLIVRE', 'VIVARA',
                    'PETLOVE', 'COBASI', 'PETZ', 'SHOPEE', 'ALIEXPRESS', 'SHEIN', 'CASAS BAHIA',
                    'MAGAZINE LUIZA', 'MAGALU'],
    'Serviços Pessoais': ['BARBEARIA', 'BARBER', 'ESTETICA', 'SALAO', 'ACADEMIA',
                          'TRUSS', 'BOX688', 'SMARTFIT', 'GYMPASS', 'TOTALPASS'],
    'Educação/Profissional': ['NELOGICA', 'CONTAB', 'CURSO', 'UDEMY', 'COURSERA',
                              'LIVRAR', 'HUBLA', 'SMARTTBOT', 'QUANTUM', 'AUGMENT',
                              'IUGU', 'HOTMART', 'EDUZZ', 'KIWIFY'],
    'Lazer': ['STEAM', 'PLAYSTATION', 'XBOX', 'NUUVEM', 'CINEMA', 'TEATRO',
              'EVENTO', 'CINEMARK', 'INGRESSO'],
    'Empresarial': ['LGELECTRONICS', 'FORNECEDOR', 'EQUIPAMENTO'],
    'Outros': ['PRUDENT', 'SEGURO', 'ANUIDADE', 'TARIFA', 'IPTU', 'SIMERS']
}

def create_directories():
    """Cria diretórios necessários se não existirem"""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(BACKUP_FOLDER, exist_ok=True)
