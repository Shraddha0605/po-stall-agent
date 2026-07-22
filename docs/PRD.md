# PO Stall Detection & Resolution Proof of Concept

This document summarizes the problem, the solution approach, and the system logic for the PO stall detection proof of concept.

## Problem
Purchasing teams lose visibility into why purchase orders are stuck. The ERP can show stage, but not the cause or the owner. The missing data often lives in email and chat.

## Solution
This project reads each configured GSM mailbox, filters for PO-related messages, extracts PO references, assigns urgency, and posts a structured stall digest to Slack. It also creates reply drafts in Gmail so a human can send the next action.

## System logic
- Ingest mail per GSM mailbox since the last run.
- Pre-filter only PO-relevant messages.
- Extract PO references and link them to seeded PO data.
- Determine urgency based on days open and PO stage.
- Compose a Slack digest grouped by Critical / Medium / No action.
- Create draft Gmail replies for actionable POs.
- Reconcile counts to ensure no messages are silently dropped.

## What this repo includes
- `src/run.py` entrypoint with `--dry-run` and `--once`
- Gmail + Slack connectors
- Deterministic pipeline modules for prefilter, validate, age, diagnose, reconcile
- SQLite-backed state and idempotency support
- Example PO seed data for two GSM users
- GitHub Actions workflow for scheduled runs
