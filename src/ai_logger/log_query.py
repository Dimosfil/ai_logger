from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any
from urllib import request


DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"


def load_jsonl_records(path: str | Path, *, limit: int = 50, text_filter: str | None = None) -> list[dict[str, Any]]:
    log_path = Path(path)
    if not log_path.exists():
        raise FileNotFoundError(f"Log path not found: {log_path}")

    needle = text_filter.lower() if text_filter else None
    records: list[dict[str, Any]] = []
    for file_path in _iter_jsonl_paths(log_path):
        with file_path.open("r", encoding="utf-8") as stream:
            for line in stream:
                line = line.strip()
                if not line:
                    continue
                if needle and needle not in line.lower():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    records.append(payload)

    if limit <= 0:
        return records
    return records[-limit:]


def _iter_jsonl_paths(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(
        (candidate for candidate in path.rglob("*.jsonl") if candidate.is_file()),
        key=lambda candidate: (candidate.stat().st_mtime, str(candidate)),
    )


def format_records_for_prompt(records: list[dict[str, Any]]) -> str:
    lines = []
    for index, record in enumerate(records, start=1):
        context = record.get("context") or {}
        exception = record.get("exception") or {}
        compact = {
            "n": index,
            "timestamp": record.get("timestamp"),
            "level": record.get("level"),
            "logger": record.get("logger") or record.get("logger_name"),
            "message": record.get("message"),
            "context": context,
        }
        if exception:
            compact["exception"] = {
                "type": exception.get("type"),
                "message": exception.get("message"),
            }
        lines.append(json.dumps(compact, ensure_ascii=False, sort_keys=True))
    return "\n".join(lines)


def ask_deepseek(
    *,
    question: str,
    log_context: str,
    api_key: str,
    base_url: str = DEFAULT_DEEPSEEK_BASE_URL,
    model: str = DEFAULT_DEEPSEEK_MODEL,
    timeout_seconds: float = 30.0,
) -> str:
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You analyze ai_logger JSONL logs. Answer only from the provided log records. "
                    "If the logs do not contain enough evidence, say what is missing."
                ),
            },
            {
                "role": "user",
                "content": f"Log records:\n{log_context}\n\nQuestion: {question}",
            },
        ],
        "stream": False,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    http_request = request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    with request.urlopen(http_request, timeout=timeout_seconds) as response:
        response_payload = json.loads(response.read().decode("utf-8"))

    choices = response_payload.get("choices") or []
    if not choices:
        raise RuntimeError("DeepSeek returned no choices.")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if not content:
        raise RuntimeError("DeepSeek returned an empty message.")
    return str(content)


def _default_logs_path() -> str:
    return (
        os.environ.get("AI_LOGGER_QUERY_LOGS_PATH")
        or os.environ.get("AI_LOGGER_SERVER_PROJECT_DAILY_DIR")
        or os.environ.get("AI_LOGGER_SERVER_JSONL_PATH")
        or "logs/server.jsonl"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ask DeepSeek a question about ai_logger JSONL logs.",
    )
    parser.add_argument("question", help="Question to answer from the log records.")
    parser.add_argument("--logs-path", default=_default_logs_path())
    parser.add_argument("--filter", default=None, help="Optional case-insensitive raw-line filter.")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--model", default=os.environ.get("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL))
    parser.add_argument("--base-url", default=os.environ.get("DEEPSEEK_BASE_URL", DEFAULT_DEEPSEEK_BASE_URL))
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.environ.get("DEEPSEEK_TIMEOUT", "30")),
    )
    parser.add_argument(
        "--print-context",
        action="store_true",
        help="Print the compact log context instead of calling DeepSeek.",
    )
    args = parser.parse_args(argv)

    try:
        records = load_jsonl_records(args.logs_path, limit=args.limit, text_filter=args.filter)
    except FileNotFoundError as exc:
        print(str(exc))
        return 2

    if not records:
        print(f"No log records found in {args.logs_path}.")
        return 1

    context = format_records_for_prompt(records)
    if args.print_context:
        print(context)
        return 0

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("DEEPSEEK_API_KEY is required to ask DeepSeek about logs.")
        return 2

    try:
        answer = ask_deepseek(
            question=args.question,
            log_context=context,
            api_key=api_key,
            base_url=args.base_url,
            model=args.model,
            timeout_seconds=args.timeout,
        )
    except Exception as exc:
        print(f"DeepSeek log query failed: {exc}")
        return 1

    print(answer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
