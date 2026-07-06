from __future__ import annotations

from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Iterator, TypeVar

from .levels import LogLevel
from .logger import Logger

T = TypeVar("T")


@contextmanager
def log_exceptions(
    logger: Logger,
    message: str,
    *,
    level: LogLevel | str | int = LogLevel.ERROR,
    suppress: bool = False,
    tags: tuple[str, ...] | list[str] = (),
    **context: Any,
) -> Iterator[None]:
    try:
        yield
    except Exception as exc:
        logger.exception(message, exc, level=level, tags=tags, **context)
        if not suppress:
            raise


def catch_and_log(
    logger: Logger,
    message: str,
    *,
    level: LogLevel | str | int = LogLevel.ERROR,
    reraise: bool = True,
    default: Any = None,
    tags: tuple[str, ...] | list[str] = (),
    **context: Any,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                logger.exception(message, exc, level=level, tags=tags, **context)
                if reraise:
                    raise
                return default

        return wrapper

    return decorator
