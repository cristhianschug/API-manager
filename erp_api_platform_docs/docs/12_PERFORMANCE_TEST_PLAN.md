# Performance Test Plan

Status: DRAFT

## Progression

Start conservatively and increase load:

`10 → 50 → 100 → 250 → 500 → 1000 → 2000+ concurrent users`

Actual levels depend on environment and database capacity.

## Measure

- RPS
- P50
- P95
- P99
- error rate
- timeout rate
- CPU
- RAM
- active connections
- pool utilization
- Firebird latency
- disk I/O

## Acceptance

No capacity claim is valid without recorded benchmark evidence.
