import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

from src.model.client import AnthropicClient
from src.pipeline.classify import TRACK_DEFINITIONS, _normalize_classification


def load_messages(path: str) -> List[Dict[str, Any]]:
    with open(path, 'r', encoding='utf-8') as handle:
        return [json.loads(line) for line in handle if line.strip()]


def build_candidate_pos(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    refs = {message['po_ref'] for message in messages if message.get('po_ref') != 'PO-99999'}
    return [{ 'po_ref': po_ref, 'supplier': 'unknown', 'amount': None } for po_ref in sorted(refs)]


def compare_fields(label: Dict[str, Any], predicted: Dict[str, Any]) -> float:
    fields = ['track', 'status_signal', 'date', 'amount', 'parties', 'evidence']
    correct = 0
    for field in fields:
        if label.get(field) == predicted.get(field):
            correct += 1
    return correct / len(fields)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--path', default='tests/golden/messages.jsonl')
    args = parser.parse_args()
    messages = load_messages(args.path)
    client = AnthropicClient(api_key=os.getenv('ANTHROPIC_API_KEY'))
    if not client.api_key:
        print('No model key present; skipping eval')
        return 0

    candidate_pos = build_candidate_pos(messages)
    total = len(messages)
    track_matches = 0
    field_matches = 0.0
    fabricated = 0

    for message in messages:
        prompt_message = {
            'id': message['id'],
            'threadId': None,
            'subject': message.get('status_signal', ''),
            'sender': message.get('sender', ''),
            'body': message.get('status_signal', ''),
        }
        predicted = client.classify_message(prompt_message, candidate_pos, TRACK_DEFINITIONS)
        normalized = _normalize_classification(predicted)
        if normalized.get('track') == message.get('track'):
            track_matches += 1
        if normalized.get('po_ref') not in {pos['po_ref'] for pos in candidate_pos}:
            fabricated += 1
        field_matches += compare_fields(message, normalized)

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
