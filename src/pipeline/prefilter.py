import re
from typing import Dict, List, Optional, Tuple


def prefilter_messages(messages: List[Dict[str, object]], po_refs: List[str], allowlist: Optional[List[str]] = None, pattern: str = r"PO-\d{5}") -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    allowlist = allowlist or []
    compiled = re.compile(pattern)
    keep = []
    discard = []
    for message in messages:
        sender = str(message.get("sender") or "")
        subject = str(message.get("subject") or "")
        body = str(message.get("body") or "")
        thread_id = str(message.get("threadId") or "")
        text = f"{subject}\n{body}\n{thread_id}"
        if any(ref in text for ref in po_refs) or sender in allowlist or compiled.search(text):
            keep.append(message)
        else:
            discard.append({
                "message_id": message.get("id"),
                "sender": sender,
                "subject": subject,
                "reason": "not in scope",
            })
    return keep, discard
