"""PostgreSQL storage and scoped API keys for the hosted ingest service."""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime
from typing import Any

from .records import LogRecord


SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_logger_api_keys (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL,
    key_prefix TEXT NOT NULL,
    key_hash TEXT NOT NULL UNIQUE,
    scopes TEXT[] NOT NULL,
    project TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at TIMESTAMPTZ,
    CONSTRAINT ai_logger_api_keys_scopes CHECK (scopes <@ ARRAY['ingest','read']::text[])
);
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
    def __init__(self, database_url: str) -> None:
        if not database_url:
            raise ValueError("DATABASE_URL is required")
        self.database_url = database_url

    def _connect(self):
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("Install ai-logger[postgres] for PostgreSQL support") from exc
        # Hosted credentials and log payloads must never travel over plain TCP.
        return psycopg.connect(self.database_url, connect_timeout=5, sslmode="require")

    def ensure_schema(self) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(SCHEMA)

    def ping(self) -> bool:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                return cursor.fetchone()[0] == 1

    def create_key(self, name: str, scopes: list[str], project: str | None = None) -> dict[str, Any]:
        if not isinstance(name, str) or not isinstance(scopes, list) or not all(isinstance(s, str) for s in scopes):
            raise ValueError("Invalid key request")
        if project is not None and not isinstance(project, str):
            raise ValueError("Invalid project")
        name = name.strip()
        scopes = sorted(set(scopes))
        project = project.strip() if project else None
        if not name or len(name) > 100 or not scopes or not set(scopes) <= {"ingest", "read"}:
            raise ValueError("Name and valid scopes (ingest, read) are required")
        if project is not None and (not project or len(project) > 100):
            raise ValueError("Invalid project")
        key = "ail_" + secrets.token_urlsafe(32)
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO ai_logger_api_keys (name, key_prefix, key_hash, scopes, project)
                       VALUES (%s, %s, %s, %s, %s) RETURNING id, created_at""",
                    (name, key[:12], digest, scopes, project),
                )
                key_id, created_at = cursor.fetchone()
        return {"id": key_id, "name": name, "key": key, "key_prefix": key[:12],
                "scopes": scopes, "project": project, "created_at": created_at.isoformat()}

    def list_keys(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""SELECT id, name, key_prefix, scopes, project, created_at, revoked_at
                                  FROM ai_logger_api_keys ORDER BY id DESC""")
                return [dict(id=row[0], name=row[1], key_prefix=row[2], scopes=row[3],
                             project=row[4], created_at=row[5].isoformat(),
                             revoked_at=row[6].isoformat() if row[6] else None)
                        for row in cursor.fetchall()]

    def revoke_key(self, key_id: int) -> bool:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""UPDATE ai_logger_api_keys SET revoked_at=now()
                                  WHERE id=%s AND revoked_at IS NULL RETURNING id""", (key_id,))
                return cursor.fetchone() is not None

    def authorize(self, key: str, scope: str) -> str | None | bool:
        if not key or not key.startswith("ail_"):
            return False
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""SELECT scopes, project FROM ai_logger_api_keys
                                  WHERE key_hash=%s AND revoked_at IS NULL""", (digest,))
                row = cursor.fetchone()
        if not row or scope not in row[0]:
            return False
        return row[1] or ""

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
