"""PostgreSQL storage for the hosted ingest service."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from .records import LogRecord


SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_logger_records (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project TEXT NOT NULL,
    record_id TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    level TEXT NOT NULL,
    logger TEXT NOT NULL,
    payload JSONB NOT NULL,
    UNIQUE (project, record_id)
);
CREATE INDEX IF NOT EXISTS ai_logger_records_recent_idx
    ON ai_logger_records (project, occurred_at DESC, id DESC);
"""


class PostgresStore:
    def __init__(self, database_url: str, *, ssl: bool = False) -> None:
        if not database_url:
            raise ValueError("DATABASE_URL is required")
        self.database_url = database_url
        self.ssl = ssl

    def _connect(self):
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("Install ai-logger[postgres] for PostgreSQL support") from exc
        return psycopg.connect(
            self.database_url,
            connect_timeout=5,
            sslmode="require" if self.ssl else "disable",
        )

    def ensure_schema(self) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(SCHEMA)

    def ping(self) -> bool:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                return cursor.fetchone()[0] == 1

    def insert_records(self, records: list[LogRecord]) -> list[LogRecord]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                inserted: list[LogRecord] = []
                for record in records:
                    project = str(record.context["project"])
                    cursor.execute(
                        """INSERT INTO ai_logger_records
                           (project, record_id, occurred_at, level, logger, payload)
                           VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                           ON CONFLICT (project, record_id) DO NOTHING""",
                        (project, record.record_id, record.timestamp, record.level.name,
                         record.logger_name, json.dumps(record.to_dict(), ensure_ascii=False)),
                    )
                    if cursor.rowcount:
                        inserted.append(record)
        return inserted

    def read_records(self, *, project: str | None, levels: set[str] | None,
                     since: datetime | None, limit: int) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if project:
            conditions.append("project=%s")
            params.append(project)
        if levels:
            conditions.append("level=ANY(%s)")
            params.append(list(levels))
        if since:
            conditions.append("occurred_at >= %s")
            params.append(since)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        params.append(max(1, min(limit, 500)))
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT payload FROM ai_logger_records" + where +
                               " ORDER BY occurred_at DESC, id DESC LIMIT %s", params)
                return [row[0] for row in cursor.fetchall()]
