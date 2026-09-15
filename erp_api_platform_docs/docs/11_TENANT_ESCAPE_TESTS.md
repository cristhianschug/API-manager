# Tenant Escape Tests

Status: DRAFT

## Objective

Prove that Tenant A cannot access Tenant B.

## Test matrix

| Vector | Attack | Expected |
|---|---|---|
| URL | Replace resource ID | DENY / NOT FOUND |
| Query | Inject another tenant identifier | DENY |
| Header | Forge tenant header | DENY |
| API key | Use Tenant A key against B mapping | DENY |
| Cache | Reuse cached B object under A | DENY |
| Pagination | Manipulate cursors | DENY |
| Concurrent | Mix A/B requests | No leakage |
| Connection | Attempt pool cross-use | Impossible |

## Critical invariant

No successful test may reveal Tenant B data to Tenant A.
