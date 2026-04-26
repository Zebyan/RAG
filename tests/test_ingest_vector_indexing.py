from __future__ import annotations

from uuid import uuid4

from app.services.embedding_service import embed_text
from app.services.vector_store import search_chunks


def test_ingest_indexes_chunks_into_qdrant(client, auth_headers):
    namespace_id = f"vector_ingest_namespace_{uuid4().hex}"
    source_id = f"s_vector_ingest_{uuid4().hex}"

    ingest_headers = {
        **auth_headers,
        "Idempotency-Key": str(uuid4()),
    }

    ingest_response = client.post(
        "/v1/ingest",
        headers=ingest_headers,
        json={
            "namespace_id": namespace_id,
            "source_id": source_id,
            "source_type": "url",
            "url": "https://example.com/vector-ingest",
            "mime_type_hint": "text/plain",
            "metadata": {
                "source_title": "Legea 31/1990 privind societățile comerciale",
                "text": (
                    "Articolul 15.\n"
                    "Aporturile în numerar sunt obligatorii la constituirea oricărei forme de societate.\n\n"
                    "Articolul 16.\n"
                    "Aporturile în natură trebuie să fie evaluabile din punct de vedere economic."
                ),
            },
        },
    )

    assert ingest_response.status_code == 202

    query_vector = embed_text("Ce spune legea despre aporturile în numerar?")

    results = search_chunks(
        tenant_id=auth_headers["X-Tenant-ID"],
        namespaces=[namespace_id],
        query_vector=query_vector,
        top_k=5,
    )

    assert results
    assert results[0].namespace_id == namespace_id
    assert results[0].source_id == source_id
    assert any(result.article_number == "15" for result in results)

def test_delete_source_removes_qdrant_vectors(client, auth_headers):
    namespace_id = f"vector_delete_namespace_{uuid4().hex}"
    source_id = f"s_vector_delete_{uuid4().hex}"

    ingest_headers = {
        **auth_headers,
        "Idempotency-Key": str(uuid4()),
    }

    ingest_response = client.post(
        "/v1/ingest",
        headers=ingest_headers,
        json={
            "namespace_id": namespace_id,
            "source_id": source_id,
            "source_type": "url",
            "url": "https://example.com/vector-delete",
            "mime_type_hint": "text/plain",
            "metadata": {
                "source_title": "Legea 31/1990 privind societățile comerciale",
                "text": "Articolul 15. Aporturile în numerar sunt obligatorii.",
            },
        },
    )

    assert ingest_response.status_code == 202

    delete_response = client.delete(
        f"/v1/namespaces/{namespace_id}/sources/{source_id}",
        headers=auth_headers,
    )

    assert delete_response.status_code == 204

    query_vector = embed_text("aporturile în numerar")

    results = search_chunks(
        tenant_id=auth_headers["X-Tenant-ID"],
        namespaces=[namespace_id],
        query_vector=query_vector,
        top_k=5,
    )

    assert results == []