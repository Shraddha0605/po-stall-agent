import random
import time
from typing import Callable, TypeVar

T = TypeVar("T")


def retry_with_backoff(func: Callable[[], T], *, retries: int = 3, base_delay: float = 0.2) -> T:
    last_error = None
    for attempt in range(retries):
        try:
            return func()
        except Exception as exc:  # pragma: no cover - simple fallback
            last_error = exc
            if attempt == retries - 1:
                raise
            delay = base_delay * (2**attempt) + random.uniform(0, 0.1)
            time.sleep(delay)
    raise last_error
