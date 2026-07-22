import argparse
import os
import sys
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from src.connectors.gmail import GmailConnector
from src.connectors.slack import SlackConnector
from src.model.client import AnthropicClient
from src.pipeline.age import age_state
from src.pipeline.classify import classify_messages
from src.pipeline.compose import compose
from src.pipeline.diagnose import diagnose_track
from src.pipeline.prefilter import prefilter_messages
from src.pipeline.reconcile import reconcile_counts
from src.pipeline.validate import validate_classification
from src.store.db import Store
from src.util.logging import configure_logging


def load_yaml(path: str):
    with open(path, 'r', encoding='utf-8') as handle:
        return yaml.safe_load(handle)


def build_arg_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--gsm', dest='gsm')
    return parser


def parse_gmail_message(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'id': raw['id'],
        'threadId': raw.get('threadId'),
        'subject': raw.get('subject', ''),
        'sender': raw.get('from', ''),
        'body': raw.get('body', ''),
        'internalDate': raw.get('internalDate', '0'),
    }


def build_query(pattern: str, since_iso: str) -> str:
    try:
        cutoff = datetime.fromisoformat(since_iso.replace('Z', '+00:00'))
        return f"{pattern} after:{cutoff.strftime('%Y/%m/%d')}"
    except Exception:
        return pattern


def run_gsm(
    gsm: Dict[str, Any],
    settings: Dict[str, Any],
    taxonomy: Dict[str, Any],
    store: Store,
    logger,
    gmail: GmailConnector,
    slack: SlackConnector,
    dry_run: bool = False,
) -> Dict[str, Any]:
    gsm_id = gsm['id']
    logger.info('Starting GSM run %s', gsm_id)
    pos = store.load_pos(gsm['po_seed_file'])
    if not pos:
        logger.warning('No PO seed data for %s', gsm_id)
        return {'ok': False, 'reason': 'no_pos'}

    checkpoint = store.get_checkpoint(gsm_id)
    if checkpoint and checkpoint.get('updated_at'):
        since = checkpoint['updated_at']
    else:
        since = (datetime.utcnow() - timedelta(days=settings.get('lookback_days_first_run', 14))).isoformat() + 'Z'

    query = build_query(settings.get('po_pattern', r'PO-\d{5}'), since)
    raw_items = gmail.list_messages(user_id=gsm.get('email'), query=query, max_results=200)
    messages = [parse_gmail_message(gmail.get_message(gsm.get('email'), item['id'])) for item in raw_items]
    messages.sort(key=lambda item: int(item.get('internalDate') or '0'))

    keep, discarded = prefilter_messages(
        messages,
        list(pos.keys()),
        allowlist=[pos[po_ref]['supplier_email'] for po_ref in pos],
        pattern=settings.get('po_pattern', r'PO-\d{5}'),
    )

    client = AnthropicClient(api_key=os.getenv('ANTHROPIC_API_KEY'), model=settings.get('model'))
    classified = classify_messages(keep, list(pos.values()), client, logger)

    current_rows = store.current_state(gsm_id)
    last_state = {(row['po_ref'], row['track']): row for row in current_rows}

    processed: List[Dict[str, Any]] = []
    review_items = 0
    state_updated = 0
    for classification in classified:
        message_id = classification.get('message_id')
        if not message_id:
            logger.info('Skipping classification with missing message_id')
            review_items += 1
            continue

        if store.message_seen(gsm_id, message_id):
            validation_ok = False
            reason = 'duplicate'
        else:
            validation_ok, reason = validate_classification(classification, pos, set(), evidence_required=True)

        if not validation_ok:
            logger.info('Validation failed for %s: %s', message_id, reason)
            if not dry_run:
                store.log_review(gsm_id, message_id, reason, classification)
            review_items += 1
            continue

        last_transition = last_state.get((classification['po_ref'], classification['track']), {}).get('timestamp')
        now_iso = datetime.utcnow().isoformat() + 'Z'
        status = age_state(last_transition, now_iso, settings.get('idle_threshold_working_days', 4))
        diagnosis = diagnose_track(classification['track'], taxonomy)

        row = {
            'gsm_id': gsm_id,
            'po_ref': classification['po_ref'],
            'track': classification['track'],
            'status': status,
            'cause': diagnosis['cause'],
            'owner': diagnosis['owner'],
            'next_action': diagnosis['next_action'],
            'source_message_id': message_id,
            'timestamp': now_iso,
            'threadId': classification.get('threadId'),
            'subject': classification.get('subject'),
            'body': classification.get('body'),
            'confidence': classification.get('confidence', 0.0),
            'amount': classification.get('amount'),
            'opened': pos[classification['po_ref']]['opened'],
            'supplier': pos[classification['po_ref']]['supplier'],
        }

        if not dry_run:
            store.append_state(
                gsm_id,
                row['po_ref'],
                row['track'],
                row['status'],
                row['source_message_id'],
                row['timestamp'],
            )
        state_updated += 1
        processed.append(row)

    if not dry_run and messages:
        store.set_checkpoint(gsm_id, messages[-1]['id'])

    composed = compose(processed, taxonomy, client, settings.get('confidence_threshold', 0.7))
    digest_blocks = composed.get('digest_blocks', [])
    draft_specs = composed.get('drafts', [])

    created_drafts = []
    run_key = datetime.utcnow().isoformat() + 'Z'
    if not dry_run:
        if digest_blocks:
            slack.post_message(channel=gsm['slack_channel'], blocks=digest_blocks)
        for draft in draft_specs:
            po_ref = draft.get('po_ref')
            if not po_ref or po_ref not in pos:
                continue
            if store.draft_seen(gsm_id, draft.get('message_id', ''), po_ref, run_key):
                continue
            created = gmail.create_draft(
                user_id=gsm.get('email'),
                thread_id=draft.get('threadId'),
                in_reply_to=draft.get('message_id', ''),
                references=draft.get('message_id', ''),
                body=draft.get('body', ''),
                subject=draft.get('subject', f"Re: {po_ref}"),
            )
            draft_id = created.get('id') if isinstance(created, dict) else str(created)
            store.record_draft(gsm_id, draft.get('message_id', ''), po_ref, draft_id, run_key)
            created_drafts.append({'po_ref': po_ref, 'draft_id': draft_id})
    else:
        logger.info('Dry run digest blocks: %s', digest_blocks)
        logger.info('Dry run draft specs: %s', draft_specs)
        for draft in draft_specs:
            created_drafts.append({'po_ref': draft.get('po_ref'), 'preview': draft.get('body')})

    reconciliation = reconcile_counts(
        len(messages),
        len(processed),
        len(discarded),
        state_updated,
        review_items,
    )
    logger.info('gsm=%s reconciliation=%s', gsm_id, reconciliation)
    return reconciliation


def main():
    parser = build_arg_parser()
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    settings = load_yaml(root / 'config' / 'settings.yaml')
    taxonomy = load_yaml(root / 'config' / 'taxonomy.yaml')
    gsms = load_yaml(root / 'config' / 'gsms.yaml')['gsms']
    logger = configure_logging(str(root / 'logs'))
    store = Store(str(root / 'po_stall_agent.db'))
    gmail = GmailConnector(auth_mode=os.getenv('GMAIL_AUTH_MODE', 'service'))
    slack = None if args.dry_run else SlackConnector(token=os.getenv('SLACK_BOT_TOKEN'))
    chosen = [gsm for gsm in gsms if args.gsm is None or gsm['id'] == args.gsm]
    exit_code = 0
    for gsm in chosen:
        try:
            result = run_gsm(gsm, settings, taxonomy, store, logger, gmail, slack, dry_run=args.dry_run)
            if not result.get('ok', True):
                exit_code = 1
        except Exception:
            logger.exception('GSM run failed for %s', gsm['id'])
            exit_code = 1
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
