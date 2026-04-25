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

def test_delete_namespace_removes_all_namespace_data(client, auth_headers):
    ingest_headers = {
        **auth_headers,
        "Idempotency-Key": "56565656-5656-4565-8565-565656565656",
    }

    ingest = client.post(
        "/v1/ingest",
        headers=ingest_headers,
        json={
            "namespace_id": "delete_namespace_test",
            "source_id": "s_delete_namespace_test",
            "source_type": "url",
            "url": "https://example.com/delete-namespace",
            "mime_type_hint": "text/plain",
            "metadata": {
                "text": "Articolul 15. Aporturile în numerar sunt obligatorii la constituirea oricărei forme de societate."
            },
        },
    )
    assert ingest.status_code == 202

    delete_response = client.delete(
        "/v1/namespaces/delete_namespace_test",
        headers=auth_headers,
    )

    assert delete_response.status_code == 202
    data = delete_response.json()
    assert data["job_id"].startswith("del_")
    assert data["status"] == "queued"
    assert data["sla"] == "24h"

    query_response = client.post(
        "/v1/query",
        headers=auth_headers,
        json={
            "question": "Ce spune articolul 15?",
            "language": "ro",
            "namespaces": ["delete_namespace_test"],
            "top_k": 5,
            "hint_article_number": "15",
            "include_answer": True,
        },
    )

    data = query_response.json()
    assert data["answer"] is None
    assert data["citations"] == []
    assert data["confidence"] == 0.0