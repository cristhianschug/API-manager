# ADR-002: Autenticação dual — cookie de sessão (admin) + API key (tenant)

## Status
Aceito

## Data
2026-08

## Contexto

A plataforma tem dois perfis de usuário com necessidades completamente diferentes:

- **Admin**: humano navegando o painel web, precisa de sessão com estado, troca de contexto entre clientes
- **Tenant/API consumer**: serviço ou dashboard consumindo dados programaticamente, precisa de auth stateless

Opções avaliadas:

- **JWT Bearer para tudo** — tokens expiram, exigem refresh, o painel web precisaria de JS extra para gerenciar tokens; mais complexo
- **HTTP Basic** — credenciais em cada request; não adequado para API keys de longa duração
- **OAuth2** — overhead enorme para uma plataforma interna single-tenant de admin
- **Cookie de sessão assinado (admin) + API key (tenant)** — encaixa perfeitamente nos dois perfis

## Decisão

**Admin panel**: cookie HttpOnly assinado com `itsdangerous.TimestampSigner` usando `ADMIN_SESSION_SECRET`. TTL de 8h. `require_admin_session` como `Depends()` em todas as rotas admin.

**Tenant API**: header `X-API-Key` → hash SHA-256 → lookup em `api_keys` → resolve `TenantContext` com escopos. A chave em si nunca é armazenada, apenas o hash.

## Escopos

Formato `recurso:ação`. Recursos suportados:

| Recurso | Ação | Significado |
|---------|------|-------------|
| `*` | `read` | Todas as tabelas expostas |
| `dyn:{TABLE}` | `read` | Tabela específica |
| `connector:{id}` | `execute` | Execução de connector |

Verificação de escopo em `_check_table_scope()` — usa `table_name.upper()` para casar com os nomes armazenados (Firebird é case-insensitive mas armazena em uppercase).

## Consequências

- API keys ficam expostas apenas no momento da criação; após isso apenas o hash existe no banco
- `require_admin_session` como `Depends()` facilita adicionar auth a novos endpoints sem duplicar lógica
- Cookie HttpOnly elimina XSS como vetor de roubo de sessão admin
- Sessão admin não tem revogação granular — um logout invalida somente via expiração ou troca de `ADMIN_SESSION_SECRET`
