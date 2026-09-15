# Security Architecture

Status: DRAFT

## Security priority

`CORREÇÃO → SEGURANÇA → ISOLAMENTO → OBSERVABILIDADE → PERFORMANCE → ESCALA`

## Mandatory controls

- authentication;
- authorization;
- tenant isolation;
- API key protection;
- secret management;
- input validation;
- output filtering;
- rate limiting;
- concurrency limiting;
- timeout controls;
- audit logging;
- request IDs;
- structured errors;
- security testing.

## Prohibited

- arbitrary SQL;
- database path supplied by client;
- Firebird credentials supplied by client;
- SYSDBA runtime access;
- cross-tenant identifiers trusted from client;
- stack traces in responses;
- secrets in logs;
- unrestricted CRUD.
