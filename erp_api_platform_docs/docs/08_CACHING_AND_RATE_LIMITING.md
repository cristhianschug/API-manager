# Caching and Rate Limiting

Status: DRAFT

## Rate limiting dimensions

Potential levels:

- global;
- tenant;
- application;
- API key;
- endpoint.

## Concurrency limiting

Limit simultaneous expensive operations separately from request-per-second limits.

## Cache

If Redis is introduced, cache keys must include tenant scope where data is tenant-specific.

Configuration changes require reliable cache invalidation.

## Rule

Do not introduce distributed infrastructure merely for theoretical scale. Add it when measurements and architecture require it.
