from __future__ import annotations

from typing import Any
from uuid import UUID

from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.config import settings
from app.models import Chunk


def get_qdrant_client() -> QdrantClient:
    return QdrantClient(
        url=settings.qdrant_url,
        timeout=30.0,
        )


def ensure_collection() -> None:
    client = get_qdrant_client()
    collection_name = settings.qdrant_collection

    existing = client.get_collections()
    existing_names = {collection.name for collection in existing.collections}

    if collection_name in existing_names:
        return

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=settings.embedding_dim,
            distance=Distance.COSINE,
        ),
    )


def _point_id_from_chunk_id(chunk_id: str) -> str:
    """
    Qdrant point IDs can be UUID strings.
    Our chunk_id values are UUID strings, so validate and return them.
    """
    UUID(chunk_id)
    return chunk_id


def upsert_chunks(
    tenant_id: str,
    chunks: list[dict[str, Any]],
    vectors: list[list[float]],
) -> None:
    if not chunks:
        return

    if len(chunks) != len(vectors):
        raise ValueError("chunks and vectors must have the same length")

    ensure_collection()

    points: list[PointStruct] = []

    for chunk, vector in zip(chunks, vectors):
        chunk_id = chunk["chunk_id"]

        payload = {
            "tenant_id": tenant_id,
            "namespace_id": chunk["namespace_id"],
            "source_id": chunk["source_id"],
            "source_url": chunk.get("source_url"),
            "source_title": chunk.get("source_title"),
            "article_number": chunk.get("article_number"),
            "section_title": chunk.get("section_title"),
            "point_number": chunk.get("point_number"),
            "page_number": chunk.get("page_number"),
            "content": chunk["content"],
            "metadata": chunk.get("metadata", {}),
        }

        points.append(
            PointStruct(
                id=_point_id_from_chunk_id(chunk_id),
                vector=vector,
                payload=payload,
            )
        )

    client = get_qdrant_client()
    client.upsert(
        collection_name=settings.qdrant_collection,
        points=points,
        wait=True,
    )


def _tenant_namespace_filter(tenant_id: str, namespaces: list[str]) -> Filter:
    return Filter(
        must=[
            FieldCondition(
                key="tenant_id",
                match=MatchValue(value=tenant_id),
            ),
            FieldCondition(
                key="namespace_id",
                match=MatchAny(any=namespaces),
            ),
        ]
    )


def search_chunks(
    tenant_id: str,
    namespaces: list[str],
    query_vector: list[float],
    top_k: int,
) -> list[Chunk]:
    if not namespaces:
        return []

    ensure_collection()

    client = get_qdrant_client()

    results = client.search(
        collection_name=settings.qdrant_collection,
        query_vector=query_vector,
        query_filter=_tenant_namespace_filter(tenant_id, namespaces),
        limit=top_k,
        with_payload=True,
        with_vectors=False,
    )

    chunks: list[Chunk] = []

    for result in results:
        payload = result.payload or {}

        chunk = Chunk(
            chunk_id=str(result.id),
            content=str(payload.get("content", "")),
            article_number=payload.get("article_number"),
            section_title=payload.get("section_title"),
            point_number=payload.get("point_number"),
            page_number=payload.get("page_number"),
            source_id=str(payload.get("source_id", "")),
            source_url=payload.get("source_url"),
            source_title=payload.get("source_title"),
            namespace_id=str(payload.get("namespace_id", "")),
            score=float(result.score),
            metadata=payload.get("metadata") or {},
        )

        chunks.append(chunk)

    return chunks


def delete_source(tenant_id: str, namespace_id: str, source_id: str) -> None:
    ensure_collection()

    client = get_qdrant_client()
    client.delete(
        collection_name=settings.qdrant_collection,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="tenant_id",
                    match=MatchValue(value=tenant_id),
                ),
                FieldCondition(
                    key="namespace_id",
                    match=MatchValue(value=namespace_id),
                ),
                FieldCondition(
                    key="source_id",
                    match=MatchValue(value=source_id),
                ),
            ]
        ),
        wait=False,
    )


def delete_namespace(tenant_id: str, namespace_id: str) -> None:
    ensure_collection()

    client = get_qdrant_client()
    client.delete(
        collection_name=settings.qdrant_collection,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="tenant_id",
                    match=MatchValue(value=tenant_id),
                ),
                FieldCondition(
                    key="namespace_id",
                    match=MatchValue(value=namespace_id),
                ),
            ]
        ),
        wait=False,
    )