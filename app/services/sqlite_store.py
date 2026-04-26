from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from threading import Lock
from typing import Any

from app.config import settings

_lock = Lock()
_started = time.monotonic()


def _db_path() -> Path:
    path = Path(settings.database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _lock:
        with _connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    tenant_id TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, job_id)
                );

                CREATE TABLE IF NOT EXISTS idempotency_keys (
                    tenant_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    body_hash TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, idempotency_key)
                );

                CREATE TABLE IF NOT EXISTS sources (
                    tenant_id TEXT NOT NULL,
                    namespace_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    chunk_ids_json TEXT NOT NULL,
                    meta_json TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, namespace_id, source_id)
                );

                CREATE TABLE IF NOT EXISTS chunks (
                    tenant_id TEXT NOT NULL,
                    chunk_id TEXT NOT NULL,
                    namespace_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, chunk_id)
                );

                CREATE TABLE IF NOT EXISTS namespace_stats (
                    tenant_id TEXT NOT NULL,
                    namespace_id TEXT NOT NULL,
                    stats_json TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, namespace_id)
                );
                """
            )


def reset_db() -> None:
    """
    Used by tests to keep each test isolated.
    Do not call this in production code.
    """
    with _lock:
        with _connect() as conn:
            conn.executescript(
                """
                DROP TABLE IF EXISTS jobs;
                DROP TABLE IF EXISTS idempotency_keys;
                DROP TABLE IF EXISTS sources;
                DROP TABLE IF EXISTS chunks;
                DROP TABLE IF EXISTS namespace_stats;
                """
            )
    init_db()


def uptime_seconds() -> int:
    return int(time.monotonic() - _started)


def set_job(tenant_id: str, job_id: str, data: dict[str, Any]) -> None:
    init_db()
    with _lock:
        with _connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO jobs (tenant_id, job_id, data_json)
                VALUES (?, ?, ?)
                """,
                (tenant_id, job_id, json.dumps(data, ensure_ascii=False)),
            )


def get_job(tenant_id: str, job_id: str) -> dict[str, Any] | None:
    init_db()
    with _lock:
        with _connect() as conn:
            row = conn.execute(
                """
                SELECT data_json FROM jobs
                WHERE tenant_id = ? AND job_id = ?
                """,
                (tenant_id, job_id),
            ).fetchone()

    if not row:
        return None

    return json.loads(row["data_json"])


def get_idem_record(tenant_id: str, key: str) -> dict[str, str] | None:
    init_db()
    with _lock:
        with _connect() as conn:
            row = conn.execute(
                """
                SELECT job_id, body_hash FROM idempotency_keys
                WHERE tenant_id = ? AND idempotency_key = ?
                """,
                (tenant_id, key),
            ).fetchone()

    if not row:
        return None

    return {
        "job_id": row["job_id"],
        "body_hash": row["body_hash"],
    }


def set_idem_record(tenant_id: str, key: str, job_id: str, body_hash: str) -> None:
    init_db()
    with _lock:
        with _connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO idempotency_keys
                    (tenant_id, idempotency_key, job_id, body_hash)
                VALUES (?, ?, ?, ?)
                """,
                (tenant_id, key, job_id, body_hash),
            )


def register_source(
    tenant_id: str,
    namespace_id: str,
    source_id: str,
    chunk_ids: list[str],
    meta: dict[str, Any],
) -> None:
    init_db()
    with _lock:
        with _connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sources
                    (tenant_id, namespace_id, source_id, chunk_ids_json, meta_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    tenant_id,
                    namespace_id,
                    source_id,
                    json.dumps(chunk_ids, ensure_ascii=False),
                    json.dumps(meta, ensure_ascii=False),
                ),
            )


def source_exists(tenant_id: str, namespace_id: str, source_id: str) -> bool:
    init_db()
    with _lock:
        with _connect() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM sources
                WHERE tenant_id = ? AND namespace_id = ? AND source_id = ?
                """,
                (tenant_id, namespace_id, source_id),
            ).fetchone()

    return row is not None


def namespace_exists(tenant_id: str, namespace_id: str) -> bool:
    init_db()
    with _lock:
        with _connect() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM sources
                WHERE tenant_id = ? AND namespace_id = ?
                LIMIT 1
                """,
                (tenant_id, namespace_id),
            ).fetchone()

    return row is not None


def set_chunk(tenant_id: str, chunk_id: str, data: dict[str, Any]) -> None:
    init_db()
    namespace_id = data["namespace_id"]
    source_id = data["source_id"]

    with _lock:
        with _connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO chunks
                    (tenant_id, chunk_id, namespace_id, source_id, data_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    tenant_id,
                    chunk_id,
                    namespace_id,
                    source_id,
                    json.dumps(data, ensure_ascii=False),
                ),
            )


def list_chunks(tenant_id: str, namespaces: list[str]) -> list[dict[str, Any]]:
    init_db()

    if not namespaces:
        return []

    placeholders = ",".join("?" for _ in namespaces)

    query = f"""
        SELECT data_json FROM chunks
        WHERE tenant_id = ?
        AND namespace_id IN ({placeholders})
    """

    with _lock:
        with _connect() as conn:
            rows = conn.execute(query, [tenant_id, *namespaces]).fetchall()

    return [json.loads(row["data_json"]) for row in rows]


def delete_source(tenant_id: str, namespace_id: str, source_id: str) -> list[str]:
    init_db()

    with _lock:
        with _connect() as conn:
            row = conn.execute(
                """
                SELECT chunk_ids_json FROM sources
                WHERE tenant_id = ? AND namespace_id = ? AND source_id = ?
                """,
                (tenant_id, namespace_id, source_id),
            ).fetchone()

            if not row:
                return []

            chunk_ids = json.loads(row["chunk_ids_json"])

            conn.execute(
                """
                DELETE FROM chunks
                WHERE tenant_id = ? AND namespace_id = ? AND source_id = ?
                """,
                (tenant_id, namespace_id, source_id),
            )

            conn.execute(
                """
                DELETE FROM sources
                WHERE tenant_id = ? AND namespace_id = ? AND source_id = ?
                """,
                (tenant_id, namespace_id, source_id),
            )

            _recompute_namespace_stats_locked(conn, tenant_id, namespace_id)

    return chunk_ids


def delete_namespace(tenant_id: str, namespace_id: str) -> list[str]:
    init_db()

    with _lock:
        with _connect() as conn:
            rows = conn.execute(
                """
                SELECT chunk_ids_json FROM sources
                WHERE tenant_id = ? AND namespace_id = ?
                """,
                (tenant_id, namespace_id),
            ).fetchall()

            deleted_chunk_ids: list[str] = []
            for row in rows:
                deleted_chunk_ids.extend(json.loads(row["chunk_ids_json"]))

            conn.execute(
                """
                DELETE FROM chunks
                WHERE tenant_id = ? AND namespace_id = ?
                """,
                (tenant_id, namespace_id),
            )

            conn.execute(
                """
                DELETE FROM sources
                WHERE tenant_id = ? AND namespace_id = ?
                """,
                (tenant_id, namespace_id),
            )

            conn.execute(
                """
                DELETE FROM namespace_stats
                WHERE tenant_id = ? AND namespace_id = ?
                """,
                (tenant_id, namespace_id),
            )

    return deleted_chunk_ids


def update_ns_stats(tenant_id: str, namespace_id: str, stats: dict[str, Any]) -> None:
    init_db()
    with _lock:
        with _connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO namespace_stats
                    (tenant_id, namespace_id, stats_json)
                VALUES (?, ?, ?)
                """,
                (
                    tenant_id,
                    namespace_id,
                    json.dumps(stats, ensure_ascii=False),
                ),
            )


def get_ns_stats(tenant_id: str, namespace_id: str) -> dict[str, Any] | None:
    init_db()
    with _lock:
        with _connect() as conn:
            row = conn.execute(
                """
                SELECT stats_json FROM namespace_stats
                WHERE tenant_id = ? AND namespace_id = ?
                """,
                (tenant_id, namespace_id),
            ).fetchone()

    if not row:
        return None

    return json.loads(row["stats_json"])


def _recompute_namespace_stats_locked(conn: sqlite3.Connection, tenant_id: str, namespace_id: str) -> None:
    chunk_count = conn.execute(
        """
        SELECT COUNT(*) AS count FROM chunks
        WHERE tenant_id = ? AND namespace_id = ?
        """,
        (tenant_id, namespace_id),
    ).fetchone()["count"]

    source_count = conn.execute(
        """
        SELECT COUNT(*) AS count FROM sources
        WHERE tenant_id = ? AND namespace_id = ?
        """,
        (tenant_id, namespace_id),
    ).fetchone()["count"]

    if source_count == 0:
        conn.execute(
            """
            DELETE FROM namespace_stats
            WHERE tenant_id = ? AND namespace_id = ?
            """,
            (tenant_id, namespace_id),
        )
        return

    existing = conn.execute(
        """
        SELECT stats_json FROM namespace_stats
        WHERE tenant_id = ? AND namespace_id = ?
        """,
        (tenant_id, namespace_id),
    ).fetchone()

    stats = json.loads(existing["stats_json"]) if existing else {}
    stats["namespace_id"] = namespace_id
    stats["chunk_count"] = chunk_count
    stats["source_count"] = source_count

    conn.execute(
        """
        INSERT OR REPLACE INTO namespace_stats
            (tenant_id, namespace_id, stats_json)
        VALUES (?, ?, ?)
        """,
        (tenant_id, namespace_id, json.dumps(stats, ensure_ascii=False)),
    )