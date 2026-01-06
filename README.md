# Dashboard Financeiro Pessoal

Sistema web local para controle e análise de gastos pessoais.

## 🚀 Fase 1 - Core do Sistema (VERSÃO ATUAL)

Esta é a primeira versão funcional com:
- ✅ Upload de faturas C6 Bank (ZIP com senha)
- ✅ Processamento automático de CSV
- ✅ Categorização automática de transações
- ✅ Dashboard básico com resumo mensal
- ✅ Tabela de gastos por categoria
- ✅ Autenticação com senha

## 📋 Pré-requisitos

- Python 3.10 ou superior
- Navegador moderno (Chrome, Firefox, Edge)
- 500MB de espaço em disco

## 🔧 Instalação

### 1. Verificar Python

```bash
python --version
# Deve mostrar: Python 3.10.x ou superior
```

Se não tiver Python instalado:
- Windows: https://python.org/downloads/
- Mac: `brew install python`
- Linux: Já vem instalado

### 2. Extrair o projeto

Extraia a pasta `financial-dashboard` para um local de sua preferência.

### 3. Abrir terminal na pasta do projeto

Windows:
- Abra a pasta no Explorer
- Clique com botão direito e escolha "Abrir no Terminal" ou "Prompt de Comando"

Mac/Linux:
- Abra o Terminal
- Digite: `cd /caminho/para/financial-dashboard`

### 4. Criar ambiente virtual

```bash
python -m venv venv
```

### 5. Ativar ambiente virtual

Windows:
```bash
venv\Scripts\activate
```

Mac/Linux:
```bash
source venv/bin/activate
```

Você verá `(venv)` no início da linha do terminal.

### 6. Instalar dependências

```bash
pip install -r requirements.txt
```

Aguarde a instalação (pode levar 2-3 minutos).

### 7. Inicializar banco de dados

```bash
python database/db.py
```

Você verá: ✓ Banco de dados inicializado com sucesso!

## ▶️ Executar o Sistema

```bash
python app.py
```

Você verá:
```
============================================================
Dashboard Financeiro Pessoal
============================================================
Acesse: http://localhost:5000
Senha padrão: admin123
============================================================
```

## 🌐 Acessar o Dashboard

1. Abra seu navegador
2. Digite: `http://localhost:5000`
3. Entre com a senha: `admin123`

## 📤 Fazer Upload de Faturas

1. Clique em "Upload" no menu
2. Selecione ou arraste seus arquivos ZIP (C6 Bank)
3. Clique em "Processar Arquivos"
4. Aguarde o processamento
5. Volte ao Dashboard para ver os dados

**Senha dos ZIPs:** O sistema usa automaticamente a senha `399838` configurada.

## 📁 Estrutura do Projeto

```
financial-dashboard/
├── app.py                  # Aplicação Flask principal
├── config.py               # Configurações
├── requirements.txt        # Dependências
├── database/
│   ├── db.py              # Gerenciamento do banco
│   └── finance.db         # SQLite (criado automaticamente)
├── processors/
│   ├── upload_handler.py  # Processamento de uploads
│   ├── csv_parser.py      # Parser CSV C6 Bank
│   └── categorizer.py     # Categorização automática
├── static/
│   ├── css/style.css      # Estilos
│   └── js/main.js         # JavaScript
├── templates/
│   ├── base.html          # Template base
│   ├── login.html         # Página de login
│   ├── dashboard.html     # Dashboard principal
│   ├── upload.html        # Página de upload
│   └── metas.html         # Metas (em desenvolvimento)
├── uploads/               # Arquivos temporários
└── backups/               # Backups do banco
```

## 🐛 Resolução de Problemas

### Erro: "python não é reconhecido"

**Solução:**
- Windows: Reinstale Python marcando "Add Python to PATH"
- Mac/Linux: Use `python3` ao invés de `python`

### Erro: "No module named 'flask'"

**Solução:**
```bash
# Certifique-se de estar com venv ativado
pip install -r requirements.txt
```

### Erro: "Address already in use"

**Solução:** Porta 5000 já está sendo usada. Mate o processo ou use outra porta:
```bash
python app.py --port 5001
```

### Erro ao processar ZIP: "Senha incorreta"

**Solução:** Verifique se a senha do ZIP é realmente `399838`. Se for diferente:
1. Abra `config.py`
2. Altere a linha: `ZIP_PASSWORD = '399838'`
3. Salve e reinicie o sistema

### Dashboard vazio após upload

**Solução:**
1. Verifique se o upload foi bem-sucedido (mensagem verde)
2. Verifique se o mês está selecionado no dropdown
3. Veja no terminal se há erros

## 🔐 Segurança

### Trocar a senha de acesso

Por enquanto, a senha está hardcoded como `admin123`.

**Para trocar:**
1. Gere um novo hash bcrypt da sua senha
2. Atualize no banco de dados

Implementaremos interface para trocar senha nas próximas sessões.

## 📊 Categorização Automática

O sistema categoriza automaticamente suas transações baseado em:

**Palavras-chave configuradas:**
- IFOOD, UBER EATS → Alimentação (Delivery)
- ZAFFARI, CARREFOUR → Alimentação (Supermercado)
- UBER, 99APP → Transporte
- NETFLIX, SPOTIFY → Streaming
- E muitos outros...

**Para ajustar:**
- Edite o arquivo `config.py`
- Seção `KEYWORDS_CATEGORIAS`
- Adicione suas próprias palavras-chave

## 🎯 Próximas Implementações

**Sessão 2:**
- Gráficos interativos (Barras, Pizza)
- Comparativo visual mês a mês
- Subcategorias expansíveis

**Sessão 3:**
- Detecção de gastos recorrentes
- Sistema de alertas
- Filtros avançados

**Sessão 4:**
- Página de metas funcionando
- Gauge de progresso
- Mais gráficos (Linha, Sankey)

## 📝 Notas

- Todos os dados ficam no seu computador (arquivo SQLite local)
- Nenhuma informação é enviada para internet
- Backups automáticos (próxima versão)
- Histórico limitado a 2 anos (configurável)

## 🆘 Suporte

Se encontrar problemas:
1. Veja a seção "Resolução de Problemas" acima
2. Verifique mensagens de erro no terminal
3. Reporte o erro com detalhes na próxima sessão

## 📄 Licença

Uso pessoal. Código fornecido "como está".

---

**Versão:** 1.0 - Fase 1 (Core)
**Data:** Dezembro 2025
**Status:** ✅ Funcional para testes
