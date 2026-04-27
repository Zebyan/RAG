ALLOWED_ERROR_CODES = {
    "invalid_request",
    "unauthorized",
    "forbidden",
    "not_found",
    "namespace_not_found",
    "duplicate_job",
    "payload_too_large",
    "unsupported_media_type",
    "validation_error",
    "rate_limited",
    "internal_error",
    "upstream_error",
    "service_unavailable",
    "timeout",
}


def assert_contract_error(response):
    data = response.json()

    assert "error" in data
    assert data["error"]["code"] in ALLOWED_ERROR_CODES
    assert data["error"]["code"] == data["error"]["code"].lower()
    assert "message" in data["error"]
    assert "request_id" in data["error"]


def test_validation_error_code_is_contract_lowercase(client, auth_headers):
    response = client.post(
        "/v1/query",
        headers=auth_headers,
        json={
            "language": "ro",
            "namespaces": ["legea_31_1990"],
        },
    )

    assert response.status_code == 422
    assert_contract_error(response)


def test_unauthorized_error_code_is_contract_lowercase(client):
    response = client.post(
        "/v1/query",
        headers={
            "X-Request-ID": "11111111-1111-4111-8111-111111111111",
            "X-Tenant-ID": "test-tenant",
        },
        json={
            "question": "Ce spune articolul 15?",
            "language": "ro",
            "namespaces": ["legea_31_1990"],
        },
    )

    assert response.status_code == 401
    assert_contract_error(response)