import os
import json
from typing import Any, Dict, List


class AnthropicClient:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")

    def classify_message(self, message: Dict[str, Any], candidate_pos: List[Dict[str, Any]], track_definitions: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not self.api_key:
            return {
                "po_ref": candidate_pos[0]["po_ref"] if candidate_pos else None,
                "track": "approval",
                "status_signal": "No model key present",
                "date": None,
                "amount": None,
                "parties": [],
                "confidence": 0.0,
                "evidence": "",
            }
        raise NotImplementedError("Anthropic integration is not configured in this scaffold")

    def compose_digest(self, rows: List[Dict[str, Any]], taxonomy: Dict[str, Any]) -> Dict[str, Any]:
        if not self.api_key:
            return {"digest": "Dry run", "drafts": []}
        raise NotImplementedError("Anthropic integration is not configured in this scaffold")
