from __future__ import annotations

import argparse
import json
import os
from urllib import request


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check an ai_logger server health endpoint.",
    )
    parser.add_argument(
        "--url",
        default=os.environ.get("AI_LOGGER_SERVER_HEALTH_URL"),
        help="Health URL, usually http://127.0.0.1:8765/health.",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("AI_LOGGER_SERVER_HOST", "127.0.0.1"),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("AI_LOGGER_SERVER_PORT", "8765")),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.environ.get("AI_LOGGER_SERVER_CHECK_TIMEOUT", "5")),
    )
    args = parser.parse_args(argv)

    health_url = args.url or f"http://{args.host}:{args.port}/health"
    try:
        http_request = request.Request(health_url, method="GET")
        with request.urlopen(http_request, timeout=args.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        print(f"ai_logger server check failed for {health_url}: {exc}")
        return 1

    if payload.get("status") != "ok":
        print(f"ai_logger server check failed for {health_url}: {payload}")
        return 1

    print(
        "ai_logger server healthy "
        f"at {health_url} plugins={payload.get('plugins', 'unknown')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
