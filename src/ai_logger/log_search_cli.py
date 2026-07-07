from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .llm import DeepSeekChatClient, LlmProviderError
from .log_search import DeepSeekLogSearchProvider, JsonlLogSource, SmartLogSearcher


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Search ai_logger JSONL logs with optional LLM help.")
    parser.add_argument("query", nargs="+", help="Problem description to search for.")
    parser.add_argument(
        "--jsonl-path",
        default=(
            os.environ.get("AI_LOGGER_LOG_SEARCH_JSONL_PATH")
            or os.environ.get("AI_LOGGER_SERVER_JSONL_PATH")
            or os.environ.get("AI_LOGGER_JSONL_PATH")
        ),
        help="JSON Lines log path. Defaults to AI_LOGGER_LOG_SEARCH_JSONL_PATH, AI_LOGGER_SERVER_JSONL_PATH, or AI_LOGGER_JSONL_PATH.",
    )
    parser.add_argument("--provider", default=os.environ.get("AI_LOGGER_LLM_PROVIDER", "deepseek"))
    parser.add_argument("--no-llm", action="store_true", help="Use local lexical ranking only.")
    parser.add_argument("--max-records", type=int, default=int(os.environ.get("AI_LOGGER_LOG_SEARCH_MAX_RECORDS", "500")))
    parser.add_argument("--candidates", type=int, default=int(os.environ.get("AI_LOGGER_LOG_SEARCH_CANDIDATES", "30")))
    parser.add_argument("--top-k", type=int, default=int(os.environ.get("AI_LOGGER_LOG_SEARCH_TOP_K", "5")))
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    if not args.jsonl_path:
        print("A JSONL path is required via --jsonl-path or AI_LOGGER_SERVER_JSONL_PATH.")
        return 2

    provider = None
    if not args.no_llm and args.provider.lower() == "deepseek":
        try:
            provider = DeepSeekLogSearchProvider(DeepSeekChatClient.from_env())
        except LlmProviderError as exc:
            print(f"DeepSeek configuration error: {exc}")
            return 2
    elif not args.no_llm and args.provider.lower() not in {"local", "none"}:
        print(f"Unsupported LLM provider: {args.provider}")
        return 2

    query = " ".join(args.query)
    try:
        result = SmartLogSearcher(
            JsonlLogSource(Path(args.jsonl_path)),
            llm_provider=provider,
        ).search(
            query,
            max_records=args.max_records,
            candidate_count=args.candidates,
            top_k=args.top_k,
        )
    except OSError as exc:
        print(f"Log search failed: {exc}")
        return 1

    if args.format == "json":
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print_text_result(result)
    return 0


def print_text_result(result) -> None:
    print(f"Provider: {result.provider}")
    for warning in result.warnings:
        print(f"Warning: {warning}")
    print(result.summary)
    for index, match in enumerate(result.matches, start=1):
        record = match.record
        print(
            f"{index}. [{record.level.name}] {record.timestamp.isoformat()} "
            f"{record.logger_name} {record.message} id={record.record_id} score={match.score:g}"
        )
        if match.reason:
            print(f"   reason: {match.reason}")
        if record.exception_type:
            print(f"   exception: {record.exception_type}: {record.exception_message or ''}")
        if record.context:
            context = json.dumps(record.context, ensure_ascii=False, sort_keys=True)
            print(f"   context: {context}")


if __name__ == "__main__":
    raise SystemExit(main())
