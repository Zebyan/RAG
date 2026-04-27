def test_namespace_stats_not_found(client, auth_headers):
    response = client.get(
        "/v1/namespaces/unknown_namespace/stats",
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "namespace_not_found"

def test_namespace_stats_after_ingest(client, auth_headers):
    ingest_headers = {
        **auth_headers,
        "Idempotency-Key": "34343434-3434-4343-8343-343434343434",
    }

    ingest = client.post(
        "/v1/ingest",
        headers=ingest_headers,
        json={
            "namespace_id": "legea_31_1990",
            "source_id": "s_stats_test",
            "source_type": "url",
            "url": "https://example.com/stats",
            "mime_type_hint": "text/plain",
            "metadata": {
                "text": "Articolul 15. Aporturile în numerar sunt obligatorii la constituirea oricărei forme de societate."
            },
        },
    )
    assert ingest.status_code == 202

    stats = client.get("/v1/namespaces/legea_31_1990/stats", headers=auth_headers)

    assert stats.status_code == 200
    data = stats.json()
    assert data["namespace_id"] == "legea_31_1990"
    assert data["chunk_count"] >= 1
    assert data["source_count"] >= 1

def test_delete_source_removes_chunks(client, auth_headers):
    namespace_id = "delete_source_namespace_test"
    source_id = "s_delete_source_test"

    ingest_headers = {
        **auth_headers,
        "Idempotency-Key": "45454545-4545-4454-8454-454545454545",
    }

    ingest = client.post(
        "/v1/ingest",
        headers=ingest_headers,
        json={
            "namespace_id": namespace_id,
            "source_id": source_id,
            "source_type": "url",
            "url": "https://example.com/delete-source",
            "mime_type_hint": "text/plain",
            "metadata": {
                "text": "Articolul 15. Aporturile în numerar sunt obligatorii la constituirea oricărei forme de societate."
            },
        },
    )
    assert ingest.status_code == 202

    delete_response = client.delete(
        f"/v1/namespaces/{namespace_id}/sources/{source_id}",
        headers=auth_headers,
    )
    assert delete_response.status_code == 204

    query_response = client.post(
        "/v1/query",
        headers=auth_headers,
        json={
            "question": "Ce spune articolul 15?",
            "language": "ro",
            "namespaces": [namespace_id],
            "top_k": 5,
            "hint_article_number": "15",
            "include_answer": True,
        },
    )

    data = query_response.json()
    assert data["answer"] is None
    assert data["citations"] == []
    assert data["confidence"] == 0.0

def test_delete_namespace_returns_202(client, auth_headers):
    namespace_id = "namespace_to_delete"
    source_id = "source_to_delete"

    ingest_headers = {
        **auth_headers,
        "Idempotency-Key": "12121212-3434-4565-8565-121212121212",
    }

    ingest_response = client.post(
        "/v1/ingest",
        headers=ingest_headers,
        json={
            "namespace_id": namespace_id,
            "source_id": source_id,
            "source_type": "url",
            "url": "https://example.com/delete-namespace",
            "mime_type_hint": "text/plain",
            "metadata": {
                "source_title": "Delete Namespace Test",
                "text": "Articolul 15. Aporturile în numerar sunt obligatorii.",
            },
        },
    )

    assert ingest_response.status_code == 202

    response = client.delete(
        f"/v1/namespaces/{namespace_id}",
        headers=auth_headers,
    )

    assert response.status_code == 202

    data = response.json()

    assert data["job_id"].startswith("del_")
    assert data["status"] == "queued"
    assert data["sla"] == "24h"

def test_deleted_namespace_is_no_longer_queryable(client, auth_headers):
    namespace_id = "namespace_deleted_verify"
    source_id = "source_deleted_verify"

    ingest_headers = {
        **auth_headers,
        "Idempotency-Key": "23232323-3434-4565-8565-232323232323",
    }

    ingest_response = client.post(
        "/v1/ingest",
        headers=ingest_headers,
        json={
            "namespace_id": namespace_id,
            "source_id": source_id,
            "source_type": "url",
            "url": "https://example.com/delete-namespace-verify",
            "mime_type_hint": "text/plain",
            "metadata": {
                "source_title": "Delete Namespace Verify",
                "text": "Articolul 15. Aporturile în numerar sunt obligatorii.",
            },
        },
    )

    assert ingest_response.status_code == 202

    delete_response = client.delete(
        f"/v1/namespaces/{namespace_id}",
        headers=auth_headers,
    )

    assert delete_response.status_code == 202

    query_response = client.post(
        "/v1/query",
        headers=auth_headers,
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