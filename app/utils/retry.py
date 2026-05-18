from __future__ import annotations

import asyncio
import functools
import logging
from collections.abc import Awaitable, Callable
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")


def async_retry(
    attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 8.0,
    retry_exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            logger = logging.getLogger(func.__module__)
            delay = base_delay
            last_exc: Exception | None = None
            for attempt in range(1, attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except retry_exceptions as exc:
                    last_exc = exc
                    if attempt >= attempts:
                        break
                    logger.warning("Retry %s/%s for %s after error: %s", attempt, attempts, func.__name__, exc)
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, max_delay)
            assert last_exc is not None
            raise last_exc

        return wrapper

    return decorator

