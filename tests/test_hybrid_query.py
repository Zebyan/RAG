from __future__ import annotations

from uuid import uuid4


def test_query_uses_hybrid_qdrant_retrieval_without_article_hint(client, auth_headers):
    namespace_id = f"hybrid_query_namespace_{uuid4().hex}"
    source_id = f"s_hybrid_query_{uuid4().hex}"

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
            "url": "https://example.com/hybrid-query",
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

    query_response = client.post(
        "/v1/query",
        headers=auth_headers,
        json={
            "question": "Ce prevede legea despre evaluarea aporturilor?",
            "language": "ro",
            "namespaces": [namespace_id],
            "top_k": 5,
            "include_answer": True,
        },
    )

    assert query_response.status_code == 200

    data = query_response.json()

    assert data["retrieval_strategy"] == "hybrid_qdrant_article_keyword"
    assert data["answer"] is not None
    assert data["citations"]
    assert any(
        citation["chunk"]["article_number"] == "16"
        for citation in data["citations"]
    )


def test_hybrid_query_still_prioritizes_exact_article_hint(client, auth_headers):
    namespace_id = f"hybrid_exact_article_namespace_{uuid4().hex}"
    source_id = f"s_hybrid_exact_{uuid4().hex}"

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
            "url": "https://example.com/hybrid-exact",
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

    query_response = client.post(
        "/v1/query",
        headers=auth_headers,
        json={
            "question": "Ce spune articolul 15 despre aporturi?",
            "language": "ro",
            "namespaces": [namespace_id],
            "top_k": 5,
            "hint_article_number": "15",
            "include_answer": True,
        },
    )

    assert query_response.status_code == 200

    data = query_response.json()

    assert data["answer"] is not None
    assert data["citations"][0]["chunk"]["article_number"] == "15"
    assert "Aporturile în numerar" in data["citations"][0]["chunk"]["content"]


def test_hybrid_query_respects_cross_tenant_isolation(client):
    namespace_id = f"hybrid_tenant_namespace_{uuid4().hex}"
    source_id = f"s_hybrid_tenant_{uuid4().hex}"

    tenant_a_headers = {
        "Authorization": "Bearer test-api-key",
        "X-Request-ID": str(uuid4()),
        "X-Tenant-ID": "hybrid-tenant-a",
    }

    tenant_a_ingest_headers = {
        **tenant_a_headers,
        "Idempotency-Key": str(uuid4()),
    }

    tenant_b_headers = {
        "Authorization": "Bearer test-api-key",
        "X-Request-ID": str(uuid4()),
        "X-Tenant-ID": "hybrid-tenant-b",
    }

    ingest_response = client.post(
        "/v1/ingest",
        headers=tenant_a_ingest_headers,
        json={
            "namespace_id": namespace_id,
            "source_id": source_id,
            "source_type": "url",
            "url": "https://example.com/hybrid-tenant",
            "mime_type_hint": "text/plain",
            "metadata": {
                "source_title": "Legea 31/1990 privind societățile comerciale",
                "text": "Articolul 15. Acest text aparține doar tenantului A.",
            },
        },
    )

    assert ingest_response.status_code == 202

    query_response = client.post(
        "/v1/query",
        headers=tenant_b_headers,
        json={
            "question": "Ce spune articolul 15?",
            "language": "ro",
            "namespaces": [namespace_id],
            "top_k": 5,
            "hint_article_number": "15",
            "include_answer": True,
        },
    )

    assert query_response.status_code == 200

    data = query_response.json()

    assert data["answer"] is None
    assert data["citations"] == []
    assert data["confidence"] == 0.0