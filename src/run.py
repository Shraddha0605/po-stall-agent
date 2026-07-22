import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

import yaml

from src.connectors.gmail import GmailConnector
from src.connectors.slack import SlackConnector
from src.pipeline.age import age_state
from src.pipeline.diagnose import diagnose_track
from src.pipeline.prefilter import prefilter_messages
from src.pipeline.reconcile import reconcile_counts
from src.pipeline.validate import validate_classification
import re
import csv
from datetime import date
from src.store.db import Store
from src.util.logging import configure_logging


def load_yaml(path: str):
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def build_arg_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--gsm", dest="gsm")
    return parser


def format_digest_lines(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    blocks = []
    if not items:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "No new PO messages were processed."}})
        return blocks
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*PO stall digest*"}})
    for item in items:
        text = f"• *{item['po_ref']}* — {item['subject']}"
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})
    return blocks


def parse_gmail_message(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": raw["id"],
        "threadId": raw["threadId"],
        "subject": raw.get("subject", ""),
        "sender": raw.get("from", ""),
        "body": raw.get("body", ""),
    }


def run_gsm(gsm: Dict[str, Any], settings: Dict[str, Any], taxonomy: Dict[str, Any], store: Store, logger, gmail: GmailConnector, slack: SlackConnector, dry_run: bool = False) -> Dict[str, Any]:
    gsm_id = gsm["id"]
    logger.info("Starting GSM run %s", gsm_id)
    pos = store.load_pos(gsm["po_seed_file"])
    po_refs = list(pos.keys())
    query = settings.get("po_query", "") or ""
    raw_messages = gmail.list_messages(query=query, max_results=50)
    messages = []
    for item in raw_messages:
        msg = gmail.get_message(item["id"])
        messages.append(parse_gmail_message(msg))
    keep, discarded = prefilter_messages(messages, po_refs, allowlist=[pos[po_ref]["supplier_email"] for po_ref in po_refs], pattern=settings.get("po_pattern", r"PO-\d{5}"))
    # Messages that passed prefilter may still lack a classified po_ref; attempt a rule-based extract from message body/subject
    processed = []
    seen_ids = set()
    po_pattern = re.compile(r"PO-\d{5}")
    # helper: guess action from stage using taxonomy or simple heuristics
    def guess_action(stage: str) -> str:
        stage = (stage or "").lower()
        if "finance" in stage or "invoice" in stage:
            return "Nudge AP for payment status"
        if "approval" in stage:
            return "Nudge the approver in-thread"
        if "quote" in stage or "revision" in stage:
            return "Request revised quote"
        if "issued" in stage:
            return "Chase acknowledgement from supplier"
        if "goods" in stage or "receipt" in stage:
            return "Confirm goods receipt and paperwork"
        return "Review"

    for message in keep:
        cleaned = {**message, "message_id": message.get("id"), "sender": message.get("sender")}
        # try to find PO refs in subject/body
        text = (message.get("subject", "") + "\n" + message.get("body", ""))
        found = po_pattern.findall(text)
        if not found:
            # no PO found -> route to review (preserves existing behavior)
            store.log_review(gsm_id, message["id"], "po_missing", message)
            continue
        # for each PO found, join with seed data and build a processed item
        for p in set(found):
            if p not in pos:
                store.log_review(gsm_id, message["id"], "po_unknown", message)
                continue
            seed = pos[p]
            # compute days open
            opened = seed.get("opened")
            days_open = None
            try:
                y, m, d = map(int, opened.split("-"))
                days_open = (date.today() - date(y, m, d)).days
            except Exception:
                days_open = None
            track = seed.get("stage")
            status = age_state(None, datetime.utcnow().isoformat() + "Z", settings.get("idle_threshold_working_days", 4))
            diagnosis = diagnose_track(track, taxonomy)
            action = guess_action(seed.get("stage"))
            store.append_state(gsm_id, p, track, status, message["id"], datetime.utcnow().isoformat() + "Z")
            processed.append({
                "po_ref": p,
                "subject": message.get("subject"),
                "track": track,
                "status": status,
                "diagnosis": diagnosis,
                "supplier": seed.get("supplier"),
                "amount": seed.get("amount"),
                "opened": seed.get("opened"),
                "days_open": days_open,
                "message_id": message.get("id"),
                "threadId": message.get("threadId"),
                "action": action,
            })
    for item in discarded:
        store.log_discard(gsm_id, item["message_id"], item.get("sender"), item.get("subject"), item.get("reason"))
    # build formatted digest blocks with details and group by urgency
    critical = []
    medium = []
    no_action = []
    for it in processed:
        d = it.get("days_open") or 0
        # map working-day threshold ~ threshold+2 calendar days for demo simplicity
        if d >= settings.get("idle_threshold_working_days", 4) + 2:
            critical.append(it)
        elif d >= 2:
            medium.append(it)
        else:
            no_action.append(it)

    digest_payload = {"critical": critical, "medium": medium, "no_action": no_action}
    # format blocks for Slack
    blocks = []
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*PO stall digest*"}})
    def line_for(e):
        return f"*{e['po_ref']}* — {e['supplier']} — ${e['amount']} — Stage: {e['track']} — Opened: {e['opened']} — Days open: {e['days_open']}\nNext action: {e['action']}"

    if critical:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*Critical*"}})
        for e in critical:
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": line_for(e)}})
    if medium:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*Medium*"}})
        for e in medium:
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": line_for(e)}})
    if no_action:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*No action*"}})
        for e in no_action:
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": line_for(e)}})

    # record digest and create drafts for actionable items
    run_key = datetime.utcnow().isoformat() + "Z"
    store.record_digest(gsm_id, run_key, digest_payload)
    # helper to build draft body
    def build_draft(e):
        subj = f"Re: {e.get('subject') or ''}"
        if 'Nudge' in e.get('action') or 'Nudge' in e.get('action'):
            body = f"Hi,\n\nFollowing up on {e['po_ref']} ({e['supplier']}, ${e['amount']}). This is currently in {e['track']} and has been open since {e['opened']} ({e['days_open']} days). Could you please provide an update or approve?\n\nThanks.\n"
        elif 'Chase' in e.get('action') or 'acknowledg' in e.get('action').lower():
            body = f"Hi {e['supplier']},\n\nCan you confirm receipt and provide expected delivery or acknowledgment for {e['po_ref']} ({e['amount']})?\n\nThanks.\n"
        else:
            body = f"Hi,\n\nQuestion on {e['po_ref']}: {e['action']}\n\nThanks.\n"
        return subj, body

    created_drafts = []
    for section in (critical + medium):
        subj, body = build_draft(section)
        if not dry_run:
            draft = gmail.create_draft(thread_id=section.get('threadId', section.get('message_id')), in_reply_to=section.get('message_id'), references=section.get('message_id'), body=body, subject=section.get('subject') or subj)
            draft_id = draft.get('id') if isinstance(draft, dict) else str(draft)
            store.record_draft(gsm_id, section.get('message_id'), section.get('po_ref'), draft_id, run_key)
            created_drafts.append({'po_ref': section.get('po_ref'), 'draft_id': draft_id})
        else:
            # dry-run: log draft intent and record as digest-only preview
            created_drafts.append({'po_ref': section.get('po_ref'), 'draft_preview': body})

    if not dry_run:
        slack.post_message(channel=gsm["slack_channel"], blocks=blocks)
    else:
        logger.info("Dry run slack blocks: %s", blocks)
        logger.info("Dry run draft previews: %s", created_drafts)
    reconciliation = reconcile_counts(len(messages), len(processed), len(discarded), len(processed), len(created_drafts))
    logger.info("gsm=%s reconciliation=%s", gsm_id, reconciliation)
    return reconciliation


def main():
    parser = build_arg_parser()
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    settings = load_yaml(root / "config" / "settings.yaml")
    taxonomy = load_yaml(root / "config" / "taxonomy.yaml")
    gsms = load_yaml(root / "config" / "gsms.yaml")["gsms"]
    logger = configure_logging(str(root / "logs"))
    store = Store(str(root / "po_stall_agent.db"))
    gmail = GmailConnector(auth_mode=os.getenv("GMAIL_AUTH_MODE", "fixture"))
    slack = SlackConnector(token=os.getenv("SLACK_BOT_TOKEN"))
    chosen = [gsm for gsm in gsms if args.gsm is None or gsm["id"] == args.gsm]
    for gsm in chosen:
        if args.gsm and gsm["id"] != args.gsm:
            continue
        run_gsm(gsm, settings, taxonomy, store, logger, gmail, slack, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
