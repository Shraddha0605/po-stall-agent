PO Stall Agent
================

[![CI](https://github.com/Shraddha0605/po-stall-agent/actions/workflows/daily-run.yml/badge.svg)](https://github.com/Shraddha0605/po-stall-agent/actions/workflows/daily-run.yml) [![Release](https://img.shields.io/github/v/release/Shraddha0605/po-stall-agent?label=release&sort=semver)](https://github.com/Shraddha0605/po-stall-agent/releases)

What it does
------------
- Reads each configured Global Sourcing Manager's (GSM) Gmail mailbox, detects stalled POs, and produces a daily digest per GSM in Slack plus draft reply emails in that GSM's Gmail Drafts. A human reviews and sends everything.

Safety model (important)
-----------------------
- Never sends email programmatically. The code uses `users.drafts.create` only; no path calls `users.messages.send`.
- Never writes to the ERP. All outputs are drafts and Slack posts for human action.
- Two LLM calls only: one for message classification+field extraction (MODEL CALL 1) and one for composing the digest + reply drafts (MODEL CALL 2). All other steps are deterministic code.

Quick start
-----------
Prerequisites: Python 3.11+, git, network access for optional model calls.

1. Install runtime deps:

```bash
python3 -m pip install -r requirements.txt
```

2. Configure (see `config/`):
- `config/settings.yaml` – pattern, thresholds, model name, confidence threshold.
- `config/gsms.yaml` – list of GSMs (id, email, slack_channel, po_seed_file).
- `config/taxonomy.yaml` – diagnostic taxonomy mapping tracks → cause/owner/next_action.

3. Credentials (no secrets in repo):
- `ANTHROPIC_API_KEY` (optional — required to run eval and live model calls).
- Gmail: `GOOGLE_SERVICE_ACCOUNT_FILE` for service-account + domain-wide delegation, or OAuth fallback (`credentials.json` / `token.json`).
- `SLACK_BOT_TOKEN` for Slack posting.

Run (dry-run first)
-------------------
Dry-run prints the digest and drafts without writing to Slack or creating drafts:

```bash
python -m src.run --once --dry-run
```

Run a single GSM (dry-run):

```bash
python -m src.run --gsm gsm1 --dry-run
```

Run one full cycle (writes drafts and posts to Slack):

```bash
python -m src.run --once
```

Evaluation harness
------------------
Run the golden-set eval (uses `ANTHROPIC_API_KEY` if present; skips cleanly without it):

```bash
python -m src.eval
```

Testing
-------
Run the unit tests locally:

```bash
python3 -m pytest -q
```

Configuration notes
-------------------
- `po_pattern` (regex) in `config/settings.yaml` defaults to `PO-\d{5}`.
- `idle_threshold_working_days` controls when a track becomes `critical`.
- `lookback_days_first_run` controls initial mailbox lookback.

How it works (the 10-step pipeline)
-----------------------------------
1. Ingest — paginated Gmail reads since the last checkpoint (14-day first-run lookback).
2. Pre-filter — deterministic keep/discard by PO pattern, allowlist, or thread link.
3. Classify — MODEL CALL 1: one JSON-only response per message with `po_ref`, `track`, `evidence`, `confidence`, etc.
4. Validate — deterministic gate; rejects messages that fail hard checks (unknown PO, amount mismatch, no evidence in new body, duplicate message_id).
5. State — append-only rows in the shared DB namespaced by `gsm_id`.
6. Age — compute working-day idle time per track vs threshold.
7. Diagnose — deterministic taxonomy lookup to map stalled tracks to `{cause, owner, next_action}`.
8. Compose — MODEL CALL 2: create the Slack digest text and per-PO reply drafts (only using facts from state rows).
9. Deliver — post Block Kit Slack message to the GSM channel and create Gmail drafts (`users.drafts.create`). Backoff + pagination applied to connectors.
10. Reconcile — assert counts: `ingested == passed + discarded` and `passed == state_updated + routed_to_review` per GSM; failures banner the Slack digest and exit non-zero for that GSM.

Robustness and production concerns
----------------------------------
- Idempotency: dedupe on `message_id`; track produced drafts/digests per run so repeated runs don't duplicate.
- Isolation: one GSM's failure doesn't abort others; per-GSM checkpoints ensure resumed runs are safe.
- Backoff & pagination: all Gmail and Slack calls use exponential backoff for 429/5xx.
- Logging: structured per-run, per-GSM logs written to rotating files.
- `--dry-run` mode avoids any external writes.

Developer notes
---------------
- Core modules: `src/run.py` (orchestrator), `src/model/client.py` (Anthropic wrapper), `src/connectors/gmail.py`, `src/connectors/slack.py`, `src/store/db.py`, `src/pipeline/*` (pipeline steps).
- Tests: `tests/` contains unit tests and the golden set for classifier evaluation.
- The repo includes `config/` seed files and `data/` sample PO CSVs for demo GSMs.

Scheduling
----------
Cron example (run daily at 07:00 UTC):

```cron
0 7 * * * cd /path/to/po-stall-agent && . /path/to/venv/bin/activate && python -m src.run --once
```

GitHub Actions
--------------
- A workflow `/.github/workflows/daily-run.yml` is included. It is guarded to no-op unless secrets are set in the repository settings.

What's deliberately not built
----------------------------
- No automatic `messages.send` or any ERP-write integration.
- No GUI review queue (messages routed to review are logged and surfaced in digests).

Where to look next
------------------
- Read the pipeline orchestrator: `src/run.py`.
- Model prompts and parsing: `src/model/client.py`.
- Eval harness: `src/eval.py` and `tests/golden/messages.jsonl`.

License
-------
MIT — see LICENSE.
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
