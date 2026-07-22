from typing import Dict, Optional

from src.util.dates import working_days_between


def age_state(last_transition: Optional[str], now: str, threshold_days: int) -> str:
    if not last_transition:
        return "no_action"
    idle_days = working_days_between(last_transition, now)
    if idle_days >= threshold_days:
        return "critical"
    if idle_days > 0:
        return "medium"
    return "no_action"
