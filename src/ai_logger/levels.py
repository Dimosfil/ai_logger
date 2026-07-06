from __future__ import annotations

from enum import IntEnum


class LogLevel(IntEnum):
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50

    @classmethod
    def coerce(cls, value: "LogLevel | str | int") -> "LogLevel":
        if isinstance(value, cls):
            return value
        if isinstance(value, int):
            return cls(value)
        normalized = value.strip().upper()
        return cls[normalized]
