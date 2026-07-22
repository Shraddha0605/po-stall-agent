from typing import Dict, List


def reconcile_counts(ingested: int, passed: int, discarded: int, state_updated: int, review_items: int) -> Dict[str, object]:
    ok = ingested == passed + discarded and passed == state_updated + review_items
    if not ok:
        return {
            "ok": False,
            "ingested": ingested,
            "passed": passed,
            "discarded": discarded,
            "state_updated": state_updated,
            "review_items": review_items,
        }
    return {
        "ok": True,
        "ingested": ingested,
        "passed": passed,
        "discarded": discarded,
        "state_updated": state_updated,
        "review_items": review_items,
    }
