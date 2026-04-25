from __future__ import annotations

import re

from app.models import Chunk, Citation, StyleHints


def _clean_article_text(content: str) -> str:
    text = re.sub(r"\s+", " ", content).strip()
    return text


def build_answer_response(
    include_answer: bool,
    question: str,
    chunks: list[Chunk],
    style_hints: StyleHints | None,
) -> tuple[str | None, list[Citation], float]:
    if not chunks:
        return None, [], 0.0

    citations = [
        Citation(marker=f"[{index}]", chunk=chunk)
        for index, chunk in enumerate(chunks, start=1)
    ]

    confidence = chunks[0].score

    if not include_answer:
        return None, citations, confidence

    top_chunk = chunks[0]
    content = _clean_article_text(top_chunk.content)

    if top_chunk.article_number:
        answer = f"Articolul {top_chunk.article_number} prevede următoarele: {content} [1]."
    else:
        answer = f"Conform sursei găsite, informația relevantă este: {content} [1]."

    if style_hints:
        answer = answer[: style_hints.answer_max_chars].rstrip()

    return answer, citations, confidence
