from __future__ import annotations

import httpx
import pytest

from app.services.url_fetcher import UrlFetchError, fetch_url_document


def test_fetch_url_document_extracts_plain_text(monkeypatch):
    def fake_get(self, url, *args, **kwargs):
        return httpx.Response(
            status_code=200,
            headers={"content-type": "text/plain; charset=utf-8"},
            content="Articolul 15. Aporturile în numerar sunt obligatorii.".encode("utf-8"),
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx.Client, "get", fake_get)

    result = fetch_url_document("https://example.com/legal.txt")

    assert result.status_code == 200
    assert result.extracted.mime_type == "text/plain"
    assert "Aporturile în numerar" in result.extracted.text
    assert result.metadata["effective_mime_type"] == "text/plain"


def test_fetch_url_document_extracts_html(monkeypatch):
    def fake_get(self, url, *args, **kwargs):
        return httpx.Response(
            status_code=200,
            headers={"content-type": "text/html; charset=utf-8"},
            content="""
            <html>
              <head>
                <script>alert("ignore")</script>
              </head>
              <body>
                <main>
                  <h1>Legea 31/1990</h1>
                  <p>Articolul 15. Aporturile în numerar sunt obligatorii.</p>
                </main>
              </body>
            </html>
            """.encode("utf-8"),
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx.Client, "get", fake_get)

    result = fetch_url_document("https://example.com/legal.html")

    assert result.status_code == 200
    assert result.extracted.mime_type == "text/html"
    assert "Legea 31/1990" in result.extracted.text
    assert "Aporturile în numerar" in result.extracted.text
    assert "alert" not in result.extracted.text


def test_fetch_url_document_uses_mime_hint_when_content_type_missing(monkeypatch):
    def fake_get(self, url, *args, **kwargs):
        return httpx.Response(
            status_code=200,
            content="Articolul 16. Aporturile în natură trebuie evaluate.".encode("utf-8"),
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx.Client, "get", fake_get)

    result = fetch_url_document(
        "https://example.com/legal",
        mime_type_hint="text/plain",
    )

    assert result.extracted.mime_type == "text/plain"
    assert "Aporturile în natură" in result.extracted.text


def test_fetch_url_document_raises_for_404(monkeypatch):
    def fake_get(self, url, *args, **kwargs):
        return httpx.Response(
            status_code=404,
            content=b"Not found",
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx.Client, "get", fake_get)

    with pytest.raises(UrlFetchError):
        fetch_url_document("https://example.com/missing")


def test_fetch_url_document_raises_for_unsupported_mime(monkeypatch):
    def fake_get(self, url, *args, **kwargs):
        return httpx.Response(
            status_code=200,
            headers={"content-type": "application/json"},
            content=b'{"hello": "world"}',
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx.Client, "get", fake_get)

    with pytest.raises(UrlFetchError):
        fetch_url_document("https://example.com/data.json")