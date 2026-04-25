from __future__ import annotations

import time
from threading import Lock
from typing import Any

_lock = Lock()
_started = time.monotonic()

_jobs: dict[tuple[str, str], dict[str, Any]] = {}
_idempotency: dict[tuple[str, str], dict[str, str]] = {}
_sources: dict[tuple[str, str, str], dict[str, Any]] = {}
_chunks: dict[tuple[str, str], dict[str, Any]] = {}
_namespace_stats: dict[tuple[str, str], dict[str, Any]] = {}


def uptime_seconds() -> int:
    return int(time.monotonic() - _started)


def set_job(tenant_id: str, job_id: str, data: dict[str, Any]) -> None:
    with _lock:
        _jobs[(tenant_id, job_id)] = data


def get_job(tenant_id: str, job_id: str) -> dict[str, Any] | None:
    with _lock:
        return _jobs.get((tenant_id, job_id))


def get_idem_record(tenant_id: str, key: str) -> dict[str, str] | None:
    with _lock:
        return _idempotency.get((tenant_id, key))


def set_idem_record(tenant_id: str, key: str, job_id: str, body_hash: str) -> None:
    with _lock:
        _idempotency[(tenant_id, key)] = {"job_id": job_id, "body_hash": body_hash}


def register_source(tenant_id: str, namespace_id: str, source_id: str, chunk_ids: list[str], meta: dict[str, Any]) -> None:
    with _lock:
        _sources[(tenant_id, namespace_id, source_id)] = {
            "chunk_ids": chunk_ids,
            "meta": meta,
        }


def source_exists(tenant_id: str, namespace_id: str, source_id: str) -> bool:
    with _lock:
        return (tenant_id, namespace_id, source_id) in _sources


def namespace_exists(tenant_id: str, namespace_id: str) -> bool:
    with _lock:
        return any(t == tenant_id and ns == namespace_id for (t, ns, _source_id) in _sources)


def set_chunk(tenant_id: str, chunk_id: str, data: dict[str, Any]) -> None:
    with _lock:
        _chunks[(tenant_id, chunk_id)] = data


def list_chunks(tenant_id: str, namespaces: list[str]) -> list[dict[str, Any]]:
    with _lock:
        return [
            chunk
            for (t, _chunk_id), chunk in _chunks.items()
            if t == tenant_id and chunk.get("namespace_id") in namespaces
        ]


def delete_source(tenant_id: str, namespace_id: str, source_id: str) -> list[str]:
    with _lock:
        source = _sources.pop((tenant_id, namespace_id, source_id), None)
        if not source:
            return []

        chunk_ids = source["chunk_ids"]
        for chunk_id in chunk_ids:
            _chunks.pop((tenant_id, chunk_id), None)

        return chunk_ids


def delete_namespace(tenant_id: str, namespace_id: str) -> list[str]:
    with _lock:
        deleted_chunk_ids: list[str] = []

        source_keys = [
            key for key in _sources
            if key[0] == tenant_id and key[1] == namespace_id
        ]

        for key in source_keys:
            source = _sources.pop(key)
            deleted_chunk_ids.extend(source["chunk_ids"])

        for chunk_id in deleted_chunk_ids:
            _chunks.pop((tenant_id, chunk_id), None)

        _namespace_stats.pop((tenant_id, namespace_id), None)
        return deleted_chunk_ids


def update_ns_stats(tenant_id: str, namespace_id: str, stats: dict[str, Any]) -> None:
    with _lock:
        _namespace_stats[(tenant_id, namespace_id)] = stats


def get_ns_stats(tenant_id: str, namespace_id: str) -> dict[str, Any] | None:
    with _lock:
        return _namespace_stats.get((tenant_id, namespace_id))
