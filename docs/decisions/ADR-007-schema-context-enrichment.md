# ADR-007: Enriquecimento semântico de schema via IA (schema_context)

## Status
Aceito

## Data
2026-09

## Contexto

O chat AI original gerava SQL a partir de listas cruas de colunas (`RDB$RELATION_FIELDS` do Firebird) buscadas a cada request. Problemas:

- IA inventava nomes de colunas (alucinação) por falta de semântica
- JOINs incorretos por ausência de mapeamento de FKs
- Filtragem errada de enums (valores possíveis desconhecidos)
- 3 chamadas de IA por request (gera → falha → corrige → gera narrativa)

## Decisão

**`schema_context`**: JSON persistido em `platform.db` por `client_id` com estrutura:

```json
{
  "CONTRATOS": {
    "purpose": "Contratos firmados com clientes",
    "joins": { "CODCLIENTE": "CLIENTES.CODCLIENTE" },
    "filters": { "SISTEMA": ["ANEXAR", "MASTER"] },
    "columns": { "DTINICIO": "Data de início do contrato" }
  }
}
```

**Geração** (`POST /admin/api/clients/{id}/schema/enrich`):
1. Para cada tabela do snapshot: `SELECT FIRST 5 * FROM {tabela}` no Firebird
2. Agrupa 10 tabelas por chamada de IA
3. IA infere `purpose`, `joins` (FKs implícitas), `filters` (enums), `columns` (labels não óbvios)
4. Retorna draft — admin revisa e confirma via `PUT /admin/api/clients/{id}/schema/context`

**Uso no chat**:
- Se `schema_context` existe: injeta o JSON como contexto no prompt, sem tocar no Firebird
- Se não existe: fallback para `_get_tbl_cols` (cache 30min em `_col_cache`)

## Caches em memória (todos por processo)

| Cache | TTL | Chave | Dado |
|-------|-----|-------|------|
| `_creds_cache` | 5 min | `client_id` | credenciais Firebird descriptografadas |
| `_col_cache` | 30 min | `client_id` | `{tabela: [colunas]}` do Firebird |
| `_table_cache` | 30s | `client_id` | lista de `exposed_tables` ativas |
| `_openapi_cache` | 60s | (global) | schema OpenAPI completo |

## Consequências

- `schema_context` precisa ser regenerado quando o schema Firebird muda (nova coluna, nova tabela)
- Tabelas com nomes de palavras reservadas Firebird (`ORDER`, `VALUE`) falham silenciosamente no enriquecimento — `SELECT FIRST 5 * FROM ORDER` é SQL inválido; o `except` armazena `{columns:[], rows:[]}` e a IA recebe contexto vazio para essa tabela
  - **Workaround**: renomear a tabela, ou adicionar quoting (`"ORDER"`) no `_sample_tables` — pendente
- O campo `joins` é o mais crítico para queries multi-tabela; sem ele, a IA não sabe como fazer JOINs corretos
- Enriquecimento é uma operação admin pontual (não em tempo real), portanto conexões Firebird sequenciais são aceitáveis
