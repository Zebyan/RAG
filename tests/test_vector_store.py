from __future__ import annotations

from uuid import uuid4

import pytest
import time

from app.models import Chunk
from app.services.embedding_service import embed_text, embed_texts
from app.services.vector_store import (
    delete_namespace,
    delete_source,
    ensure_collection,
    search_chunks,
    upsert_chunks,
)


pytestmark = pytest.mark.integration

def wait_until_no_results(tenant_id: str, namespace_id: str, query: str, timeout_seconds: float = 5.0):
    deadline = time.time() + timeout_seconds
    query_vector = embed_text(query)

    while time.time() < deadline:
        results = search_chunks(
            tenant_id=tenant_id,
            namespaces=[namespace_id],
            query_vector=query_vector,
            top_k=5,
        )

        if results == []:
            return

        time.sleep(0.2)

    assert results == []

def test_qdrant_collection_can_be_created():
    ensure_collection()


def test_qdrant_upsert_and_search_chunk():
    tenant_id = f"tenant_{uuid4().hex}"
    namespace_id = f"namespace_{uuid4().hex}"
    source_id = f"source_{uuid4().hex}"
    chunk_id = str(uuid4())

    chunk = {
        "chunk_id": chunk_id,
        "content": "Articolul 15. Aporturile în numerar sunt obligatorii la constituirea oricărei forme de societate.",
        "article_number": "15",
        "section_title": None,
        "point_number": None,
        "page_number": None,
        "source_id": source_id,
        "source_url": "https://example.com/source",
        "source_title": "Legea 31/1990",
        "namespace_id": namespace_id,
        "score": 0.0,
        "metadata": {},
    }

    vector = embed_text(chunk["content"])

    upsert_chunks(
        tenant_id=tenant_id,
        chunks=[chunk],
        vectors=[vector],
    )

    query_vector = embed_text("Ce spune articolul 15 despre aporturile în numerar?")

    results = search_chunks(
        tenant_id=tenant_id,
        namespaces=[namespace_id],
        query_vector=query_vector,
        top_k=5,
    )

    assert results
    assert isinstance(results[0], Chunk)
    assert results[0].article_number == "15"
    assert results[0].namespace_id == namespace_id
    assert "Aporturile în numerar" in results[0].content


def test_qdrant_search_respects_tenant_isolation():
    tenant_a = f"tenant_a_{uuid4().hex}"
    tenant_b = f"tenant_b_{uuid4().hex}"
    namespace_id = f"namespace_{uuid4().hex}"
    source_id = f"source_{uuid4().hex}"

    chunk = {
        "chunk_id": str(uuid4()),
        "content": "Articolul 16. Aporturile în natură trebuie să fie evaluabile din punct de vedere economic.",
        "article_number": "16",
        "section_title": None,
        "point_number": None,
        "page_number": None,
        "source_id": source_id,
        "source_url": "https://example.com/source",
        "source_title": "Legea 31/1990",
        "namespace_id": namespace_id,
        "score": 0.0,
        "metadata": {},
    }

    vector = embed_text(chunk["content"])

    upsert_chunks(
        tenant_id=tenant_a,
        chunks=[chunk],
        vectors=[vector],
    )

    query_vector = embed_text("Ce spune articolul 16 despre aporturile în natură?")

    results = search_chunks(
        tenant_id=tenant_b,
        namespaces=[namespace_id],
        query_vector=query_vector,
        top_k=5,
    )

    assert results == []


def test_qdrant_delete_source_removes_points():
    tenant_id = f"tenant_{uuid4().hex}"
    namespace_id = f"namespace_{uuid4().hex}"
    source_id = f"source_{uuid4().hex}"

    chunk = {
        "chunk_id": str(uuid4()),
        "content": "Articolul 15. Aporturile în numerar sunt obligatorii.",
        "article_number": "15",
        "section_title": None,
        "point_number": None,
        "page_number": None,
        "source_id": source_id,
        "source_url": "https://example.com/source",
        "source_title": "Legea 31/1990",
        "namespace_id": namespace_id,
        "score": 0.0,
        "metadata": {},
    }

    vector = embed_text(chunk["content"])

    upsert_chunks(tenant_id=tenant_id, chunks=[chunk], vectors=[vector])

    delete_source(
        tenant_id=tenant_id,
        namespace_id=namespace_id,
        source_id=source_id,
    )

    wait_until_no_results(
    tenant_id=tenant_id,
    namespace_id=namespace_id,
    query="aporturile în numerar",
)


def test_qdrant_delete_namespace_removes_points():
    tenant_id = f"tenant_{uuid4().hex}"
    namespace_id = f"namespace_{uuid4().hex}"
    source_id = f"source_{uuid4().hex}"

    chunks = [
        {
            "chunk_id": str(uuid4()),
            "content": "Articolul 15. Aporturile în numerar sunt obligatorii.",
            "article_number": "15",
            "section_title": None,
            "point_number": None,
            "page_number": None,
            "source_id": source_id,
            "source_url": "https://example.com/source",
            "source_title": "Legea 31/1990",
            "namespace_id": namespace_id,
            "score": 0.0,
            "metadata": {},
        },
        {
            "chunk_id": str(uuid4()),
            "content": "Articolul 16. Aporturile în natură trebuie să fie evaluabile.",
            "article_number": "16",
            "section_title": None,
            "point_number": None,
            "page_number": None,
            "source_id": source_id,
            "source_url": "https://example.com/source",
            "source_title": "Legea 31/1990",
            "namespace_id": namespace_id,
            "score": 0.0,
            "metadata": {},
        },
    ]

    vectors = embed_texts([chunk["content"] for chunk in chunks])

    upsert_chunks(tenant_id=tenant_id, chunks=chunks, vectors=vectors)

    delete_namespace(
        tenant_id=tenant_id,
        namespace_id=namespace_id,
    )

    wait_until_no_results(
    tenant_id=tenant_id,
    namespace_id=namespace_id,
    query="aporturi",
)