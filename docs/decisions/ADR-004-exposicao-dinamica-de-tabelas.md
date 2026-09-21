# ADR-004: Exposição dinâmica de tabelas com slug e Swagger por tabela

## Status
Aceito

## Data
2026-09

## Contexto

O objetivo é que o admin configure quais tabelas do Firebird ficam acessíveis via REST sem redeploy. O desafio é que o FastAPI registra rotas em tempo de startup — não é possível adicionar rotas em runtime sem restart.

Opções avaliadas:

- **Rotas fixas por tabela** — requer restart ao adicionar tabela; não serve
- **Rota catch-all `/api/v1/data/{slug}`** — resolve o problema de roteamento; o slug é mapeado para a tabela no banco; funciona
- **Swagger dinâmico** — a rota catch-all aparece como uma entrada genérica no Swagger; não documenta cada tabela individualmente

## Decisão

**Rota:** `GET /api/v1/data/{slug}` e `GET /api/v1/data/{slug}/{pk_id}` em `dynamic_router.py`. O `slug` é resolvido contra `exposed_tables` no SQLite.

**Swagger:** `app.openapi` é substituído por uma função customizada que injeta entradas individuais por tabela exposta no schema OpenAPI. Cache de 60s (`_openapi_cache`) evita rebuild em cada load do Swagger.

**Segurança SQL:** nomes de colunas e tabelas são validados contra `_IDENT_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')` antes de interpolação. FIRST/SKIP usam inteiros literais (não `?`) porque o Firebird não aceita bind params nessa posição.

**Seleção de colunas:** o admin pode marcar quais colunas expor por tabela. Se nenhuma for marcada, `SELECT *` é usado. Colunas selecionadas são validadas contra `_IDENT_RE` no momento da query (mesmo que o valor armazenado seja válido — defesa em profundidade).

## Slug e unicidade

- `slug` é único por `(client_id, slug)` — índice único no SQLite
- `table_name` é armazenado em uppercase (`table_name.upper()`)
- Escopos de API key seguem o mesmo uppercase: `dyn:CLIENTES`

## Consequências

- Admin vê a tabela no Swagger em até 60s após ativação
- Cache do Swagger é por processo — em multi-worker, cada worker tem cache independente
- Tabelas com nomes de palavras reservadas do Firebird funcionam normalmente nos endpoints (o nome é validado por `_IDENT_RE`, não por lista negra); o risco é no enriquecimento de schema (`_sample_tables`), que usa `SELECT FIRST 5 * FROM {tbl}` sem aspas — palavras reservadas lá falham silenciosamente (ver ADR-007)
