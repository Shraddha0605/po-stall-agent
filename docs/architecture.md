# Architecture

This project follows the staged pipeline described in the specification:

1. Ingest
2. Pre-filter
3. Classify
4. Validate
5. State
6. Age
7. Diagnose
8. Compose
9. Deliver
10. Reconcile

The current scaffold implements the deterministic pieces in the pipeline and exposes dry-run and eval entrypoints for local verification.
