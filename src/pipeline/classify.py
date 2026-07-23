from typing import Any, Dict, List

from src.model.client import AnthropicClient

TRACK_DEFINITIONS = [
    {"track": "approval", "description": "Approval stage or approver action required.", "blockers": ["approver_idle", "over_limit", "budget_blocked"]},
    {"track": "supplier", "description": "Supplier acknowledgement, onboarding, or delivery issue.", "blockers": ["no_ack", "onboarding"]},
    {"track": "finance", "description": "Finance, AP, payment, or goods receipt issue.", "blockers": ["gr_missing", "payment_overdue"]},
    {"track": "commercial", "description": "Quote, price, or commercial review issue.", "blockers": ["quote_pending", "price_mismatch"]},
]

REQUIRED_FIELDS = [
    "po_ref",
    "track",
    "blocker",
    "status_signal",
    "date",
    "amount",
    "parties",
    "confidence",
    "evidence",
]


def _normalize_classification(output: Dict[str, Any]) -> Dict[str, Any]:
    normalized = {}
    for field in REQUIRED_FIELDS:
        normalized[field] = output.get(field, None)
    if isinstance(normalized["parties"], str):
        normalized["parties"] = [normalized["parties"]]
    if normalized["confidence"] is not None:
        try:
            normalized["confidence"] = float(normalized["confidence"])
        except (TypeError, ValueError):
            normalized["confidence"] = 0.0
    else:
        normalized["confidence"] = 0.0
    return normalized


def classify_messages(messages: List[Dict[str, Any]], candidate_pos: List[Dict[str, Any]], client: AnthropicClient, logger) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for message in messages:
        classification = client.classify_message(message, candidate_pos, TRACK_DEFINITIONS)
        if not isinstance(classification, dict):
            logger.warning("Invalid classification type for message %s", message.get("id"))
            classification = {field: None for field in REQUIRED_FIELDS}
            classification["confidence"] = 0.0
            classification["evidence"] = None

        normalized = _normalize_classification(classification)
        normalized.update(
            {
                "message_id": message.get("id"),
                "sender": message.get("sender"),
                "subject": message.get("subject"),
                "body": message.get("body"),
                "threadId": message.get("threadId"),
            }
        )
        results.append(normalized)
    return results
