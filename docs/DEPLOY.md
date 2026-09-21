# Migração para servidor externo — mapa completo

Este documento lista **tudo que precisa ser instalado no servidor** e **tudo que muda no projeto**
ao sair do ambiente local (Windows, `localhost:8002`, OmniRoute) para produção.

---

## 1. O que o projeto precisa para rodar

| Componente | Versão | Observação |
|---|---|---|
| Python | 3.11+ | O projeto roda com 3.14 em dev; imagem Docker usa 3.11-slim |
| Dependências Python | `requirements.txt` | `firebirdsql` é Python puro — **não** precisa de `libfbclient` |
| SQLite | embutido no Python | `platform.db` — plano de controle (clientes, keys, mapeamentos) |
| Acesso de rede aos Firebird dos clientes | porta 3050 (padrão) | O servidor precisa alcançar cada host Firebird cadastrado (VPN, firewall, IP fixo) |
| Provedor de IA | API compatível com OpenAI | Em dev é o OmniRoute local; em produção use OpenAI/Groq/OpenRouter/Azure… (seção 4) |
| Reverse proxy com TLS | nginx / Caddy / Traefik | HTTPS obrigatório — o cookie admin e as API keys trafegam em claro sem ele |

Não é necessário instalar: Node.js (o OmniRoute é opcional), banco externo (Postgres/MySQL), Redis.

---

## 2. Arquivos e dados que DEVEM ser levados

| Item | Por quê | Como |
|---|---|---|
| Código do projeto | — | `git clone` ou cópia da pasta (sem `venv/`, `__pycache__/`, `.env.local`) |
| `platform.db` (+ `platform.db-wal`, `platform.db-shm` se existirem) | Contém clientes, credenciais Firebird cifradas, API keys (hash), tabelas expostas, contexto de schema já enriquecido pela IA | Copie com o servidor **parado**, ou rode `sqlite3 platform.db ".backup backup.db"` |
| `PLATFORM_ENCRYPTION_KEY` | É a chave Fernet que cifra as senhas Firebird e a API key da IA dentro do `platform.db`. **Sem a mesma chave, o banco copiado é inútil** (credenciais ilegíveis) | Copie o valor do `.env.local` atual para o `.env.production` |
| `JWT_SECRET_KEY` | Pode ser **trocado** (só invalida sessões admin abertas) | Gere um novo em produção |

> Se preferir **não** levar o `platform.db`, gere uma `PLATFORM_ENCRYPTION_KEY` nova e recadastre os clientes pelo painel (o mapeamento roda automaticamente no cadastro).

---

## 3. Variáveis de ambiente — o que muda

Crie `.env.production` a partir de `.env.example`:

| Variável | Local (hoje) | Servidor | Motivo |
|---|---|---|---|
| `CORS_ORIGINS` | `http://localhost:8002,...` | `https://api.seudominio.com.br` (e o domínio dos dashboards que chamarão a API pelo navegador) | Navegador rejeita credenciais com origem não listada |
| `JWT_SECRET_KEY` | valor dev | **novo** valor aleatório | Segredo não deve sair do ambiente dev |
| `PLATFORM_ENCRYPTION_KEY` | valor dev | **o mesmo** (se levar o platform.db) | Ver seção 2 |
| `ADMIN_BOOTSTRAP_PASSWORD` | dev | senha forte; só é usada se o `platform.db` não tiver admin | Depois do 1º login, troque em Configurações ou com `scripts/reset_admin_password.py` |
| `AI_BASE_URL` / `AI_API_KEY` / `AI_MODEL` | OmniRoute `localhost:20128` | URL/chave/modelo do provedor real — **ou** deixe vazio e configure pelo painel | Seção 4 |
| `PLATFORM_DB_PATH` | não definido (`./platform.db`) | `/var/lib/anexar/platform.db` (ou volume Docker `/app/data/platform.db`) | Dados fora da pasta do código; facilita backup e atualizações |
| `LOG_LEVEL` | `INFO` | `INFO` (`DEBUG` expõe SQL/estrutura de schema nos logs) | Segurança |
| `DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD` | fallback legado | **remover** — não são usados pela API multi-tenant | Higiene |

---

## 4. Provedor de IA — trocar OmniRoute por uma API real

O código usa **uma única abstração** (`omniroute_client.py`) compatível com a API da OpenAI. Nada muda no código.

Ordem de precedência da configuração:

1. **Painel admin → Configurações → Provedor de IA** (gravado cifrado no `platform.db`) — recomendado em produção
2. Variáveis `AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL`
3. Padrão: OmniRoute local

No painel o fluxo é guiado: **1 · Fornecedor** (lista suspensa) → **2 · API key** → **Autenticar e carregar modelos**
(a plataforma consulta o `/models` do próprio fornecedor com a sua chave) → **3 · Modelo** (lista suspensa) →
**Testar modelo** → **Salvar**. As URLs dos fornecedores ficam no backend (`omniroute_client.AI_PROVIDERS`);
o painel só envia o identificador. A chave de um fornecedor nunca é reaproveitada em outro.

| Fornecedor na lista | URL (registrada no backend) |
|---|---|
| OpenAI | `https://api.openai.com/v1` |
| Groq | `https://api.groq.com/openai/v1` |
| OpenRouter (Claude, GPT, Llama…) | `https://openrouter.ai/api/v1` |
| Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` |
| DeepSeek / Mistral / xAI / Together AI | URLs oficiais de cada um |
| Ollama (servidor próprio) | `OLLAMA_URL` (padrão `http://localhost:11434/v1`) — sem chave |
| OmniRoute (local — desenvolvimento) | `OMNIROUTE_URL` (padrão `http://localhost:20128/v1`) — sem chave, modelo `auto` |
| Outro (URL personalizada) | informada no painel — para Azure OpenAI ou gateway próprio |

Para acrescentar um fornecedor, adicione uma entrada em `AI_PROVIDERS` (precisa expor API compatível com OpenAI).
A alteração salva vale em até 30 s para Chat IA, MCP e mapeamento — sem reiniciar.

Consumo estimado: o mapeamento inicial de um banco faz **1 chamada por 10 tabelas** (~2 000 tokens de saída cada). Um ERP com 700 tabelas ≈ 70 chamadas. Cada pergunta no chat/MCP ≈ 2 chamadas (planejamento + narrativa).

---

## 5. Instalação no servidor (Linux, sem Docker)

```bash
# 1. Sistema
sudo apt update && sudo apt install -y python3.11 python3.11-venv git nginx
sudo useradd -r -m -d /opt/anexar anexar

# 2. Código
sudo -u anexar git clone <repo> /opt/anexar/app
cd /opt/anexar/app
sudo -u anexar python3.11 -m venv venv
sudo -u anexar venv/bin/pip install -r requirements.txt

# 3. Dados e configuração
sudo mkdir -p /var/lib/anexar && sudo chown anexar: /var/lib/anexar
# copie platform.db para /var/lib/anexar/ (opcional, ver seção 2)
sudo -u anexar cp .env.example .env.production   # edite conforme seção 3
```

`/etc/systemd/system/anexar-api.service`:

```ini
[Unit]
Description=Anexar ERP API
After=network.target

[Service]
User=anexar
WorkingDirectory=/opt/anexar/app
EnvironmentFile=/opt/anexar/app/.env.production
Environment=PLATFORM_DB_PATH=/var/lib/anexar/platform.db
ExecStart=/opt/anexar/app/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8002 --workers 1 --proxy-headers --forwarded-allow-ips 127.0.0.1
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload && sudo systemctl enable --now anexar-api
curl -s http://127.0.0.1:8002/api/v1/health
```

> **Por que `--workers 1`?** Lockout de login, fila de mapeamento e caches (schema, colunas, respostas de IA) são em memória do processo. Com vários workers eles deixariam de ser consistentes. Para escalar horizontalmente, mova esses três pontos para Redis (todos estão marcados com `# ponytail:` no código).

`/etc/nginx/sites-available/anexar`:

```nginx
server {
    listen 443 ssl http2;
    server_name api.seudominio.com.br;
    ssl_certificate     /etc/letsencrypt/live/api.seudominio.com.br/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.seudominio.com.br/privkey.pem;

    client_max_body_size 5m;          # upload do confrede.ini

    location / {
        proxy_pass http://127.0.0.1:8002;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;   # ativa o header HSTS na API
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
    location /mcp/ {                  # SSE do MCP precisa de streaming sem buffer
        proxy_pass http://127.0.0.1:8002;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_read_timeout 3600s;
    }
}
server { listen 80; server_name api.seudominio.com.br; return 301 https://$host$request_uri; }
```

---

## 6. Instalação com Docker

```bash
cp .env.example .env.production   # edite (seção 3)
docker compose --env-file .env.production up -d --build
docker compose logs -f api
```

O `platform.db` fica no volume `anexar-data`. Para levar o banco atual:

```bash
docker compose up -d --no-start
docker cp platform.db anexar-api:/app/data/platform.db
docker compose up -d
```

Coloque o nginx/Caddy/Traefik com TLS na frente da porta 8002 (mesma config da seção 5).

---

## 7. Checklist pós-deploy

- [ ] `GET https://api.seudominio.com.br/api/v1/health` → 200 e headers `strict-transport-security`, `x-frame-options: DENY`
- [ ] Login no painel `https://api.seudominio.com.br/admin` (senha do bootstrap ou redefinida)
- [ ] Configurações → Provedor de IA → **Testar conexão** → OK; Salvar
- [ ] Clientes → coluna **Mapeamento** = "Mapeado" (ou clique em Sincronizar)
- [ ] Chat IA: escolher cliente + API key → pergunta simples responde citando `via /api/v1/...`
- [ ] Cliente externo: `curl -H "X-API-Key: sk_live_..." https://api.seudominio.com.br/api/v1/data` → lista de tabelas permitidas
- [ ] MCP: seguir `docs/MCP.md` a partir de uma IA externa
- [ ] Backup diário do `platform.db`: `sqlite3 /var/lib/anexar/platform.db ".backup /backup/platform-$(date +%F).db"`
- [ ] Guardar `PLATFORM_ENCRYPTION_KEY` em cofre de segredos (sem ela o backup não serve)

---

## 8. O que continua igual

- Rotas e contratos da API (`/api/v1/*`, `/admin/api/*`, `/mcp/sse`) — nenhum cliente precisa mudar, só o host
- Swagger em `/docs` (público) e por cliente em `/docs/{slug}`
- Estrutura do `platform.db` — migrações são idempotentes e rodam no start (`init_platform_db`)

## 9. Pontos conhecidos a evoluir para alta escala (não bloqueiam o deploy)

| Ponto | Hoje | Quando evoluir |
|---|---|---|
| Lockout de login / caches / fila de mapeamento | memória do processo (`# ponytail:`) | > 1 worker ou > 1 servidor → Redis |
| Pool de conexões Firebird | 1 conexão por request | Firebird Classic saturar conexões → pool por `client_id` |
| Rate limit por API key | ausente (`slowapi` já está no requirements) | primeiro cliente abusivo |
| Hash de API key | SHA-256 puro | migrar para HMAC com segredo do servidor (exige regerar keys) |
