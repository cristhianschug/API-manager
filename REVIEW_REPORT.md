# API Anexar — Relatório de Revisão Multi-Skill

> Gerado em 2026-09-16 | Skills: code-review-and-quality, security-and-hardening, frontend-ui-engineering, ci-cd-and-automation, observability-and-instrumentation, debugging-and-error-recovery, code-simplification, performance-optimization

---

## Sumário Executivo

| Dimensão | Críticos | Altos | Médios | Status |
|---|---|---|---|---|
| Segurança | 3 | 4 | 6 | 🔴 Bloqueador |
| Infra / CI-CD | 3 | 6 | 5 | 🔴 Bloqueador |
| Qualidade de Código | 4 | 6 | 6 | 🟠 Urgente |
| Observabilidade | 5 | 6 | 5 | 🟠 Urgente |
| Frontend / UI | 4 | 8 | 7 | 🟠 Urgente |

---

## 🔴 CRÍTICO — Deve corrigir antes de qualquer deploy

### SEC-1 · Credenciais reais no docker-compose.yml (commitadas no git)
**[docker-compose.yml:11-15]**  
IP, usuário e senha do banco Firebird em texto claro em arquivo rastreado pelo git.  
**Fix imediato:** Rotacionar as credenciais. Mover para `.env` referenciado por `env_file: .env` no compose.

### SEC-2 · `main_security.py` — API sem autenticação no repositório
**[main_security.py:76-83]**  
`get_current_tenant()` usa só `X-Tenant-ID` header sem verificação nenhuma. É uma app FastAPI completa que pode ser ativada com `uvicorn main_security:app`. Acessa dados de qualquer tenant com um simples header.  
**Fix:** Deletar o arquivo. As primitivas de segurança já estão em `tenant_auth.py`.

### SEC-3 · JWT secret com fallback público permite forjar tokens admin
**[admin_routes.py:21]**  
`JWT_SECRET = os.getenv('JWT_SECRET_KEY', 'dev-secret-change-in-prod')` — qualquer pessoa pode criar um token admin válido com a chave pública.  
**Fix:** `JWT_SECRET = os.environ["JWT_SECRET_KEY"]` — falha no startup se ausente.

### INFRA-1 · `docker-compose.prod.yml` não existe — deploys quebrados
**[.github/workflows/ci-cd.yml:102-103]**  
CI executa `docker-compose -f docker-compose.prod.yml down/up` mas o arquivo não existe. Todo push para `main` falha no step de deploy.  
**Fix:** Criar `docker-compose.prod.yml` conforme documentado em `DEPLOYMENT_SAFETY.md`.

### INFRA-2 · Sem `.dockerignore` — `.env.local` pode vazar na imagem Docker
**[Dockerfile]**  
`COPY . .` sem `.dockerignore` inclui `.env.local` na imagem. Se a imagem for pushed para Docker Hub, secrets se tornam públicos.  
**Fix:** Criar `.dockerignore` que espelha `.gitignore`.

### CODE-1 · `FileResponse(content=...)` — crash em runtime
**[admin_routes.py:353]**  
`FileResponse` não aceita parâmetro `content=`. Esse endpoint lança `TypeError` em toda chamada.  
**Fix:** Usar `Response(content=json.dumps(...), media_type="application/json")`.

### CODE-2 · Fernet key aleatória se env var ausente — dados irrecuperáveis
**[security.py:118]**  
`Fernet(os.getenv('ENCRYPTION_KEY', Fernet.generate_key()))` — nova chave aleatória por restart. Todos os dados encriptados da sessão anterior ficam ilegíveis.  
**Fix:** `Fernet(os.environ["ENCRYPTION_KEY"])` — sem fallback.

### OBS-1 · Zero cobertura de testes no código atual
**[conftest.py, test_endpoints.py]**  
`conftest.py` importa `from database import Base, get_db` e instancia modelos SQLAlchemy que não existem na arquitetura v2. Os testes não podem nem importar. "19/19 passing" em `DEBUG_LOG.md` é da arquitetura v1 abandonada.  
**Fix:** Reescrever `conftest.py` mockando `get_tenant_context` com um `TenantContext` fake.

### FRONT-1 · XSS via innerHTML em ambos os dashboards
**[admin_dashboard.html:624, dashboard.html:434-557]**  
Template literals com dados da API inseridos via `innerHTML` sem sanitização. Um nome de cliente como `<img src=x onerror=alert(1)>` executa JavaScript no contexto admin.  
**Fix:** Usar `.textContent` por célula ou uma função `sanitize()` em vez de `innerHTML`.

### FRONT-2 · `response.ok` não verificado antes de `.json()`
**[dashboard.html:432, 461, 491, 519, 543]**  
`await response.json()` chamado incondicionalmente. Um 401 por chave expirada silencia a falha de autenticação.  
**Fix:** `if (!response.ok) throw new Error(\`HTTP \${response.status}\`)`

---

## 🟠 ALTO — Corrigir na próxima sprint

### Segurança
- **[admin_routes.py:21]** Senha admin padrão `changeme123` se env var ausente — usar `os.environ["ADMIN_BOOTSTRAP_PASSWORD"]`
- **[platform_repository.py:89]** Senha Firebird decriptada retornada na resposta de `GET /admin/api/clients/{id}` — remover `db_password` do dict retornado
- **[tenant_auth.py:63]** Exception do Firebird expõe hostname/porta/path nos detalhes do 503 — retornar mensagem genérica
- **[main.py, admin_routes.py]** Sem rate limiting em nenhum endpoint — nem no login admin

### Infra/CI-CD
- **[requirements.txt]** Todas dependências com `>=`, sem pins — builds não-reproduzíveis (`pip freeze > requirements.txt`)
- **[ci-cd.yml:~95]** Deploy rebuilda imagem no servidor em vez de fazer `docker pull` da imagem que passou nos testes
- **[ci-cd.yml]** Sem rollback — se deploy falhar, serviço fica down
- **[ci-cd.yml]** `safety` e `pip-audit` estão em `requirements.txt` mas nunca invocados no CI
- **[ci-cd.yml]** Actions desatualizadas: `actions/checkout@v3` → `@v4`, etc.

### Qualidade de Código
- **[main.py:46-52]** `allow_origins=["*"]` + `allow_credentials=True` — browsers rejeitam isso; usar origens explícitas
- **[tenant_auth.py:54-68]** Conexão Firebird nunca fechada por request — sem `try/yield/finally conn.close()`
- **[main.py — 12 locais]** `str(e)` como HTTP detail vaza SQL e nomes de tabelas — retornar mensagem genérica
- **[main_security.py]** App duplicada com rotas sem auth — deve ser deletada
- **[security.py:104]** `RowLevelSecurity.apply_tenant_filter` referencia `models.Tbcliente` mas `models` não é importado — `NameError` em runtime
- **[ai_routes.py:116]** URL OmniRoute hardcoded no endpoint `/status` em vez de ler `OMNIROUTE_BASE_URL`

### Observabilidade
- **[request_logging.py:19-20]** `request.state.tenant_context` nunca é escrito — toda linha de log tem `client_id=NULL` e `api_key_id=NULL`
- **[main.py, database.py, platform_db.py]** `print()` em vez de logger estruturado — sem níveis, sem timestamps, sem filtro
- **[main.py — 12 locais]** Exceções relançadas como 500 sem logar traceback — debug por `str(e)` apenas
- **[/api/v1/health]** Retorna 200 mesmo com banco inacessível — health check sem live check
- **[tenant_auth.py:66-74]** `asyncio.get_event_loop()` em contexto async — deprecado no Python 3.10+, falha no 3.12+

### Frontend
- **[admin_dashboard.html]** Tabs sem `role="tablist"`, `aria-selected`, `aria-controls` — inacessível para leitores de tela
- **[admin_dashboard.html:524-538]** Modal sem `role="dialog"`, sem trap de foco, sem handler de `Escape`
- **[dashboard.html:445-561]** Valores de métricas hardcoded (`'3.013'`, `'53'`) — nunca refletem dados reais
- **[admin_dashboard.html:964]** `showLoginScreen(true)` chamado incondicionalmente no init — sem verificação de sessão ativa

---

## 🟡 MÉDIO / Melhorias

### Segurança
- Sem limite de tamanho no body da request — DoS por payload grande
- `security.py:277` — `except:` nu captura `KeyboardInterrupt`/`SystemExit`
- `security.py:338-349` — Bloqueio por User-Agent (`curl`, `wget`) — fácil de contornar e quebra integrações legítimas
- `database.py` — Teste de conexão no nível de módulo mata o processo em falha de rede transitória

### Infra
- Sem `.env.example` — desenvolvedor novo começa sem saber quais vars configurar
- Sem Dependabot configurado
- `sleep 5` no health check pós-deploy — frágil; usar loop de retry

### Qualidade de Código
- `ini_parser.py:57-63` — `except ValueError` recaptura ValueError do bloco try, duplicando a mensagem de erro
- `omniroute_client.py:33-48` — `max_tokens + 500` silencioso nos helpers — comportamento inesperado para chamadores
- `admin_routes.py:79` — Header `Set-Cookie` construído manualmente em vez de `response.set_cookie()`

### Observabilidade
- Sem `/metrics` endpoint no formato Prometheus — sem integração com alertas
- `database.py` — teste de conexão no módulo impede import por ferramentas sem banco disponível
- README descreve v1 (SQLAlchemy, read-only) não v2 (multi-tenant, Firebird raw)

### Frontend
- 5 funções `loadXxx` idênticas em `dashboard.html` — refatorar para `loadTab(name, url, renderRow)`
- Tabelas sem scroll horizontal em mobile — overflow sem wrapper
- Sem `aria-live` para feedback de status/erro

---

## Pontos Positivos

### Segurança ✅
- Isolamento por tenant é forte por arquitetura: cada chave aponta para uma conexão Firebird dedicada
- Hashing de API keys com SHA-256; argon2 para senhas admin; Fernet para credenciais em repouso
- `require_scope()` aplicado consistentemente em todas as rotas via `Depends()`
- Mascaramento de CPF e email acontece na camada de dados antes dos DTOs
- `.env.local` está no `.gitignore`

### Frontend ✅
- `lang="pt-BR"` correto, viewport meta tag presente
- `Intl.NumberFormat('pt-BR', {currency:'BRL'})` — formatação locale-aware correta
- A API key no modal usa `.textContent` (o único lugar que importa está correto)
- Alerts auto-dismiss com tipos error/success/info

### Infra ✅
- Dockerfile tem `HEALTHCHECK` com `start-period` adequado
- CI gates `build` no `test` via `needs: test`
- Credenciais Docker Hub usam GitHub Secrets (sem plaintext no YAML)
- `DEPLOYMENT_SAFETY.md` é um runbook operacional detalhado

### Qualidade ✅
- Paginação com bounds enforced (`le=500`) em todos os endpoints de lista
- `ini_parser.py` trata UTF-8/Latin-1 fallback corretamente para Windows
- Queries Firebird usam `?` placeholders — sem concatenação SQL
- Fluxo de resolução de tenant é limpo e single-path

---

## Revisor Contínuo — Como Manter

Para que as skills revisem cada commit automaticamente, adicione ao `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash(git commit*)",
        "hooks": [{
          "type": "command",
          "command": "python \".claude/scripts/pre_commit_review.py\""
        }]
      }
    ]
  }
}
```

E crie `.claude/scripts/pre_commit_review.py` com checks rápidos dos itens críticos (sem LLM) para feedback instantâneo no terminal a cada commit.

As skills `code-review-and-quality`, `security-and-hardening` e `ci-cd-and-automation` podem ser invocadas manualmente a qualquer momento para revisão profunda de uma área específica.

---

## Higiene de Código & Performance (`code-simplification` + `performance-optimization`)

### Código morto — deletar com segurança (1.064 linhas)

| Arquivo | Linhas | Motivo |
|---|---|---|
| `security.py` | 607 | Zero importações em produção — `main.py`, `admin_routes.py`, `ai_routes.py`, `tenant_auth.py` não importam nada daqui |
| `main_security.py` | 384 | App FastAPI duplicada com auth sem verificação — nunca usada em produção |
| `models.py` | 73 | SQLAlchemy ORM para Firebird que usa raw cursor; `from database import Base` falha com ImportError |

**Classes em `security.py` 100% sem chamadores:**
`APIKeyManager`, `GitSecretProtection`, `PKIManager`, `RowLevelSecurity`, `SessionCookieSecurity`, `PasswordSecurity`, `QuerySecurity`, `FileUploadSecurity`, `HTTPSEnforcement`, `DependencySecurity`, `SecureLogging`, `add_security_middleware`

### Imports mortos

- **`main.py:5`** — `from fastapi.security import APIKeyHeader` — nunca usado
- **`main.py:11`** — `from database import get_db` — nunca usado em nenhuma rota; também dispara teste de conexão Firebird no startup
- **`admin_routes.py:6`** — `Dict` e `Any` no import de `typing` — nunca usados

### Lógica duplicada

- **`main.py:94-286`** — 10 route handlers com o mesmo padrão `try/except → HTTPException(500)` repetido. Um decorator ou helper de 3 linhas elimina 50+ linhas de repetição
- **`platform_repository.py`** — `list_api_keys` e `get_api_key_by_hash` rodam a mesma query SQL de scopes separadamente. Extrair `_load_scopes(cur, api_key_id)` deduplicaria 12 linhas
- **`platform_repository.py:get_request_metrics`** — 3 queries SQLite separadas com o mesmo `WHERE` → 1 query com `COUNT(CASE WHEN...)` economiza 2 round-trips por chamada de métricas

### Performance (bloqueio do event loop)

- **`tenant_auth.py:54`** — `firebirdsql.connect(...)` síncrono chamado dentro de `async def` — bloqueia o event loop em TODA request. Fix: `await asyncio.to_thread(firebirdsql.connect, ...)`
- **`request_logging.py:41`** — SQLite write síncrono em middleware async. Fix: `asyncio.create_task(asyncio.to_thread(log_request, ...))`
- **`tenant_auth.py:72-75`** — `loop.run_in_executor(None, ...)` sem `await` descarta o Future silenciosamente — key usage nunca é atualizado. Fix: `await asyncio.to_thread(...)`
- **`platform_repository.py:list_api_keys`** — N+1: 1 query por chave para carregar scopes dentro do loop. Fix: `LEFT JOIN api_key_scopes` na query principal

### God files (dividir)

- **`main.py` (345 linhas)** → extrair `routers/clientes.py`, `routers/produtos.py`, etc. — `main.py` fica só com wiring
- **`platform_repository.py` (459 linhas)** → `client_repository.py` + `api_key_repository.py` + `log_repository.py`

### Quick wins (< 10 min cada)

1. Remover `from database import get_db` de `main.py` — elimina crash de startup em env sem DB_HOST
2. Corrigir `FileResponse(content=...)` → `Response(content=...)` em `admin_routes.py:353`
3. Extrair `_load_scopes()` em `platform_repository.py`
4. Corrigir `run_in_executor` sem `await` em `tenant_auth.py:72`
5. Deletar `main_security.py` + `models.py` + `security.py` = -1.064 linhas
