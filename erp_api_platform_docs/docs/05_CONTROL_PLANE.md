# Control Plane

Status: DRAFT

## Responsibilities

- tenant management
- database mapping
- API key management
- permissions
- route publication
- schema catalog
- rate-limit configuration
- audit
- administrative users

## Storage

A separate relational control database is recommended, such as PostgreSQL.

## Security

Administrative access should be stronger than normal API access, preferably using modern identity federation and MFA where available.

## Hot path

The Control Plane must not be queried synchronously for every normal API request if cached configuration can safely be used.
