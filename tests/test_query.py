def test_query_empty_without_ingest(client, auth_headers):
    response = client.post(
        "/v1/query",
        headers=auth_headers,
        json={
            "question": "Care este programul primăriei Bălta Doamnei?",
            "language": "ro",
            "namespaces": ["legea_31_1990"],
            "top_k": 5,
            "include_answer": True,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] is None
    assert data["citations"] == []
    assert data["confidence"] == 0.0


def test_query_exact_article_after_ingest(client, auth_headers):
    ingest_headers = {
        **auth_headers,
        "Idempotency-Key": "44444444-4444-4444-8444-444444444444",
    }

    ingest_response = client.post(
        "/v1/ingest",
        headers=ingest_headers,
        json={
            "namespace_id": "legea_31_1990",
            "source_id": "s_47381",
            "source_type": "url",
            "url": "https://legislatie.just.ro/Public/DetaliiDocument/47381",
            "mime_type_hint": "text/plain",
            "metadata": {
                "source_title": "Legea 31/1990 privind societățile comerciale",
                "text": "Articolul 15. Aporturile în numerar sunt obligatorii la constituirea oricărei forme de societate.",
            },
        },
    )
    assert ingest_response.status_code == 202

    query_response = client.post(
        "/v1/query",
        headers=auth_headers,
        json={
            "question": "Ce spune articolul 15 din Legea 31/1990?",
            "language": "ro",
            "namespaces": ["legea_31_1990"],
            "top_k": 5,
            "hint_article_number": "15",
            "rerank": True,
            "include_answer": True,
        },
    )

    assert query_response.status_code == 200
    data = query_response.json()
    assert data["answer"] is not None
    assert "[1]" in data["answer"]
    assert data["citations"][0]["chunk"]["article_number"] == "15"
    assert "aporturile în numerar" in data["citations"][0]["chunk"]["content"].lower()

def test_wrong_namespace_returns_empty_result(client, auth_headers):
    ingest_headers = {
        **auth_headers,
        "Idempotency-Key": "23232323-2323-4232-8232-232323232323",
    }

    client.post(
        "/v1/ingest",
        headers=ingest_headers,
        json={
            "namespace_id": "legea_31_1990",
            "source_id": "s_wrong_namespace_test",
            "source_type": "url",
            "url": "https://example.com/legea31",
            "mime_type_hint": "text/plain",
            "metadata": {
                "text": "Articolul 15. Aporturile în numerar sunt obligatorii la constituirea oricărei forme de societate."
            },
        },
    )

    response = client.post(
        "/v1/query",
        headers=auth_headers,
        json={
            "question": "Ce spune articolul 15?",
            "language": "ro",
            "namespaces": ["cod_civil"],
            "top_k": 5,
            "hint_article_number": "15",
            "include_answer": True,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] is None
    assert data["citations"] == []
    assert data["confidence"] == 0.0

def test_cross_tenant_isolation(client):
    tenant_a_headers = {
        "Authorization": "Bearer test-api-key",
        "X-Request-ID": "67676767-6767-4676-8676-676767676767",
        "X-Tenant-ID": "tenant-a",
    }
    tenant_a_ingest_headers = {
        **tenant_a_headers,
        "Idempotency-Key": "67676767-6767-4676-8676-676767676768",
    }

    tenant_b_headers = {
        "Authorization": "Bearer test-api-key",
        "X-Request-ID": "78787878-7878-4787-8787-787878787878",
        "X-Tenant-ID": "tenant-b",
    }

    ingest = client.post(
        "/v1/ingest",
        headers=tenant_a_ingest_headers,
        json={
            "namespace_id": "shared_namespace",
            "source_id": "s_tenant_a",
            "source_type": "url",
            "url": "https://example.com/tenant-a",
            "mime_type_hint": "text/plain",
            "metadata": {
                "text": "Articolul 15. Acest text aparține doar tenantului A."
            },
        },
    )
    assert ingest.status_code == 202

    response = client.post(
        "/v1/query",
        headers=tenant_b_headers,
        json={
            "question": "Ce spune articolul 15?",
            "language": "ro",
            "namespaces": ["shared_namespace"],
            "top_k": 5,
            "hint_article_number": "15",
            "include_answer": True,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] is None
    assert data["citations"] == []
    assert data["confidence"] == 0.0

def test_language_not_ro_returns_422(client, auth_headers):
    response = client.post(
        "/v1/query",
        headers=auth_headers,
        json={
            "question": "What does article 15 say?",
            "language": "en",
            "namespaces": ["legea_31_1990"],
        },
    )

    assert response.status_code == 422


def test_top_k_over_50_returns_422(client, auth_headers):
    response = client.post(
        "/v1/query",
        headers=auth_headers,
        json={
            "question": "Ce spune articolul 15?",
            "language": "ro",
            "namespaces": ["legea_31_1990"],
            "top_k": 100,
        },
    )

    assert response.status_code == 422


def test_empty_namespaces_returns_422(client, auth_headers):
    response = client.post(
        "/v1/query",
        headers=auth_headers,
        json={
            "question": "Ce spune articolul 15?",
            "language": "ro",
            "namespaces": [],
        },
    )

    assert response.status_code == 422