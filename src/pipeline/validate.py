from typing import Dict, List, Optional, Tuple


def validate_classification(message: Dict[str, object], po_map: Dict[str, Dict[str, object]], seen_ids: set, evidence_required: bool = True) -> Tuple[bool, str]:
    po_ref = str(message.get("po_ref") or "")
    if not po_ref or po_ref not in po_map:
        return False, "po_missing"
    if message.get("message_id") in seen_ids:
        return False, "duplicate"
    if message.get("evidence") in (None, "") and evidence_required:
        return False, "no_evidence"
    amount = message.get("amount")
    if amount is not None:
        expected_amount = po_map[po_ref].get("amount")
        if amount != expected_amount:
            return False, "amount_mismatch"
    sender = message.get("sender")
    if sender and sender not in {po_map[po_ref].get("supplier_email"), po_map[po_ref].get("supplier")}: 
        return False, "sender_unknown"
    return True, "ok"
