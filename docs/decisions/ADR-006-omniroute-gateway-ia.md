# ADR-006: OmniRoute como gateway de IA (sem chamadas diretas à Anthropic)

## Status
Aceito

## Data
2026-09

## Contexto

A plataforma usa IA em dois lugares:
1. **Chat admin** (`/admin/api/ai/chat`) — NL → SQL → dados Firebird
2. **Enriquecimento de schema** (`/admin/api/clients/{id}/schema/enrich`) — IA infere semântica de tabelas

Opções para o modelo:
- **Anthropic API direta** — requer chave, billing, rate limits por ambiente
- **OpenAI API** — mesmo problema
- **OmniRoute** (`localhost:20128`) — gateway interno que roteia para múltiplos providers; chave `sk-free` no dev; compatível com OpenAI API format

## Decisão

Usar **OmniRoute** em `http://localhost:20128` com modelo `auto`. A interface é idêntica à OpenAI (`client.chat.completions.create`), então trocar o provider é uma mudança de URL + key.

```python
client = openai.OpenAI(base_url=OMNI_URL, api_key=OMNI_KEY)
```

Configurável via `OMNI_ROUTE_URL` e `OMNI_ROUTE_KEY`.

## Fluxo do Chat AI

```
pergunta NL
    → contexto de schema (schema_context se disponível, senão _get_tbl_cols)
    → prompt com schema + pergunta
    → IA gera SQL SELECT
    → validação: SELECT-only, sem multi-statement (`;` fora de strings)
    → executa no Firebird do cliente
    → se erro: retry com SQL corrigido (regex LIMIT→ROWS para Firebird)
    → IA gera narrativa sobre os dados
    → retorna {answer, data, sql, total}
```

## Validação de SQL

O SQL gerado pela IA é validado antes de executar:
1. Deve começar com `SELECT` (regex)
2. Não deve conter `;` fora de strings literais (regex strip de `'...'` antes da checagem)
3. Se falhar: uma retry com prompt de correção, não três chamadas

## Consequências

- OmniRoute deve estar rodando localmente; sem ele, o chat AI retorna 503
- O modelo `auto` significa que o OmniRoute escolhe o melhor disponível; pode ser inconsistente entre environments
- Para produção, configurar `OMNI_ROUTE_URL` para um endpoint fixo com provider definido
- Contexto semântico (`schema_context`) elimina a necessidade de buscar schema do Firebird em cada request de chat; sem ele, cada chat abre uma conexão Firebird para listar colunas
