from __future__ import annotations

import json
import re
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Protocol

from .client import redact_value
from .llm import LlmProviderError
from .records import LogRecord


TOKEN_RE = re.compile(r"[\w.-]+", re.UNICODE)


class LogSearchLlmProvider(Protocol):
    name: str

    def analyze(
        self,
        query: str,
        candidates: list["LogSearchCandidate"],
        *,
        top_k: int,
        response_language: str = "en",
    ) -> "LlmLogSearchAnalysis":
        ...


@dataclass(frozen=True)
class LogSearchCandidate:
    record: LogRecord
    score: float
    highlights: tuple[str, ...] = ()


@dataclass(frozen=True)
class LogSearchMatch:
    record: LogRecord
    score: float
    reason: str = ""


@dataclass(frozen=True)
class LlmLogSearchAnalysis:
    summary: str
    matches: list[tuple[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class LogSearchResult:
    query: str
    summary: str
    matches: list[LogSearchMatch]
    provider: str
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "summary": self.summary,
            "provider": self.provider,
            "warnings": list(self.warnings),
            "matches": [
                {
                    "score": match.score,
                    "reason": match.reason,
                    "record": match.record.to_dict(),
                }
                for match in self.matches
            ],
        }


class JsonlLogSource:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def read_recent(self, max_records: int = 500) -> list[LogRecord]:
        if max_records <= 0:
            return []
        if not self.path.exists():
            raise FileNotFoundError(f"Log file not found: {self.path}")

        records: deque[LogRecord] = deque(maxlen=max_records)
        with self.path.open("r", encoding="utf-8") as stream:
            for line in stream:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    records.append(LogRecord.from_dict(payload))
        return list(records)


class StructuredLlmLogSearchProvider:
    def __init__(self, name: str, client: Any) -> None:
        self.name = name
        self.client = client

    def analyze(
        self,
        query: str,
        candidates: list[LogSearchCandidate],
        *,
        top_k: int,
        response_language: str = "en",
    ) -> LlmLogSearchAnalysis:
        language_name = response_language_name(response_language)
        system_prompt = (
            "You analyze structured application logs. Return only JSON with "
            'shape {"summary": string, "matches": [{"id": string, "reason": string}]}. '
            f"Write the summary and match reasons in {language_name}. "
            "The summary is the bot answer for the user: explain what likely happened, "
            "what looks broken or suspicious, and what evidence is missing when the logs "
            "are inconclusive. Choose records that best support the answer. Do not invent ids."
        )
        user_prompt = json.dumps(
            {
                "problem": query,
                "response_language": normalize_response_language(response_language),
                "top_k": top_k,
                "candidate_logs": [compact_candidate(candidate) for candidate in candidates],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        payload = self.client.complete_json(system_prompt, user_prompt)
        summary = str(payload.get("summary") or "LLM did not provide a summary.")
        raw_matches = payload.get("matches") or []
        matches: list[tuple[str, str]] = []
        if isinstance(raw_matches, list):
            for item in raw_matches:
                if not isinstance(item, Mapping):
                    continue
                record_id = str(item.get("id") or "").strip()
                if not record_id:
                    continue
                matches.append((record_id, str(item.get("reason") or "")))
        return LlmLogSearchAnalysis(summary=summary, matches=matches[:top_k])


class DeepSeekLogSearchProvider(StructuredLlmLogSearchProvider):
    def __init__(self, client: Any) -> None:
        super().__init__("deepseek", client)


class SmartLogSearcher:
    def __init__(
        self,
        source: JsonlLogSource,
        *,
        llm_provider: LogSearchLlmProvider | None = None,
    ) -> None:
        self.source = source
        self.llm_provider = llm_provider

    def search(
        self,
        query: str,
        *,
        max_records: int = 500,
        candidate_count: int = 30,
        top_k: int = 5,
        response_language: str = "en",
    ) -> LogSearchResult:
        records = self.source.read_recent(max_records=max_records)
        candidates = rank_candidates(query, records)[: max(candidate_count, top_k)]
        if not candidates:
            return LogSearchResult(
                query=query,
                summary="No matching log records found.",
                matches=[],
                provider="local",
            )

        local_matches = [
            LogSearchMatch(record=candidate.record, score=candidate.score)
            for candidate in candidates[:top_k]
        ]
        if not self.llm_provider:
            return LogSearchResult(
                query=query,
                summary=build_local_summary(query, local_matches),
                matches=local_matches,
                provider="local",
            )

        try:
            analysis = self.llm_provider.analyze(
                query,
                candidates,
                top_k=top_k,
                response_language=response_language,
            )
        except LlmProviderError as exc:
            return LogSearchResult(
                query=query,
                summary=build_local_summary(query, local_matches),
                matches=local_matches,
                provider="local",
                warnings=(f"{self.llm_provider.name} failed: {exc}",),
            )

        by_id = {candidate.record.record_id: candidate for candidate in candidates}
        llm_matches: list[LogSearchMatch] = []
        seen: set[str] = set()
        for record_id, reason in analysis.matches:
            candidate = by_id.get(record_id)
            if not candidate or record_id in seen:
                continue
            seen.add(record_id)
            llm_matches.append(
                LogSearchMatch(record=candidate.record, score=candidate.score, reason=reason)
            )
        for candidate in candidates:
            if len(llm_matches) >= top_k:
                break
            if candidate.record.record_id not in seen:
                llm_matches.append(LogSearchMatch(record=candidate.record, score=candidate.score))
        return LogSearchResult(
            query=query,
            summary=analysis.summary,
            matches=llm_matches[:top_k],
            provider=self.llm_provider.name,
        )


def rank_candidates(query: str, records: Iterable[LogRecord]) -> list[LogSearchCandidate]:
    query_tokens = set(tokenize(query))
    phrase = query.casefold().strip()
    candidates: list[LogSearchCandidate] = []
    for record in records:
        text = searchable_text(record)
        text_folded = text.casefold()
        text_tokens = set(tokenize(text))
        hits = tuple(sorted(query_tokens & text_tokens))
        score = float(len(hits) * 10)
        if phrase and phrase in text_folded:
            score += 25
        if record.exception_type:
            score += 6
        if int(record.level) >= 40:
            score += 5
        elif int(record.level) >= 30:
            score += 2
        if score > 0:
            candidates.append(LogSearchCandidate(record=record, score=score, highlights=hits))
    return sorted(
        candidates,
        key=lambda candidate: (
            candidate.score,
            int(candidate.record.level),
            candidate.record.timestamp,
        ),
        reverse=True,
    )


def build_local_summary(query: str, matches: list[LogSearchMatch]) -> str:
    if not matches:
        return "No matching log records found."
    levels = ", ".join(sorted({match.record.level.name for match in matches}))
    return f"Found {len(matches)} candidate log record(s) for '{query}' using local ranking. Levels: {levels}."


def normalize_response_language(value: str | None) -> str:
    language = (value or "").strip().lower()
    if language in {"ru", "rus", "russian", "ru-ru"}:
        return "ru"
    return "en"


def response_language_name(value: str | None) -> str:
    return "Russian" if normalize_response_language(value) == "ru" else "English"


def compact_candidate(candidate: LogSearchCandidate) -> dict[str, Any]:
    record = candidate.record
    payload: dict[str, Any] = {
        "id": record.record_id,
        "timestamp": record.timestamp.isoformat(),
        "level": record.level.name,
        "logger": record.logger_name,
        "message": truncate(record.message, 400),
        "score": candidate.score,
        "highlights": list(candidate.highlights),
        "context": redact_value(record.context),
    }
    if record.exception_type:
        payload["exception"] = {
            "type": record.exception_type,
            "message": truncate(record.exception_message or "", 400),
            "stack_trace": truncate(record.stack_trace or "", 1200),
        }
    return payload


def searchable_text(record: LogRecord) -> str:
    parts = [
        record.record_id,
        record.logger_name,
        record.level.name,
        record.message,
        json.dumps(redact_value(record.context), ensure_ascii=False, sort_keys=True),
        " ".join(record.tags),
        record.exception_type or "",
        record.exception_message or "",
        record.stack_trace or "",
    ]
    return "\n".join(parts)


def tokenize(value: str) -> list[str]:
    return [match.group(0).casefold() for match in TOKEN_RE.finditer(value)]


def truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 3)] + "..."
