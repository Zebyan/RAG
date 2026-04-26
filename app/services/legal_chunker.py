from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


ARTICLE_RE = re.compile(
    r"(?im)^\s*(?:Articolul|Art\.?)\s+([0-9]+(?:\^[0-9]+)?|[IVXLCDM]+)\s*[\.\-–:]?"
)

HEADING_RE = re.compile(
    r"(?im)^\s*((?:TITLUL|CAPITOLUL|SEC[ȚT]IUNEA|SECTIUNEA)\s+[^\n]+)"
)

PARAGRAPH_RE = re.compile(r"(?m)^\s*\(([0-9]+)\)")
POINT_RE = re.compile(r"(?m)^\s*([a-z])\)")


@dataclass
class LegalChunk:
    content: str
    article_number: str | None = None
    section_title: str | None = None
    point_number: str | None = None
    page_number: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def _headings_before(text: str, position: int) -> list[str]:
    before = text[:position]
    return [match.group(1).strip() for match in HEADING_RE.finditer(before)]


def _first_paragraph_number(text: str) -> str | None:
    match = PARAGRAPH_RE.search(text)
    return match.group(1) if match else None


def _first_point_number(text: str) -> str | None:
    match = POINT_RE.search(text)
    return match.group(1) if match else None


def _split_long_content(
    content: str,
    max_chunk_chars: int,
    overlap_chars: int,
) -> list[str]:
    content = content.strip()

    if len(content) <= max_chunk_chars:
        return [content] if content else []

    parts: list[str] = []
    start = 0

    while start < len(content):
        end = min(start + max_chunk_chars, len(content))

        if end < len(content):
            paragraph_break = content.rfind("\n\n", start, end)
            sentence_break = content.rfind(". ", start, end)
            break_point = max(paragraph_break, sentence_break)

            if break_point > start + max_chunk_chars // 2:
                end = break_point + 1

        part = content[start:end].strip()
        if part:
            parts.append(part)

        if end >= len(content):
            break

        start = max(0, end - overlap_chars)

    return parts


def chunk_legal_text(
    text: str,
    page_number: int | None = None,
    max_chunk_chars: int = 3800,
    overlap_chars: int = 300,
) -> list[LegalChunk]:
    """
    Legal-aware chunking strategy.

    Current behavior:
    - detects Articolul 15 / Art. 15 / Articolul 15^1 / Art. II
    - keeps one article as one chunk when possible
    - attaches latest legal heading as section_title
    - stores heading path and paragraph number in metadata
    - extracts first lettered point like a), b), c)
    - splits long articles into overlapping subchunks
    """
    normalized = _normalize_newlines(text)

    if not normalized:
        return []

    article_matches = list(ARTICLE_RE.finditer(normalized))

    if not article_matches:
        parts = _split_long_content(
            normalized,
            max_chunk_chars=max_chunk_chars,
            overlap_chars=overlap_chars,
        )

        return [
            LegalChunk(
                content=part,
                page_number=page_number,
                metadata={
                    "chunk_type": "unstructured",
                    "chunk_part": index + 1,
                    "chunk_total": len(parts),
                },
            )
            for index, part in enumerate(parts)
        ]

    chunks: list[LegalChunk] = []

    document_preamble = normalized[: article_matches[0].start()].strip()

    for article_index, match in enumerate(article_matches):
        article_start = match.start()
        article_end = (
            article_matches[article_index + 1].start()
            if article_index + 1 < len(article_matches)
            else len(normalized)
        )

        article_number = match.group(1)
        article_text = normalized[article_start:article_end].strip()

        headings = _headings_before(normalized, article_start)
        section_title = headings[-1] if headings else None
        paragraph_number = _first_paragraph_number(article_text)
        point_number = _first_point_number(article_text)

        parts = _split_long_content(
            article_text,
            max_chunk_chars=max_chunk_chars,
            overlap_chars=overlap_chars,
        )

        for part_index, part in enumerate(parts):
            metadata: dict[str, Any] = {
                "chunk_type": "legal_article",
                "headings": headings,
                "paragraph_number": paragraph_number,
                "chunk_part": part_index + 1,
                "chunk_total": len(parts),
            }

            if article_index == 0 and document_preamble:
                metadata["document_preamble"] = document_preamble

            chunks.append(
                LegalChunk(
                    content=part,
                    article_number=article_number,
                    section_title=section_title,
                    point_number=point_number,
                    page_number=page_number,
                    metadata=metadata,
                )
            )

    return chunks