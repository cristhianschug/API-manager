# Project Vision

Status: DRAFT  
Version: 0.1.0

## 1. Objective

Build a secure, scalable, documented API platform that exposes controlled ERP capabilities without exposing Firebird databases directly to external consumers.

The platform must support multiple tenants, where each tenant has an isolated Firebird database and its own database credentials.

## 2. Core principles

1. Tenant isolation is non-negotiable.
2. ERP business rules must be understood before writes are exposed.
3. The public API must be independent from the internal database schema.
4. Unknown or ambiguous database behavior must not be published automatically.
5. Read-only functionality is the initial delivery target.
6. Swagger/OpenAPI is documentation and testing infrastructure, not a security boundary.
7. Secrets must never be exposed in source code, API responses, logs, or documentation.
8. Performance must be measured, not assumed.
9. The Control Plane must not become a mandatory database lookup on every hot-path request.
10. Simplicity must not compromise integrity or security.

## 3. Target architecture

### Control Plane

Responsible for:

- tenants
- database mappings
- API keys
- users
- permissions
- routes
- schema catalog
- configuration
- rate limits
- audit

### Data Plane

Responsible for:

- API gateway
- authentication
- tenant resolution
- authorization
- request validation
- connection management
- repositories
- services
- DTOs
- endpoint execution
- observability

## 4. Initial scope

The first release should provide:

- authenticated API access;
- tenant isolation;
- API key management;
- read-only endpoints;
- pagination;
- filtering through controlled parameters;
- structured errors;
- OpenAPI/Swagger;
- audit and request IDs;
- basic rate/concurrency limiting;
- observability.

## 5. Explicit non-goals

The first release must not provide:

- arbitrary SQL;
- public database credentials;
- public database paths;
- public Firebird ports;
- unrestricted CRUD;
- automatic publication of all tables;
- direct execution of arbitrary procedures;
- cross-tenant querying;
- implicit trust of client-supplied tenant identifiers.

## 6. Success criteria

A request authenticated with Tenant A credentials can access only Tenant A resources.

A request authenticated with Tenant B credentials can access only Tenant B resources.

The same API contract works through Swagger and external clients.

All public fields and endpoints are explicitly approved.
