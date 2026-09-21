# ADR-005: Regra de negócio — Endpoints REST para dashboards, Connectors para agentes de IA

## Status
Aceito

## Data
2026-09

## Contexto

A plataforma serve dois perfis de consumo:

1. **Dashboards e BI tools** — ferramentas como Metabase, Power BI, planilhas que consomem dados via HTTP GET de forma direta, paginada, e preferem endpoints com contratos fixos
2. **Agentes de IA e MCP clients** — agentes que precisam de contexto semântico, podem combinar múltiplas queries, e beneficiam de outputs enriquecidos com metadados

Inicialmente ambos usariam endpoints REST. O problema: endpoints REST são genéricos (tabela por tabela), enquanto agentes precisam de queries orientadas a negócio com semântica definida pelo admin.

## Decisão

**Regra de negócio formal:**

| Caso de uso | Mecanismo | Auth |
|-------------|-----------|------|
| Dashboard, Metabase, Power BI, planilha | Endpoint REST dinâmico (`/api/v1/data/{slug}`) | API key |
| Agente de IA, MCP client, automação | Connector (`/api/v1/connectors/{id}/execute`) | API key com escopo de connector |

**Connectors** são templates reutilizáveis com:
- `query_id`: identificador semântico da query (ex: `faturamento-mensal`)
- `route`: rota relativa no ERP externo que o connector chama
- `params`: parâmetros fixos configurados pelo admin (não sobrescrevíveis pelo tenant — ADR-002)
- `instance_name`: permite múltiplos bindings do mesmo connector com configurações diferentes

**Por que connectors, não endpoints, para IA:**
- Agentes precisam de queries com nomes de negócio (`faturamento-mensal`), não slugs de tabela (`NOTAFISCAL`)
- O admin controla quais queries o agente pode executar (escopo `connector:{id}:execute`)
- Connectors podem chamar APIs externas (ERP externo, não só Firebird), abstraindo a fonte
- O sistema de auto-sugestão de bindings usa IA para propor qual query mapeia para qual connector

## Consequências

- Um cliente precisa de dois tipos de configuração: tabelas expostas (dashboards) e connectors (agentes)
- A UI do admin separa claramente: aba "Endpoints" e aba "Connectors"
- Auto-suggest de bindings (`POST /admin/api/connectors/{id}/suggest-bindings`) usa o schema snapshot + IA para propor mapeamentos; o admin revisa e aprova
- Bindings sugeridos têm `status='suggested'`; aprovados têm `status='active'`; apenas `active` são executados pelo tenant
