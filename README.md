# PO Stall Detection & Resolution Agent

This project is a proof of concept that reads GSM mailboxes, detects stalled purchase orders, posts a structured digest to Slack, and creates Gmail reply drafts for follow-up.

## Problem
Finance and sourcing teams know a PO is delayed, but the ERP only shows the stage. The missing piece is the cause and next owner, which usually lives in email and chat.

## Solution
This repository provides a pipeline that:
- reads each GSM mailbox,
- identifies PO-related messages,
- links messages to seeded PO data,
- ranks stalled items by urgency,
- posts a digest to Slack,
- creates Gmail drafts for the next action.

## How it works
- `src/run.py` runs the end-to-end pipeline.
- `config/gsms.yaml` defines each GSM and channel.
- `config/settings.yaml` controls the PO pattern and ages.
- `src/connectors` contains Gmail and Slack integration.
- `src/pipeline` implements deterministic filtering, aging, diagnosis, and reconciliation.

## Setup
1. Install Python 3.11+.
2. Copy `.env.example` to `.env`.
3. Fill in your own Slack token and Gmail credential paths.
4. Review `config/*.yaml` for your GSMs and taxonomy.
5. Run:

```bash
python3 -m pip install -r requirements.txt
python3 -m src.run --dry-run --gsm gsm1
```

6. If the dry run looks correct, run:

```bash
python3 -m src.run --once --gsm gsm1
```

## GitHub Actions
The workflow in `.github/workflows/daily-run.yml` only runs when required secrets are configured in GitHub.

## Docs
See `docs/Discovery.md` and `docs/PRD.md` for the project assumptions, system logic, and proof-of-concept design.

## Important
- Do not commit `.env` or any credential files.
- The repo is public-ready and uses environment variables for all secrets.
- Configure GitHub secrets for Slack and Gmail before enabling the scheduled workflow.
- This is a proof of concept; a real deployment should add stronger production validation and monitoring.

## Structure
- `src/`: application code
- `config/`: runtime settings and GSM definitions
- `data/`: sample PO seed files
- `tests/`: unit tests
- `docs/`: PRD and discovery notes
