# Connection Management

Status: DRAFT

## Requirements

- per-tenant connection isolation;
- bounded pools;
- lazy allocation;
- idle connection expiration;
- maximum connections;
- health checks;
- query timeouts;
- transaction boundaries;
- connection cleanup.

## Anti-patterns

Do not create a permanent huge pool for every tenant.

Do not reuse a connection between tenants.

Do not let a client select connection parameters.
