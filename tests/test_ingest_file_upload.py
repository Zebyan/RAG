from __future__ import annotations

import json
from uuid import uuid4


def test_ingest_multipart_text_file(client, auth_headers):
    namespace_id = f"file_upload_namespace_{uuid4().hex}"
    source_id = f"s_file_upload_{uuid4().hex}"

    payload = {
        "namespace_id": namespace_id,
        "source_id": source_id,
        "source_type": "file",
        "mime_type_hint": "text/plain",
        "metadata": {
            "source_title": "Uploaded Legal Text"
        },
    }

    file_content = (
        "Articolul 15.\n"
        "Aporturile în numerar sunt obligatorii la constituirea oricărei forme de societate."
    ).encode("utf-8")

    ingest_headers = {
        **auth_headers,
        "Idempotency-Key": str(uuid4()),
    }

    response = client.post(
        "/v1/ingest",
        headers=ingest_headers,
        data={
            "payload": json.dumps(payload),
        },
        files={
            "file": ("legea_31.txt", file_content, "text/plain"),
        },
    )

    assert response.status_code == 202

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

    assert data["answer"] is not None
    assert data["citations"]
    assert data["citations"][0]["chunk"]["source_title"] == "Uploaded Legal Text"
    assert data["citations"][0]["chunk"]["metadata"]["text_source"] == "uploaded_file"
    assert data["citations"][0]["chunk"]["metadata"]["uploaded_filename"] == "legea_31.txt"
    assert data["citations"][0]["chunk"]["metadata"]["effective_mime_type"] == "text/plain"


def test_ingest_multipart_requires_payload(client, auth_headers):
    ingest_headers = {
        **auth_headers,
        "Idempotency-Key": str(uuid4()),
    }

    response = client.post(
        "/v1/ingest",
        headers=ingest_headers,
        files={
            "file": ("legea_31.txt", b"Articolul 15.", "text/plain"),
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_ingest_multipart_requires_file(client, auth_headers):
    ingest_headers = {
        **auth_headers,
        "Idempotency-Key": str(uuid4()),
    }

    payload = {
        "namespace_id": f"missing_file_namespace_{uuid4().hex}",
        "source_id": f"s_missing_file_{uuid4().hex}",
        "source_type": "file",
        "mime_type_hint": "text/plain",
        "metadata": {
            "source_title": "Missing File"
        },
    }

    response = client.post(
        "/v1/ingest",
        headers=ingest_headers,
        data={
            "payload": json.dumps(payload),
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"