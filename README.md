PO Stall Agent
================

[![CI](https://github.com/Shraddha0605/po-stall-agent/actions/workflows/daily-run.yml/badge.svg)](https://github.com/Shraddha0605/po-stall-agent/actions/workflows/daily-run.yml) [![Release](https://img.shields.io/github/v/release/Shraddha0605/po-stall-agent?label=release&sort=semver)](https://github.com/Shraddha0605/po-stall-agent/releases)

A daily agent for Global Sourcing Managers (GSMs): it reads each GSM's Gmail mailbox, works out
which purchase orders are stuck and why, posts a ranked digest to Slack, and drafts the reply
emails a human reviews and sends.

What it does
------------
The ERP shows the *stage* of a PO but never the *cause* or the *owner* — that lives in email. This
system reconstructs each PO's state from the mailbox, detects stalls, and hands each GSM a morning
Slack digest plus ready-to-send Gmail draft replies. It's built to serve up to ~10 GSMs sharing one
Slack workspace, each with their own mailbox, PO list, channel, and drafts.

Safety model (important)
-----------------------
- **Never sends email.** The code only ever calls `users.drafts.create`; no path calls
  `users.messages.send` (enforced by `tests/test_no_send.py`, a static check over `src/`).
- **Never writes to the ERP.** All outputs are Gmail drafts and Slack posts for a human to act on.
- **Two LLM calls only.** One call classifies a message onto a track and extracts fields (MODEL CALL
  1); one call composes the digest and draft replies (MODEL CALL 2). Every other step — pre-filter,
  validation, aging, diagnosis, reconciliation — is deterministic code.

How it works (the 10-step pipeline)
-----------------------------------
1. **Ingest** — paginated Gmail reads since the GSM's last checkpoint (14-day lookback on first run).
2. **Pre-filter** — deterministic keep/discard by PO pattern, sender allowlist, or thread link.
3. **Classify** — MODEL CALL 1 (`src/pipeline/classify.py`): one JSON-only response per message with
   `po_ref`, `track`, `evidence`, `confidence`, etc. No verbatim quote, no field.
4. **Validate** — deterministic gate (`src/pipeline/validate.py`): rejects unknown POs, amount
   mismatches, evidence not found in the new message body, and duplicate `message_id`s.
5. **State** — append-only rows in the shared DB, namespaced by `gsm_id` (`src/store/db.py`).
6. **Age** — working-day idle time per track vs. the configured threshold.
7. **Diagnose** — deterministic taxonomy lookup to `{cause, owner, next_action}`.
8. **Compose** — MODEL CALL 2 (`src/pipeline/compose.py`): writes the Slack digest and per-PO reply
   drafts using only the facts in the state rows.
9. **Deliver** — posts a Block Kit message to the GSM's Slack channel and creates Gmail drafts.
10. **Reconcile** — asserts `ingested == passed + discarded` and `passed == state_updated +
    review_items` per GSM; a mismatch banners that GSM's digest and fails the run.

See `docs/architecture.md` for more detail.

Setup
-----
Prerequisites: Python 3.11+.

```bash
python3 -m pip install -r requirements.txt
```

Credentials (none are committed — copy `.env.example` to `.env` and fill in your own):
- `ANTHROPIC_API_KEY` — required for classification/compose; both steps skip cleanly without it.
- Gmail — either:
  - **Service account (recommended for a team):** create a service account in Google Cloud, enable
    domain-wide delegation, authorize the `gmail.readonly` and `gmail.compose` scopes for it in the
    Workspace admin console, download the JSON key, and set `GOOGLE_SERVICE_ACCOUNT_FILE` +
    `GMAIL_AUTH_MODE=service`. The agent impersonates each GSM's `email` from `config/gsms.yaml` —
    no per-user consent, safe to run unattended on a schedule.
  - **OAuth fallback (single personal mailbox, for demos):** create an OAuth client, download
    `credentials.json`, set `GMAIL_AUTH_MODE=oauth`, `GMAIL_OAUTH_CREDENTIALS`, and
    `GMAIL_OAUTH_TOKEN` (path to write/read `token.json`). First run opens a browser consent flow.
- Slack — create a bot token with the `chat:write` scope, set `SLACK_BOT_TOKEN`, and put each GSM's
  channel id in `config/gsms.yaml`.

Config:
- `config/settings.yaml` — PO pattern, idle threshold, model, confidence threshold.
- `config/gsms.yaml` — the list of GSMs: id, email, Slack channel, PO seed file.
- `config/taxonomy.yaml` — stall causes/owners/next actions per track.

Run
---
Dry-run first — prints the digest and drafts it *would* produce, writes nothing to Slack, Gmail, or
the state DB:

```bash
python -m src.run --once --dry-run
```

Single GSM:

```bash
python -m src.run --gsm gsm1 --dry-run
```

Full cycle (posts to Slack, creates Gmail drafts, advances checkpoints):

```bash
python -m src.run --once
```

To sanity-check the pipeline wiring before any credentials are set up at all, set
`GMAIL_AUTH_MODE=fixture` — this skips Gmail/Anthropic/Slack entirely and dry-runs an empty cycle for
every configured GSM, so you can confirm the install and config are wired correctly first.

Evaluation harness
------------------
```bash
python -m src.eval
```
Runs MODEL CALL 1 over the labelled messages in `tests/golden/messages.jsonl` and prints track
accuracy, field accuracy, and fabricated-PO count. Gate: ≥95% track, ≥95% field, zero fabricated POs.
Skips cleanly (exit 0) if `ANTHROPIC_API_KEY` isn't set.

Testing
-------
```bash
python3 -m pytest -q
```
All tests are deterministic and run with no network access, including `test_no_send` (static check:
no send scope, no `messages.send` anywhere in `src/`), `test_idempotency`, and `test_multi_gsm`.

Schedule it
-----------
Cron, daily at 07:00 UTC:

```cron
0 7 * * * cd /path/to/po-stall-agent && . /path/to/venv/bin/activate && python -m src.run --once
```

Or use `.github/workflows/daily-run.yml`, included in this repo. It runs on a schedule using
repository secrets and no-ops if those secrets aren't configured, so a fork won't fail CI.

Adapt for your team
--------------------
- Add a GSM: append an entry to `config/gsms.yaml` (id, email, Slack channel, PO seed file) and a
  matching CSV under `data/`. No code changes needed.
- Seed each GSM's PO list from your real PO tracker/ERP export instead of the sample CSVs.
- Point `slack_channel` at your team's real channels and set the bot token's scope accordingly.
- Tune `config/settings.yaml` (idle threshold, PO pattern, model) and `config/taxonomy.yaml`
  (add causes/owners specific to your procurement process).
- The included SQLite store (`src/store/db.py`) is sized for ~10 GSMs sharing one deployment; a
  larger rollout should move it to a managed Postgres/Cloud SQL instance behind the same `Store`
  interface.

Configuration reference
------------------------
- `config/settings.yaml`: `po_pattern` (regex, default `PO-\d{5}`), `idle_threshold_working_days`
  (default 4 — days idle before a track is `critical`), `lookback_days_first_run` (default 14),
  `model` (Anthropic model id), `confidence_threshold` (default 0.7 — below this, no draft is
  created and the digest names the department to follow up instead).
- `config/gsms.yaml`: `id`, `email`, `slack_channel`, `po_seed_file` per GSM.
- `config/taxonomy.yaml`: per-track rules mapping a stall to `{cause, owner, next_action}`.

What's deliberately not built
------------------------------
- Auto-send of any email, or any write path into the ERP.
- A review-queue UI — items routed to review are logged and surfaced in the Slack digest.
- Intra-day runs — this is a once-a-day batch by design.

Docs
----
- `docs/architecture.md` — pipeline and data-model detail.
- `docs/Discovery.md`, `docs/PRD.md` — the discovery notes and product requirements this was built
  from. The original source documents (`Discovery.pdf`/`.docx`, `PRD - PO Stall Detection.docx`,
  `AI Evaluation Plan.docx`) are kept at the repo root for reference.

Project layout
--------------
```
po-stall-agent/
├── README.md
├── LICENSE
├── .env.example
├── requirements.txt
├── .github/workflows/daily-run.yml
├── config/                  # settings.yaml, gsms.yaml, taxonomy.yaml
├── data/                    # seed PO CSVs per GSM
├── src/
│   ├── run.py                # entrypoint: iterate GSMs, run the 10 steps, exit code
│   ├── eval.py                # golden-set eval harness
│   ├── connectors/            # gmail.py, slack.py — read + draft, never send
│   ├── pipeline/               # prefilter, classify, validate, age, diagnose, compose, reconcile
│   ├── model/client.py          # Anthropic wrapper (both model calls)
│   ├── store/db.py              # schema, checkpoints, state — namespaced by gsm_id
│   └── util/                    # logging, dates, backoff
├── tests/                     # unit tests + golden classification set
└── docs/                      # architecture, discovery, PRD
```

License
-------
MIT — see LICENSE.
