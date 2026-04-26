def test_query_validation_error_uses_standard_error_response(client, auth_headers):
    response = client.post(
        "/v1/query",
        headers=auth_headers,
        json={
            # missing required "question"
            "language": "ro",
            "namespaces": ["legea_31_1990"],
            "top_k": 5,
            "include_answer": True,
        },
    )

    assert response.status_code == 422

    data = response.json()

    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert data["error"]["message"] == "Request validation failed."
    assert data["error"]["request_id"] == auth_headers["X-Request-ID"]
    assert "details" in data["error"]
    assert "errors" in data["error"]["details"]

    errors = data["error"]["details"]["errors"]

    assert any(
        error["loc"][-1] == "question"
        for error in errors
    )


def test_ingest_validation_error_uses_standard_error_response(client, auth_headers):
    ingest_headers = {
        **auth_headers,
        "Idempotency-Key": "11111111-1111-4111-8111-111111111111",
    }

    response = client.post(
        "/v1/ingest",
        headers=ingest_headers,
        json={
            # missing namespace_id
            "source_id": "s_validation_test",
            "source_type": "url",
            "url": "https://example.com",
            "mime_type_hint": "text/plain",
        },
    )

    assert response.status_code == 422

    data = response.json()

    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert data["error"]["request_id"] == auth_headers["X-Request-ID"]

    errors = data["error"]["details"]["errors"]

    assert any(
        error["loc"][-1] == "namespace_id"
        for error in errors
    )