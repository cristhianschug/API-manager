# ERP API Platform — Documentation

Status: DRAFT  
Version: 0.1.0

## Purpose

This repository documents the architecture, discovery, security model, API contract, tenancy model, scalability strategy, and validation plan for a multi-tenant API over Firebird ERP databases.

## Documentation rule

Documentation is a controlled artifact. Changes must preserve traceability and must not silently overwrite previous decisions.

Lifecycle:

`DISCOVERY → EVIDENCE → DECISION → DESIGN → IMPLEMENTATION → VALIDATION`

No production implementation should begin before the corresponding architecture and contract artifacts are approved.

## Source of truth

- Database facts: database discovery artifacts and captured evidence.
- Architectural decisions: `00.3_DECISION_LOG.md`.
- Public API contract: `04.1_API_CONTRACT.md` and OpenAPI specification.
- Security requirements: `03_SECURITY_ARCHITECTURE.md` and its child documents.
- Tenant isolation requirements: `03.2_TENANT_ISOLATION.md`.
