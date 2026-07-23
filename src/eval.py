import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.model.client import AnthropicClient
from src.pipeline.classify import TRACK_DEFINITIONS, _normalize_classification


def load_messages(path: str) -> List[Dict[str, Any]]:
    with open(path, 'r', encoding='utf-8') as handle:
        return [json.loads(line) for line in handle if line.strip()]


def build_candidate_pos(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    refs = {message['label']['po_ref'] for message in messages if message['label'].get('po_ref') != 'PO-99999'}
    return [{ 'po_ref': po_ref, 'supplier': 'unknown', 'amount': None } for po_ref in sorted(refs)]


def compare_fields(label: Dict[str, Any], predicted: Dict[str, Any], body: str) -> float:
    fields = ['track', 'blocker', 'date', 'amount', 'parties']
    correct = sum(1 for field in fields if label.get(field) == predicted.get(field))
    evidence = predicted.get('evidence') or ''
    correct += 1 if evidence and evidence in body else 0
    return correct / (len(fields) + 1)


def is_fabricated(predicted_ref: Optional[str], known_refs: set, label_ref: Optional[str]) -> bool:
    if not predicted_ref:
        return False
    if predicted_ref in known_refs:
        return False
    if predicted_ref == label_ref:
        return False
    return True


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--path', default='tests/golden/messages.jsonl')
    args = parser.parse_args(argv)
    messages = load_messages(args.path)
    client = AnthropicClient(api_key=os.getenv('ANTHROPIC_API_KEY'))
    if not client.api_key:
        print('No model key present; skipping eval')
        return 0

    candidate_pos = build_candidate_pos(messages)
    known_refs = {pos['po_ref'] for pos in candidate_pos}
    total = len(messages)
    track_matches = 0
    field_matches = 0.0
    fabricated = 0

    for message in messages:
        label = message['label']
        body = message.get('body', '')
        prompt_message = {
            'id': message['id'],
            'threadId': None,
            'subject': 'PO status update',
            'sender': message.get('sender', ''),
            'body': body,
        }
        predicted = client.classify_message(prompt_message, candidate_pos, TRACK_DEFINITIONS)
        normalized = _normalize_classification(predicted)
        if normalized.get('track') == label.get('track'):
            track_matches += 1
        if is_fabricated(normalized.get('po_ref'), known_refs, label.get('po_ref')):
            fabricated += 1
        field_matches += compare_fields(label, normalized, body)

    track_accuracy = track_matches / total * 100.0
    field_accuracy = field_matches / total * 100.0
    print(f'Track accuracy: {track_accuracy:.1f}%')
    print(f'Field accuracy: {field_accuracy:.1f}%')
    print(f'Fabricated PO count: {fabricated}')

    if track_accuracy >= 95.0 and field_accuracy >= 95.0 and fabricated == 0:
        print('Eval gate passed')
        return 0
    print('Eval gate failed')
    return 1


if __name__ == '__main__':
    sys.exit(main())
