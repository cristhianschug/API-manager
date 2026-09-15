# API Architecture

Status: DRAFT

## Request flow

`Client → Gateway → Authentication → Tenant Resolver → Authorization → Rate/Concurrency Limits → Service → Repository → Tenant Firebird`

## Design rules

- stateless application layer;
- horizontal scalability;
- DTO-based responses;
- explicit field selection;
- pagination;
- bounded filters;
- query timeouts;
- structured errors;
- request IDs;
- observability.

## No SELECT *

Public endpoints must select explicit fields.
