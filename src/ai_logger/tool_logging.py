from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .config import configured_logger
from .logger import Logger


def get_tool_logger(
    name: str,
    *,
    environ: Mapping[str, str] | None = None,
    **context: Any,
) -> Logger:
    return configured_logger(
        name,
        environ=environ,
        context={"tool": name, **context},
    )
