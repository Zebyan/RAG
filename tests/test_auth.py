def test_missing_authorization_header(client):
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
    assert response.json()["error"]["code"] == "unauthorized"
