# API Manager — Multi-tenant ERP API Gateway

Gerenciador de API multi-tenant para Firebird ERP com chat IA inteligente, enriquecimento semântico de schema e exposição dinâmica de endpoints REST.

**Principais características:**
- 🏗️ Arquitetura 3-tier com isolamento de tenant (public / client / admin)
- 🤖 Chat IA com retroalimentação — reaprender de queries validadas
- 🧠 Enriquecimento semântico de schema (purpose, joins, filters, columns)
- 🔀 Mapeamento dinâmico com OmniRoute para roteamento inteligente
- 📊 Dashboard admin completo — clientes, chaves, métricas, conectores
- 🔐 Autenticação multi-camada: admin session + API keys com escopos
- 📁 Endpoints REST automáticos para tabelas expostas do Firebird

---

## 🚀 Quick Start

### Requisitos
- Python 3.11+
- Firebird 4.0+ (credenciais configuradas)
- pip / venv

### Setup Local

```bash
# 1. Clone e entre no diretório
git clone https://github.com/cristhianschug/API-manager.git
cd API-manager

# 2. Crie ambiente virtual
python -m venv venv
source venv/bin/activate  # ou: venv\Scripts\activate (Windows)

# 3. Instale dependências
pip install -r requirements.txt

# 4. Configure variáveis de ambiente
cp .env.example .env
# Edite .env com suas credenciais Firebird e chaves de API
nano .env

# 5. Inicie o servidor
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 6. Acesse
# - Documentação: http://localhost:8000/docs
# - Admin Dashboard: http://localhost:8000/admin
```

### Docker Compose

```bash
docker-compose up -d
# Logs: docker logs -f api-manager
# Parar: docker-compose down
```

---

## 🏛️ Arquitetura

```
┌─────────────────────────────────────────────────┐
│           Admin Dashboard (UI)                  │
│  • Gerenciar clientes, API keys, conectores    │
│  • Enriquecer schema com IA                    │
│  • Ver métricas e logs                         │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│      FastAPI Application (main.py)              │
├─────────────────────────────────────────────────┤
│ • /docs (Swagger)        — Documentação        │
│ • /admin/api/*           — Admin routes        │
│ • /api/v1/data/{slug}    — Endpoints dinâmicos │
│ • /api/v1/ai/chat        — Chat IA             │
│ • /api/v1/openapi/*      — OpenAPI specs       │
└─────────────────────────────────────────────────┘
         ↓              ↓            ↓
    ┌────────┐  ┌──────────┐  ┌─────────────┐
    │ IA     │  │ Firebird │  │ SQLite      │
    │Provider│  │ (ERP)    │  │ (Platform)  │
    └────────┘  └──────────┘  └─────────────┘
```

**3 Camadas de OpenAPI Specs:**
1. **Public** (`/openapi.json`) — Sem rotas internas, schemas públicos apenas
2. **Client** (`/api/v1/openapi/{slug}`) — Respeitando API key scopes
3. **Admin** (`/admin/api/openapi`) — Acesso total + gerenciador

---

## 🤖 AI Chat com Retroalimentação

O chat IA aprende com suas queries validadas:

### Como funciona
1. Usuário faz pergunta: *"Faturamento total do mês?"*
2. IA gera plano de consulta (endpoints + params)
3. Backend executa e retorna dados
4. Admin valida a lição → salva para reuso futuro

### Endpoints
- `POST /admin/api/ai/chat` — Fazer pergunta (opera como uma API key)
- `GET /admin/api/ai-memory` — Listar lições aprendidas (pendentes/validadas)
- `PATCH /admin/api/ai-memory/{id}` — Validar ou rejeitar lição

### Contexto Semântico
- `POST /admin/api/clients/{client_id}/schema/enrich` — Gerar draft do contexto via IA
- `GET /admin/api/clients/{client_id}/schema/context` — Ler contexto salvo
- `PUT /admin/api/clients/{client_id}/schema/context` — Salvar contexto validado

O contexto injeta na IA: `purpose` (descrição da tabela), `joins` (FK mapeadas), `filters` (valores enum), `columns` (descrições).

---

## 📊 Admin Dashboard

Acesse em `http://localhost:8000/admin` após login.

### Seções
- **Clientes** — Criar, editar, mapear credenciais Firebird
- **Endpoints Automáticos** — Expor tabelas como REST endpoints
- **API Keys** — Gerar chaves com escopos granulares
- **Chat IA** — Conversa com queries validadas
- **Conectores** — Bindings male/female para integrações
- **Auditoria** — Logs de ações admin
- **Métricas** — Uso de endpoints, latência, erros

---

## 🧪 Testes

```bash
# Rodar todos os testes
pytest

# Com verbose output
pytest -v

# Teste específico
pytest tests/test_schema_enrich.py::test_put_saves_context

# Com cobertura
pytest --cov=. --cov-report=html
# Abrir: htmlcov/index.html
```

### Suites Principais
- `test_docs.py` — Isolamento de specs (public/client/admin)
- `test_ai_memory.py` — Captura/validação de lições
- `test_schema_enrich.py` — Enriquecimento de contexto
- `test_security_hardening.py` — Proteção contra ataques

---

## 🔐 Segurança

### Multi-tenant Isolation
- Cada `client_id` tem credenciais separadas + encrypted storage
- API keys são scoped por recurso (dyn:TABLE, /api/v1/pedidos, etc)
- Admin session requer JWT + cookie

### Validação de Entrada
- Identificadores SQL (IDENT_RE): `^[a-zA-Z_][a-zA-Z0-9_]*$`
- Slugs: `^[a-z0-9_-]+$`
- Nenhum SQL dinâmico — queries parameterizadas

### Headers de Segurança
- `Content-Security-Policy` — Bloqueia inline scripts
- `X-Content-Type-Options: nosniff` — Força MIME type
- `X-Frame-Options: DENY` — Nega clickjacking

---

## 🔧 Variáveis de Ambiente

```bash
# Database
PLATFORM_DB_PATH=./platform.db
PLATFORM_ENCRYPTION_KEY=<gere com: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">

# Admin
JWT_SECRET_KEY=seu-secret-aqui
ADMIN_BOOTSTRAP_PASSWORD=senha-inicial

# AI Provider (OpenAI-compatible)
AI_BASE_URL=http://localhost:20128/v1  # OmniRoute local
AI_API_KEY=sua-chave-opcional
AI_MODEL=auto  # ou gpt-4, claude-3.5-sonnet, etc

# Server
LOG_LEVEL=INFO
```

---

## 📝 API Exemplos

### Health Check
```bash
curl http://localhost:8000/api/v1/health
```

### Listar Clientes (com admin session)
```bash
curl -H "Cookie: admin_token=SEU_TOKEN" \
  http://localhost:8000/admin/api/clients
```

### Criar API Key
```bash
curl -X POST \
  -H "Cookie: admin_token=SEU_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "mobile-app",
    "scopes": {"*": {"read": true}},
    "expires_in_days": 90
  }' \
  http://localhost:8000/admin/api/clients/1/api-keys
```

### Chat IA
```bash
curl -X POST \
  -H "Cookie: admin_token=SEU_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "api_key_id": 1,
    "query": "Faturamento total do mês?",
    "history": []
  }' \
  http://localhost:8000/admin/api/ai/chat
```

### Enriquecer Schema
```bash
curl -X POST \
  -H "Cookie: admin_token=SEU_TOKEN" \
  http://localhost:8000/admin/api/clients/1/schema/enrich
```

---

## 📚 Documentação

- **OpenAPI/Swagger:** `/docs` (documentação interativa)
- **Decisões arquiteturais:** `docs/decisions/ADR-*.md`
- **Deployment:** `docs/DEPLOY.md`
- **Security:** `docs/SECURITY.md`

---

## 🤝 Contribuindo

1. Clone o repositório
2. Crie branch: `git checkout -b feature/sua-feature`
3. Commit: `git commit -m "feat: descrição"`
4. Push: `git push origin feature/sua-feature`
5. Abra PR para `master`

**Antes de submeter:**
- `pytest` — Todos os testes passam
- `pylint` — Sem warnings críticos
- `.env.local` — Não commitar credenciais

---

## 📜 Licença

Proprietário — Anexar ERP

---

## 🆘 Suporte

- **Issues:** GitHub Issues
- **Docs:** `docs/` directory
- **Logs:** `docker logs -f api-manager`

---

**Última atualização:** 2026-09-21  
**Versão:** 1.0 (Semantic Context Enrichment)
