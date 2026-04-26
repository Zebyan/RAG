from __future__ import annotations

import pytest

from app.services.document_extractor import (
    DocumentExtractionError,
    extract_document_text,
    normalize_mime_type,
)


def test_normalize_mime_type_removes_charset():
    assert normalize_mime_type("text/html; charset=utf-8") == "text/html"


def test_extract_plain_text():
    content = "Articolul 15. Aporturile în numerar sunt obligatorii.".encode("utf-8")

    result = extract_document_text(content, "text/plain")

    assert result.mime_type == "text/plain"
    assert "Aporturile în numerar" in result.text
    assert result.metadata["original_size_bytes"] == len(content)


def test_extract_markdown_text():
    content = (
        "# Legea 31/1990\n\n"
        "Articolul 15.\n"
        "Aporturile în numerar sunt obligatorii."
    ).encode("utf-8")

    result = extract_document_text(content, "text/markdown")

    assert result.mime_type == "text/markdown"
    assert "Articolul 15" in result.text
    assert "Aporturile în numerar" in result.text


def test_extract_html_visible_text_only():
    content = """
    <html>
      <head>
        <style>.hidden { display: none; }</style>
        <script>alert("ignore");</script>
      </head>
      <body>
        <header>Menu</header>
        <main>
          <h1>Legea 31/1990</h1>
          <p>Articolul 15. Aporturile în numerar sunt obligatorii.</p>
        </main>
        <footer>Footer text</footer>
      </body>
    </html>
    """.encode("utf-8")

    result = extract_document_text(content, "text/html; charset=utf-8")

    assert result.mime_type == "text/html"
    assert "Legea 31/1990" in result.text
    assert "Aporturile în numerar" in result.text
    assert "alert" not in result.text
    assert "Footer text" not in result.text


def test_unsupported_mime_type_raises_error():
    with pytest.raises(DocumentExtractionError):
        extract_document_text(b"{}", "application/json")


def test_empty_text_raises_error():
    with pytest.raises(DocumentExtractionError):
        extract_document_text(b"   ", "text/plain")