from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone

from .config import build_client_from_env
from .levels import LogLevel
from .records import LogRecord


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Send a test event to an ai_logger ingest server.",
    )
    parser.add_argument("--server-url", default=os.environ.get("AI_LOGGER_SERVER_URL"))
    parser.add_argument("--token", default=os.environ.get("AI_LOGGER_SERVER_TOKEN"))
    parser.add_argument("--project", default=os.environ.get("AI_LOGGER_PROJECT", "client-check"))
    parser.add_argument("--service", default=os.environ.get("AI_LOGGER_SERVICE", "client-check"))
    parser.add_argument(
        "--environment",
        default=os.environ.get("AI_LOGGER_ENVIRONMENT", "local"),
    )
    parser.add_argument("--host", default=os.environ.get("AI_LOGGER_HOST"))
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.environ.get("AI_LOGGER_HTTP_TIMEOUT", "5")),
    )
    parser.add_argument(
        "--fallback-jsonl-path",
        default=os.environ.get("AI_LOGGER_FALLBACK_JSONL_PATH"),
    )
    parser.add_argument("--message", default="ai_logger.client_check")
    args = parser.parse_args(argv)

    if not args.server_url:
        print("AI_LOGGER_SERVER_URL or --server-url is required.")
        return 2

    environ = {
        "AI_LOGGER_SERVER_URL": args.server_url,
        "AI_LOGGER_HTTP_TIMEOUT": str(args.timeout),
    }
    if args.token:
        environ["AI_LOGGER_SERVER_TOKEN"] = args.token
    if args.project:
        environ["AI_LOGGER_PROJECT"] = args.project
    if args.service:
        environ["AI_LOGGER_SERVICE"] = args.service
    if args.environment:
        environ["AI_LOGGER_ENVIRONMENT"] = args.environment
    if args.host:
        environ["AI_LOGGER_HOST"] = args.host
    if args.fallback_jsonl_path:
        environ["AI_LOGGER_FALLBACK_JSONL_PATH"] = args.fallback_jsonl_path

    client = build_client_from_env(environ)
    delivered = client.send(
        LogRecord(
            "ai_logger.client_check",
            LogLevel.INFO,
            args.message,
            context={
                "check": "client_install",
                "checked_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    )
    if delivered:
        print(f"ai_logger client check delivered to {args.server_url}")
        return 0

    print(f"ai_logger client check failed for {args.server_url}")
    if args.fallback_jsonl_path:
        print(f"fallback written to {args.fallback_jsonl_path}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
