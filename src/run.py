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
    processed = []
    seen_ids = set()
    for message in keep:
        cleaned = {**message, "message_id": message.get("id"), "sender": message.get("sender")}
        valid, reason = validate_classification(cleaned, pos, seen_ids)
        if valid:
            seen_ids.add(message["id"])
            track = "approval"
            status = age_state(None, datetime.utcnow().isoformat() + "Z", settings.get("idle_threshold_working_days", 4))
            diagnosis = diagnose_track(track, taxonomy)
            store.append_state(gsm_id, message.get("subject", "unknown"), track, status, message["id"], datetime.utcnow().isoformat() + "Z")
            processed.append({"po_ref": "unknown", "subject": message["subject"], "track": track, "status": status, "diagnosis": diagnosis})
        else:
            store.log_review(gsm_id, message["id"], reason, message)
    for item in discarded:
        store.log_discard(gsm_id, item["message_id"], item.get("sender"), item.get("subject"), item.get("reason"))
    blocks = format_digest_lines(processed)
    if not dry_run:
        slack.post_message(channel=gsm["slack_channel"], blocks=blocks)
    else:
        logger.info("Dry run slack blocks: %s", blocks)
    reconciliation = reconcile_counts(len(messages), len(processed), len(discarded), len(processed), 0)
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
