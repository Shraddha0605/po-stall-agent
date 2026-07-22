from typing import Dict, List, Any

from src.model.client import AnthropicClient


def compose(ranked_rows: List[Dict[str, Any]], taxonomy: Dict[str, Any], client: AnthropicClient, confidence_threshold: float) -> Dict[str, Any]:
    response = client.compose_digest(ranked_rows, taxonomy)
    digest_text = response.get("digest", "")
    drafts = response.get("drafts", [])
    valid_po_refs = {row["po_ref"] for row in ranked_rows}
    valid_drafts = []
    for draft in drafts:
        if draft.get("po_ref") in valid_po_refs:
            if draft.get("confidence") is None or draft.get("confidence", 0.0) >= confidence_threshold:
                valid_drafts.append(draft)
        else:
            # drop any draft that does not reference a known PO
            continue

    blocks: List[Dict[str, Any]] = []
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*PO stall digest*"}})
    for line in digest_text.splitlines():
        if line.strip():
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": line}})
    return {"digest_blocks": blocks, "drafts": valid_drafts}
