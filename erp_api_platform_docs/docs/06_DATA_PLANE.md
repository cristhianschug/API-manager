# Data Plane

Status: DRAFT

## Components

- gateway/reverse proxy
- authentication
- tenant resolver
- authorization
- rate limiting
- concurrency limiting
- connection manager
- repository layer
- service layer
- DTO layer
- OpenAPI

## Statelessness

Application instances should be stateless so they can scale horizontally.

Tenant configuration may be cached, but cache correctness must preserve isolation.
