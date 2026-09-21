# ADR-008: Defesa contra SQL injection em queries dinâmicas

## Status
Aceito

## Data
2026-09

## Contexto

A plataforma executa SQL construído dinamicamente em três lugares:

1. **Endpoints dinâmicos** (`dynamic_router.py`) — `table_name` e colunas vêm do banco de controle; `limit`/`offset` vêm do request
2. **Chat AI** (`admin_routes.py`) — SQL gerado pela IA
3. **Enriquecimento de schema** (`admin_routes.py._sample_tables`) — `table_name` do snapshot

O Firebird não suporta bind params em `FIRST`/`SKIP` nem em nomes de tabela/coluna — só em valores de WHERE.

## Decisão

**Identificadores (tabela, coluna):** validação por regex antes de qualquer interpolação.

```python
_IDENT_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
```

Aplicado em `dynamic_router.py` para `col_select` (colunas configuradas), e em `admin_routes.py` para validar colunas no momento da exposição de tabela.

**FIRST/SKIP:** inteiros literais na f-string (não `?`).

```python
# ERRADO — Firebird rejeita bind params nessa posição:
cur.execute("SELECT FIRST ? SKIP ? * FROM {tbl}", (limit, offset))

# CORRETO:
cur.execute(f"SELECT FIRST {limit} SKIP {offset} * FROM {tbl}")
```

`limit` e `offset` são `int` validados pelo FastAPI via `Query(ge=1, le=500)` e `Query(ge=0)` — injeção impossível.

**SQL gerado por IA:** validação pré-execução:
- Deve começar com `SELECT` (regex)
- Não deve conter `;` fora de strings literais (regex strip `'[^']*'` antes da checagem)
- Apenas `SELECT` — nunca `INSERT`, `UPDATE`, `DELETE`, `DROP`

**Credenciais do admin:** parâmetros admin de connector têm prioridade absoluta sobre o body do tenant — tenant não pode injetar parâmetros que sobrescrevam filtros configurados pelo admin.

## Por que não ORM

O Firebird não tem ORM maduro para Python. `firebirdsql` é o driver mais estável; SQLAlchemy com Firebird tem suporte limitado e bugs conhecidos com FIRST/SKIP. A validação de identificadores + parâmetros tipados é a alternativa segura.

## Consequências

- `_IDENT_RE` rejeita nomes com espaço, hífen, ou caracteres especiais — válido para Firebird (identificadores seguem a mesma regra)
- Palavras reservadas do Firebird passam no regex mas falham na execução SQL (silenciosamente no enriquecimento, com exceção nos endpoints — ver ADR-007)
- Qualquer nova rota que interpole identificadores Firebird deve usar `_IDENT_RE` — convenção estabelecida no código
