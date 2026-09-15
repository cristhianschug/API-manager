# Scalability

Status: DRAFT

## Target architecture

`Load Balancer → API instances → Tenant-safe connection layer → Firebird`

API instances should be horizontally scalable.

## Bottleneck candidates

- Firebird itself;
- connection limits;
- disk I/O;
- slow queries;
- unbounded pagination;
- large result sets;
- reporting;
- Control Plane dependencies;
- cache contention.

## Heavy workloads

Long reports/exports should use asynchronous jobs rather than blocking normal API requests.

## Rule

Capacity must be established through benchmark evidence.
