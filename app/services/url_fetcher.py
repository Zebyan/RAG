from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import settings
from app.services.document_extractor import (
    DocumentExtractionError,
    ExtractedDocument,
    extract_document_text,
    normalize_mime_type,
)


class UrlFetchError(ValueError):
    pass


@dataclass
class FetchedUrlDocument:
    url: str
    extracted: ExtractedDocument
    status_code: int
    headers: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


def fetch_url_document(
    url: str,
    mime_type_hint: str | None = None,
) -> FetchedUrlDocument:
    """
    Fetch a URL and extract supported document text.

    Supported MIME types:
    - text/plain
    - text/markdown
    - text/html
    - application/pdf
    """
    try:
        with httpx.Client(
            timeout=settings.url_fetch_timeout_seconds,
            follow_redirects=True,
        ) as client:
            response = client.get(url)
    except httpx.TimeoutException as exc:
        raise UrlFetchError(
            f"URL fetch timed out after {settings.url_fetch_timeout_seconds} seconds."
        ) from exc
    except httpx.HTTPError as exc:
        raise UrlFetchError("URL fetch failed.") from exc

    if response.status_code >= 400:
        raise UrlFetchError(f"URL fetch returned HTTP {response.status_code}.")

    response_mime = normalize_mime_type(response.headers.get("content-type"))
    hint_mime = normalize_mime_type(mime_type_hint)

    # Prefer response Content-Type. If missing, use mime_type_hint.
    mime_type = response_mime
    if mime_type == "application/octet-stream" and hint_mime != "application/octet-stream":
        mime_type = hint_mime

    try:
        extracted = extract_document_text(response.content, mime_type)
    except DocumentExtractionError as exc:
        raise UrlFetchError(str(exc)) from exc

    return FetchedUrlDocument(
        url=str(response.url),
        extracted=extracted,
        status_code=response.status_code,
        headers=dict(response.headers),
        metadata={
            "fetched_url": str(response.url),
            "http_status_code": response.status_code,
            "content_type": response.headers.get("content-type"),
            "effective_mime_type": extracted.mime_type,
        },
    )