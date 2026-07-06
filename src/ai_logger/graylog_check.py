from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone

from .levels import LogLevel
from .plugins import GraylogGelfPlugin
from .records import LogRecord


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Send a test GELF event to a Graylog HTTP input.",
    )
    parser.add_argument("--url", default=os.environ.get("AI_LOGGER_GRAYLOG_GELF_URL"))
    parser.add_argument("--host", default=os.environ.get("AI_LOGGER_GRAYLOG_HOST"))
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.environ.get("AI_LOGGER_GRAYLOG_TIMEOUT", "5")),
    )
    parser.add_argument("--message", default="ai_logger.graylog_check")
    args = parser.parse_args(argv)

    if not args.url:
        print("AI_LOGGER_GRAYLOG_GELF_URL or --url is required.")
        return 2

    plugin = GraylogGelfPlugin(
        args.url,
        host=args.host,
        timeout_seconds=args.timeout,
    )
    record = LogRecord(
        "ai_logger.graylog_check",
        LogLevel.INFO,
        args.message,
        context={
            "check": "graylog_backend",
            "checked_at": datetime.now(timezone.utc).isoformat(),
        },
        tags=("deploy", "graylog"),
    )
    try:
        plugin.emit(record)
    except Exception as exc:
        print(f"ai_logger Graylog check failed for {args.url}: {exc}")
        return 1

    print(f"ai_logger Graylog check delivered to {args.url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
