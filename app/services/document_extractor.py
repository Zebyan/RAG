from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from typing import Any

from bs4 import BeautifulSoup
from pypdf import PdfReader


MAX_DOCUMENT_BYTES = 50 * 1024 * 1024

SUPPORTED_MIME_TYPES = {
    "text/plain",
    "text/markdown",
    "text/html",
    "application/pdf",
}


class DocumentExtractionError(ValueError):
    pass


@dataclass
class ExtractedDocument:
    text: str
    mime_type: str
    metadata: dict[str, Any] = field(default_factory=dict)


def normalize_mime_type(mime_type: str | None) -> str:
    if not mime_type:
        return "application/octet-stream"

    return mime_type.split(";", 1)[0].strip().lower()


def validate_document_size(content: bytes) -> None:
    if len(content) > MAX_DOCUMENT_BYTES:
        raise DocumentExtractionError("Document exceeds maximum allowed size of 50 MiB.")


def validate_mime_type(mime_type: str) -> None:
    if mime_type not in SUPPORTED_MIME_TYPES:
        raise DocumentExtractionError(f"Unsupported MIME type: {mime_type}")


def _decode_text(content: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue

    raise DocumentExtractionError("Could not decode text content.")


def _extract_plain_text(content: bytes) -> str:
    return _decode_text(content).strip()


def _extract_markdown(content: bytes) -> str:
    # Keep markdown mostly as-is. Legal headings/articles are usually text-based,
    # and the legal chunker can process them directly.
    return _decode_text(content).strip()


def _extract_html(content: bytes) -> str:
    html = _decode_text(content)
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(
        [
            "script",
            "style",
            "noscript",
            "template",
            "svg",
            "canvas",
            "nav",
            "footer",
            "header",
        ]
    ):
        tag.decompose()

    text = soup.get_text(separator="\n")

    lines = [line.strip() for line in text.splitlines()]
    clean_lines = [line for line in lines if line]

    return "\n".join(clean_lines).strip()


def _extract_pdf(content: bytes) -> tuple[str, dict[str, Any]]:
    try:
        reader = PdfReader(BytesIO(content))
    except Exception as exc:
        raise DocumentExtractionError("Could not read PDF document.") from exc

    pages: list[str] = []
    page_count = len(reader.pages)

    for index, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""

        page_text = page_text.strip()

        if page_text:
            pages.append(f"[Page {index}]\n{page_text}")

    text = "\n\n".join(pages).strip()

    if not text:
        raise DocumentExtractionError("No extractable text found in PDF document.")

    return text, {"page_count": page_count}


def extract_document_text(
    content: bytes,
    mime_type: str | None,
) -> ExtractedDocument:
    validate_document_size(content)

    normalized_mime = normalize_mime_type(mime_type)
    validate_mime_type(normalized_mime)

    metadata: dict[str, Any] = {
        "original_size_bytes": len(content),
    }

    if normalized_mime == "text/plain":
        text = _extract_plain_text(content)
    elif normalized_mime == "text/markdown":
        text = _extract_markdown(content)
    elif normalized_mime == "text/html":
        text = _extract_html(content)
    elif normalized_mime == "application/pdf":
        text, pdf_metadata = _extract_pdf(content)
        metadata.update(pdf_metadata)
    else:
        raise DocumentExtractionError(f"Unsupported MIME type: {normalized_mime}")

    if not text:
        raise DocumentExtractionError("Extracted document text is empty.")

    return ExtractedDocument(
        text=text,
        mime_type=normalized_mime,
        metadata=metadata,
    )