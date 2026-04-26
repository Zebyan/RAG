from __future__ import annotations

from uuid import uuid4

from app.services.document_extractor import ExtractedDocument
from app.services.url_fetcher import FetchedUrlDocument


def test_ingest_fetches_url_when_metadata_text_missing(client, auth_headers, monkeypatch):
    namespace_id = f"url_fetch_namespace_{uuid4().hex}"
    source_id = f"s_url_fetch_{uuid4().hex}"

    def fake_fetch_url_document(url: str, mime_type_hint: str | None = None):
        return FetchedUrlDocument(
            url=url,
            status_code=200,
            extracted=ExtractedDocument(
                text=(
                    "Articolul 15.\n"
                    "Aporturile în numerar sunt obligatorii la constituirea oricărei forme de societate."
                ),
                mime_type="text/plain",
                metadata={"original_size_bytes": 128},
            ),
            metadata={
                "fetched_url": url,
                "http_status_code": 200,
                "effective_mime_type": "text/plain",
            },
        )

    monkeypatch.setattr(
        "app.services.ingest_service.fetch_url_document",
        fake_fetch_url_document,
    )

    ingest_headers = {
        **auth_headers,
        "Idempotency-Key": str(uuid4()),
    }

    response = client.post(
        "/v1/ingest",
        headers=ingest_headers,
        json={
            "namespace_id": namespace_id,
            "source_id": source_id,
            "source_type": "url",
            "url": "https://example.com/legal.txt",
            "mime_type_hint": "text/plain",
            "metadata": {
                "source_title": "Fetched Legal Text"
            },
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
    assert data["citations"][0]["chunk"]["source_title"] == "Fetched Legal Text"
    assert data["citations"][0]["chunk"]["metadata"]["text_source"] == "url_fetch"
    assert data["citations"][0]["chunk"]["metadata"]["effective_mime_type"] == "text/plain"


def test_ingest_metadata_text_still_works_without_fetch(client, auth_headers, monkeypatch):
    namespace_id = f"metadata_text_namespace_{uuid4().hex}"
    source_id = f"s_metadata_text_{uuid4().hex}"

    def fail_if_called(url: str, mime_type_hint: str | None = None):
        raise AssertionError("fetch_url_document should not be called when metadata.text exists")

    monkeypatch.setattr(
        "app.services.ingest_service.fetch_url_document",
        fail_if_called,
    )

    ingest_headers = {
        **auth_headers,
        "Idempotency-Key": str(uuid4()),
    }

    response = client.post(
        "/v1/ingest",
        headers=ingest_headers,
        json={
            "namespace_id": namespace_id,
            "source_id": source_id,
            "source_type": "url",
            "url": "https://example.com/fixture",
            "mime_type_hint": "text/plain",
            "metadata": {
                "source_title": "Fixture Text",
                "text": "Articolul 16. Aporturile în natură trebuie să fie evaluabile.",
            },
        },
    )

    assert response.status_code == 202

    query_response = client.post(
        "/v1/query",
        headers=auth_headers,
        json={
            "question": "Ce spune articolul 16?",
            "language": "ro",
            "namespaces": [namespace_id],
            "top_k": 5,
            "hint_article_number": "16",
            "include_answer": True,
        },
    )

    assert query_response.status_code == 200

    data = query_response.json()

    assert data["answer"] is not None
    assert data["citations"][0]["chunk"]["metadata"]["text_source"] == "metadata.text"