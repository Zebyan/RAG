from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

from app.config import settings
from app.errors import raise_error
from app.models import IngestAcceptedResponse, IngestJobStatus, IngestProgress, IngestRequest
from app.services import sqlite_store as store
from app.services.legal_chunker import chunk_legal_text
from app.services.embedding_service import embed_texts
from app.services import vector_store
from app.services.url_fetcher import UrlFetchError, fetch_url_document

ALLOWED_MIME_TYPES = {"text/html", "application/pdf", "text/plain", "text/markdown"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_body_hash(request: IngestRequest) -> str:
    body = request.model_dump(mode="json", exclude_none=True)
    encoded = json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

def _extract_article_number(text: str) -> str | None:
    match = re.search(
        r"(?im)^\s*(?:Articolul|Art\.?)\s+([0-9]+(?:\^[0-9]+)?|[IVXLCDM]+)\s*[\.\-–]?",
        text,
    )
    return match.group(1) if match else None

def _resolve_ingest_text_and_metadata(request: IngestRequest) -> tuple[str, dict]:
    """
    Resolve ingest text.

    Priority:
    1. metadata.text local fixture override
    2. source_type=url fetch + extract
    """
    metadata = dict(request.metadata or {})

    metadata_text = metadata.get("text")
    if isinstance(metadata_text, str) and metadata_text.strip():
        metadata["text_source"] = "metadata.text"
        return metadata_text, metadata

    if request.source_type == "url":
        if not request.url:
            raise ValueError("URL is required when source_type is url.")

        fetched = fetch_url_document(
            url=str(request.url),
            mime_type_hint=request.mime_type_hint,
        )

        metadata.update(fetched.extracted.metadata)
        metadata.update(fetched.metadata)
        metadata["text_source"] = "url_fetch"

        return fetched.extracted.text, metadata

    raise ValueError("No extractable text found for ingest request.")

def _index_chunks_in_vector_store(
    tenant_id: str,
    chunks: list[dict],
) -> None:
    """
    Index chunk embeddings into the configured vector store.

    For now:
      - VECTOR_STORE=qdrant -> embed and upsert into Qdrant
      - anything else -> skip vector indexing
    """
    if settings.vector_store.lower() != "qdrant":
        return

    if not chunks:
        return

    vectors = embed_texts([chunk["content"] for chunk in chunks])

    vector_store.upsert_chunks(
        tenant_id=tenant_id,
        chunks=chunks,
        vectors=vectors,
    )

def _chunk_text_by_articles(text: str) -> list[str]:
    """
    Split Romanian legal text into article-level chunks.

    Handles examples:
    - Articolul 15.
    - Art. 15
    - Articolul 15^1.
    - Art. II.
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()

    article_pattern = re.compile(
        r"(?im)^\s*(?:Articolul|Art\.?)\s+([0-9]+(?:\^[0-9]+)?|[IVXLCDM]+)\s*[\.\-–]?"
    )

    matches = list(article_pattern.finditer(normalized))

    if not matches:
        return [normalized] if normalized else []

    chunks: list[str] = []

    # Keep any preamble/title before the first article as part of first article.
    preamble = normalized[: matches[0].start()].strip()

    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(normalized)
        chunk = normalized[start:end].strip()

        if index == 0 and preamble:
            chunk = f"{preamble}\n\n{chunk}"

        if chunk:
            chunks.append(chunk)

    return chunks

def create_ingest_job(
    tenant_id: str,
    request_id: str,
    request: IngestRequest,
    idempotency_key: str,
) -> IngestAcceptedResponse:
    if request.source_type == "url" and not request.url:
        raise_error(422, "validation_error", "url is required when source_type='url'.", request_id=request_id)

    if request.mime_type_hint and request.mime_type_hint not in ALLOWED_MIME_TYPES:
        raise_error(
            415,
            "unsupported_media_type",
            f"Unsupported MIME type: {request.mime_type_hint}",
            request_id=request_id,
            details={"mime_type": request.mime_type_hint},
        )

    body_hash = _stable_body_hash(request)
    idem = store.get_idem_record(tenant_id, idempotency_key)
    if idem:
        if idem["body_hash"] != body_hash:
            raise_error(409, "duplicate_job", "Idempotency-Key reused with different body.", request_id=request_id)
        existing_job = store.get_job(tenant_id, idem["job_id"])
        if existing_job:
            return IngestAcceptedResponse(
                job_id=existing_job["job_id"],
                status=existing_job["status"],
                submitted_at=existing_job["submitted_at"],
                estimated_completion_at=existing_job.get("estimated_completion_at"),
            )

    job_id = f"j_{uuid.uuid4().hex[:12]}"
    submitted_at = utc_now()
    estimated_completion_at = (
        datetime.now(timezone.utc).replace(microsecond=0) + timedelta(minutes=5)
    ).isoformat().replace("+00:00", "Z")

    job = {
        "job_id": job_id,
        "namespace_id": request.namespace_id,
        "source_id": request.source_id,
        "status": "queued",
        "progress": {"stage": "queued", "percent": 0, "chunks_created": 0},
        "submitted_at": submitted_at,
        "estimated_completion_at": estimated_completion_at,
        "completed_at": None,
        "error": None,
    }

    store.set_job(tenant_id, job_id, job)
    store.set_idem_record(tenant_id, idempotency_key, job_id, body_hash)

    # MVP: process synchronously using metadata.text if provided.
    _process_ingest_synchronously(tenant_id, request, job)

    return IngestAcceptedResponse(
        job_id=job_id,
        status="queued",
        submitted_at=submitted_at,
        estimated_completion_at=estimated_completion_at,
    )


def _process_ingest_synchronously(
    tenant_id: str,
    request: IngestRequest,
    job: dict[str, Any],
) -> None:
    try:
        job["progress"] = {
            "stage": "extracting",
            "percent": 20,
            "chunks_created": 0,
        }
        store.set_job(tenant_id, job["job_id"], job)

        text, resolved_metadata = _resolve_ingest_text_and_metadata(request)

        if not text.strip():
            raise ValueError("Extracted document text is empty.")

        job["progress"] = {
            "stage": "chunking",
            "percent": 40,
            "chunks_created": 0,
        }
        store.set_job(tenant_id, job["job_id"], job)

        legal_chunks = chunk_legal_text(text)

        if not legal_chunks:
            raise ValueError("No chunks were created from the extracted document text.")

        chunk_ids: list[str] = []
        chunk_records: list[dict] = []

        for legal_chunk in legal_chunks:
            chunk_id = str(uuid.uuid4())
            chunk_ids.append(chunk_id)

            chunk_metadata = dict(resolved_metadata)
            chunk_metadata.update(legal_chunk.metadata)

            chunk_record = {
                "chunk_id": chunk_id,
                "content": legal_chunk.content[:4000],
                "article_number": legal_chunk.article_number,
                "section_title": legal_chunk.section_title,
                "point_number": legal_chunk.point_number,
                "page_number": legal_chunk.page_number,
                "source_id": request.source_id,
                "source_url": request.url,
                "source_title": resolved_metadata.get("source_title"),
                "namespace_id": request.namespace_id,
                "score": 0.0,
                "metadata": chunk_metadata,
            }

            chunk_records.append(chunk_record)

            store.set_chunk(
                tenant_id,
                chunk_id,
                chunk_record,
            )

        job["progress"] = {
            "stage": "embedding",
            "percent": 75,
            "chunks_created": len(chunk_ids),
        }
        store.set_job(tenant_id, job["job_id"], job)

        _index_chunks_in_vector_store(
            tenant_id=tenant_id,
            chunks=chunk_records,
        )

        store.register_source(
            tenant_id=tenant_id,
            namespace_id=request.namespace_id,
            source_id=request.source_id,
            chunk_ids=chunk_ids,
            meta=resolved_metadata,
        )

        completed_at = utc_now()

        job.update(
            {
                "status": "done",
                "progress": {
                    "stage": "indexing",
                    "percent": 100,
                    "chunks_created": len(chunk_ids),
                },
                "completed_at": completed_at,
                "error": None,
            }
        )
        store.set_job(tenant_id, job["job_id"], job)

        store.update_ns_stats(
            tenant_id,
            request.namespace_id,
            {
                "namespace_id": request.namespace_id,
                "chunk_count": len(chunk_ids),
                "source_count": 1,
                "total_tokens_indexed": sum(
                    len(chunk.content.split()) for chunk in legal_chunks
                ),
                "last_ingested_at": completed_at,
                "embedding_model": settings.embedding_model,
                "embedding_dim": settings.embedding_dim,
            },
        )

    except (ValueError, UrlFetchError) as exc:
        completed_at = utc_now()

        job.update(
            {
                "status": "failed",
                "progress": {
                    "stage": "failed",
                    "percent": 100,
                    "chunks_created": 0,
                },
                "completed_at": completed_at,
                "error": {
                    "code": "INGEST_FAILED",
                    "message": str(exc),
                },
            }
        )
        store.set_job(tenant_id, job["job_id"], job)


def get_ingest_job(tenant_id: str, request_id: str, job_id: str) -> IngestJobStatus:
    job = store.get_job(tenant_id, job_id)
    if not job:
        raise_error(404, "not_found", "Ingest job not found.", request_id=request_id, details={"job_id": job_id})

    return IngestJobStatus(
        job_id=job["job_id"],
        namespace_id=job["namespace_id"],
        source_id=job["source_id"],
        status=job["status"],
        progress=IngestProgress(**job["progress"]),
        submitted_at=job["submitted_at"],
        completed_at=job.get("completed_at"),
        error=job.get("error"),
    )
