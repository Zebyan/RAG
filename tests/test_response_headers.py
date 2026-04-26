from uuid import uuid4


def test_health_response_includes_standard_headers(client):
    request_id = str(uuid4())

    response = client.get(
        "/v1/health",
        headers={
            "X-Request-ID": request_id,
        },
    )

    assert response.status_code == 200

    assert response.headers["X-Request-ID"] == request_id
    assert response.headers["X-Vendor-Trace-ID"].startswith("tr_")
    assert response.headers["Server-Timing"].startswith("app;dur=")


def test_query_response_includes_retrieval_strategy_header(client, auth_headers):
    namespace_id = f"headers_namespace_{uuid4().hex}"
    source_id = f"s_headers_{uuid4().hex}"

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
            "url": "https://example.com/headers",
            "mime_type_hint": "text/plain",
            "metadata": {
                "source_title": "Legea 31/1990",
                "text": "Articolul 15. Aporturile în numerar sunt obligatorii.",
            },
        },
    )

    assert ingest_response.status_code == 202

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

    assert query_response.headers["X-Request-ID"] == auth_headers["X-Request-ID"]
    assert query_response.headers["X-Vendor-Trace-ID"].startswith("tr_")
    assert query_response.headers["Server-Timing"].startswith("app;dur=")
    assert query_response.headers["X-Vendor-Retrieval-Strategy"] == "hybrid_qdrant_article_keyword"

    data = query_response.json()

    assert data["trace_id"] == query_response.headers["X-Vendor-Trace-ID"]
    assert data["retrieval_strategy"] == query_response.headers["X-Vendor-Retrieval-Strategy"]


def test_vendor_trace_id_can_be_supplied_by_client(client):
    trace_id = f"tr_{uuid4().hex}"
    request_id = str(uuid4())

    response = client.get(
        "/v1/health",
        headers={
            "X-Request-ID": request_id,
            "X-Vendor-Trace-ID": trace_id,
        },
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == request_id
    assert response.headers["X-Vendor-Trace-ID"] == trace_id