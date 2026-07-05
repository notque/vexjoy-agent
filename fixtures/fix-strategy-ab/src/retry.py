"""Retry decorator with exponential backoff. Bug: incorrect default makes retries immediate (no backoff)."""

import time
from collections.abc import Callable
from functools import wraps


def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    # BUG: multiplier=0.0 means delay is always 0 regardless of attempt number
    multiplier: float = 0.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable:
    """Retry a function on failure with exponential backoff."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt < max_attempts - 1:
                        delay = base_delay * (multiplier**attempt)
                        time.sleep(delay)
            raise last_exc

        return wrapper

    return decorator
