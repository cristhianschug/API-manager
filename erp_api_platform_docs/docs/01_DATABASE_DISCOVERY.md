# Database Discovery

Status: DRAFT  
Input: `<FDB_FILE_TO_BE_ANALYZED>`

## Objective

Create an evidence-based inventory of the Firebird database structure before designing API endpoints.

## Required inspection

- tables
- columns
- data types
- domains
- nullability
- defaults
- primary keys
- foreign keys
- unique constraints
- indexes
- views
- view dependencies
- triggers
- trigger timing/events
- procedures
- procedure parameters
- procedure dependencies
- functions
- generators/sequences
- constraints
- system objects relevant to application behavior

## Evidence policy

Every significant finding must identify its evidence source.

Use one of:

- FACT
- EVIDENCE
- INFERENCE
- ASSUMPTION
- UNKNOWN

## Deliverable

No API implementation begins from this document alone. Discovery must be reviewed before domain/API design.
