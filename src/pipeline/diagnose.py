from typing import Dict, Optional


def diagnose_track(track: str, taxonomy: Dict[str, Dict[str, Dict[str, str]]], key: Optional[str] = None) -> Dict[str, str]:
    if track not in taxonomy:
        return {"cause": "inferred", "owner": "unknown", "next_action": "review"}
    rule = taxonomy[track].get(key)
    if rule is None:
        return {"cause": "inferred", "owner": "unknown", "next_action": "review"}
    return rule
