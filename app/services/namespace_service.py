from __future__ import annotations

import uuid

from app.config import settings
from app.errors import raise_error
from app.models import DeleteNamespaceResponse, NamespaceStats
from app.services import sqlite_store as store
from app.services import vector_store
from app.services.vector_store import delete_namespace as delete_namespace_vectors


def get_namespace_stats_data(
    tenant_id: str,
    request_id: str,
    namespace_id: str,
) -> NamespaceStats:
    if not store.namespace_exists(tenant_id, namespace_id):
        raise_error(
            404,
            "namespace_not_found",
            f"Namespace '{namespace_id}' has no indexed content.",
            request_id=request_id,
            details={"namespace_id": namespace_id},
        )

    stats = store.get_ns_stats(tenant_id, namespace_id)

    if not stats:
        stats = {
            "namespace_id": namespace_id,
            "chunk_count": 0,
            "source_count": 0,
            "total_tokens_indexed": 0,
            "last_ingested_at": None,
            "embedding_model": settings.embedding_model,
            "embedding_dim": settings.embedding_dim,
        }

    return NamespaceStats(**stats)


def delete_source_data(
    tenant_id: str,
    request_id: str,
    namespace_id: str,
    source_id: str,
) -> None:
    if not store.source_exists(tenant_id, namespace_id, source_id):
        raise_error(
            404,
            "not_found",
            "Source not found.",
            request_id=request_id,
            details={
                "namespace_id": namespace_id,
                "source_id": source_id,
            },
        )

    store.delete_source(tenant_id, namespace_id, source_id)

    if settings.vector_store.lower() == "qdrant":
        vector_store.delete_source(
            tenant_id=tenant_id,
            namespace_id=namespace_id,
            source_id=source_id,
        )


def delete_namespace_data(
    tenant_id: str,
    namespace_id: str,
    request_id: str | None = None,
) -> DeleteNamespaceResponse:
    if not store.namespace_exists(tenant_id, namespace_id):
        raise_error(
            404,
            "namespace_not_found",
            f"Namespace not found: {namespace_id}",
            request_id=request_id,
            details={"namespace_id": namespace_id},
        )

    store.delete_namespace(
        tenant_id=tenant_id,
        namespace_id=namespace_id,
    )

    if settings.vector_store.lower() == "qdrant":
        delete_namespace_vectors(
            tenant_id=tenant_id,
            namespace_id=namespace_id,
        )

    return DeleteNamespaceResponse(
        job_id=f"del_{uuid.uuid4().hex[:12]}",
        status="queued",
        sla="24h",
    )