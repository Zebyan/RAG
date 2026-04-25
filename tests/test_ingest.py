def test_idempotency_conflict_returns_409(client, auth_headers):
    headers = {
        **auth_headers,
        "Idempotency-Key": "88888888-8888-4888-8888-888888888888",
    }

    first = {
        "namespace_id": "legea_31_1990",
        "source_id": "s_test_002",
        "source_type": "url",
        "url": "https://example.com/a",
        "mime_type_hint": "text/plain",
    }
    second = {
        "namespace_id": "legea_31_1990",
        "source_id": "s_test_003",
        "source_type": "url",
        "url": "https://example.com/b",
        "mime_type_hint": "text/plain",
    }

    r1 = client.post("/v1/ingest", headers=headers, json=first)
    assert r1.status_code == 202

    r2 = client.post("/v1/ingest", headers=headers, json=second)
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "duplicate_job"

def test_idempotent_same_key_same_body_returns_same_job(client, auth_headers):
    headers = {
        **auth_headers,
        "Idempotency-Key": "99999999-9999-4999-8999-999999999999",
    }

    body = {
        "namespace_id": "legea_31_1990",
        "source_id": "s_test_same_body",
        "source_type": "url",
        "url": "https://example.com/same",
        "mime_type_hint": "text/plain",
        "metadata": {
            "text": "Articolul 15. Aporturile în numerar sunt obligatorii la constituirea oricărei forme de societate."
        },
    }

    r1 = client.post("/v1/ingest", headers=headers, json=body)
    r2 = client.post("/v1/ingest", headers=headers, json=body)

    assert r1.status_code == 202
    assert r2.status_code == 202
    assert r1.json()["job_id"] == r2.json()["job_id"]

def test_poll_existing_job_returns_done(client, auth_headers):
    headers = {
        **auth_headers,
        "Idempotency-Key": "12121212-1212-4121-8121-121212121212",
    }

    body = {
        "namespace_id": "legea_31_1990",
        "source_id": "s_poll_test",
        "source_type": "url",
        "url": "https://example.com/poll",
        "mime_type_hint": "text/plain",
        "metadata": {
            "text": "Articolul 15. Aporturile în numerar sunt obligatorii la constituirea oricărei forme de societate."
        },
    }

    ingest = client.post("/v1/ingest", headers=headers, json=body)
    assert ingest.status_code == 202

    job_id = ingest.json()["job_id"]

    status = client.get(f"/v1/ingest/{job_id}", headers=auth_headers)

    assert status.status_code == 200
    data = status.json()
    assert data["job_id"] == job_id
    assert data["status"] == "done"
    assert data["progress"]["percent"] == 100

def test_unsupported_mime_type_returns_415(client, auth_headers):
    headers = {
        **auth_headers,
        "Idempotency-Key": "89898989-8989-4898-8898-898989898989",
    }

    response = client.post(
        "/v1/ingest",
        headers=headers,
        json={
            "namespace_id": "legea_31_1990",
            "source_id": "s_bad_mime",
            "source_type": "url",
            "url": "https://example.com/bad",
            "mime_type_hint": "application/msword",
        },
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_media_type"