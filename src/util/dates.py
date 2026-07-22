from datetime import datetime, timedelta
import calendar


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def working_days_between(start: str, end: str) -> int:
    start_dt = parse_iso(start)
    end_dt = parse_iso(end)
    if end_dt < start_dt:
        return 0
    days = 0
    current = start_dt.date()
    while current <= end_dt.date():
        if calendar.weekday(current.year, current.month, current.day) < 5:
            days += 1
        current += timedelta(days=1)
    return days - 1
