# Resilience Test Plan

Status: DRAFT

Test behavior when:

- Firebird is unavailable;
- Control Plane database is unavailable;
- cache is unavailable;
- API instance disappears;
- connections are lost;
- queries time out;
- a query becomes slow;
- a tenant sends excessive requests.

## Expected behavior

Failures must be bounded, observable, tenant-safe, and must not expose internal details.
