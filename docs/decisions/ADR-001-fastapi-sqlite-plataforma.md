# ADR-001: FastAPI + SQLite como plataforma de controle

## Status
Aceito

## Data
2026-08

## Contexto

O projeto partiu de uma API FastAPI simples com SQLAlchemy lendo diretamente do Firebird. Para suportar múltiplos clientes com credenciais diferentes, tabelas diferentes e API keys diferentes, precisávamos de um "plano de controle" separado do banco de dados dos clientes.

Opções avaliadas para o banco de controle:

- **PostgreSQL** — requer servidor separado, infra adicional, overhead de ops
- **MySQL** — mesmo problema de PostgreSQL; pesado para uma plataforma de controle local
- **SQLite** — zero infra, arquivo local, perfeito para estado de controle de uma instância

## Decisão

Usar **SQLite** (`platform.db`) como banco exclusivo da plataforma. O Firebird de cada cliente é acessado apenas no plano de dados, por request, com credenciais criptografadas armazenadas no SQLite.

FastAPI foi mantido por já estar em uso e ter suporte excelente a async, Pydantic, e OpenAPI.

## Estrutura

```
platform.db
├── clients                  # cadastro de inquilinos
├── client_credentials       # credenciais Firebird (Fernet)
├── api_keys                 # chaves de acesso (SHA-256)
├── api_key_scopes           # escopos por recurso/ação
├── schema_snapshots         # snapshot de schema Firebird
├── schema_context           # contexto semântico enriquecido por IA
├── exposed_tables           # mapeamento tabela → slug REST
├── connector_definitions    # templates de connectors
├── connector_bindings       # bindings connector ↔ cliente
└── request_logs             # logs de acesso por tenant
```

Migrações são idempotentes: executadas a cada startup com `try/except` em cada `ALTER TABLE` — não há framework de migração.

## Consequências

- SQLite é single-writer; escritas concorrentes são serializadas pelo WAL. Aceitável para volume de controle.
- Thread safety: todas as operações SQLite rodam via `asyncio.to_thread()` para não bloquear o event loop.
- Backup é simples: copiar um arquivo.
- Se escala exigir multi-instância, migrar para PostgreSQL — a camada `platform_repository.py` isola esse acoplamento.
