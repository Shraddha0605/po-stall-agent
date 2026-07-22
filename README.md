# PO Stall Detection & Resolution Agent

This repository provides a starter implementation of the PO stall detection workflow described in the project spec. It reads configured PO seed data, runs the deterministic prefilter/validation/reconciliation steps, and exposes CLI entrypoints for dry runs and evaluation.

## Safety model

The system is intentionally write-safe. It never sends email and never writes to the ERP; it only produces structured output and draft-ready artifacts in the scaffolded connectors.

## Setup order for the human

1. Install Python 3.11+ and the project requirements.
2. Copy .env.example to .env and add your Anthropic and Slack credentials.
3. Review config/settings.yaml, config/gsms.yaml, and config/taxonomy.yaml.
4. Run the dry-run entrypoint to confirm the workflow without writing anything.
5. When ready, run the once entrypoint against your real connectors.

## Quick start

```bash
python3 -m pip install -r requirements.txt
python3 -m src.run --dry-run
python3 -m src.eval
```

## Project layout

- src/run.py: CLI entrypoint
- src/pipeline: deterministic prefilter, validation, ageing, diagnosis, reconciliation
- src/connectors: Gmail and Slack connectors
- src/model: Anthropic wrapper scaffold
- src/store: SQLite-backed store with checkpoints and state rows
- tests: automated coverage for the deterministic workflow

## Scheduling

A simple cron example:

```bash
0 7 * * * cd /path/to/repo && python3 -m src.run --once
```

## Notes

This scaffold is designed to be extended into the full enterprise workflow from the specification. The current implementation focuses on deterministic logic, tests, and a runnable dry-run/evaluation path.
