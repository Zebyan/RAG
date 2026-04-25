from __future__ import annotations

import re

from app.models import Chunk
from app.services import store


ROMANIAN_STOPWORDS = {
    "ce", "spune", "din", "si", "și", "sau", "la", "de", "in", "în",
    "care", "este", "sunt", "un", "o", "cu", "pe", "pentru", "articolul",
}


def _tokens(text: str) -> set[str]:
    words = re.findall(r"\w+", text.lower(), flags=re.UNICODE)
    return {w for w in words if len(w) > 2 and w not in ROMANIAN_STOPWORDS}


def _keyword_score(question: str, content: str) -> float:
    q = _tokens(question)
    c = _tokens(content)
    if not q:
        return 0.0
    overlap = len(q & c) / len(q)
    return min(overlap * 0.25, 0.25)


def retrieve_chunks(
    tenant_id: str,
    namespaces: list[str],
    question: str,
    top_k: int,
    hint_article_number: str | None,
) -> list[Chunk]:
    candidates = store.list_chunks(tenant_id=tenant_id, namespaces=namespaces)

    scored: list[Chunk] = []
    for raw in candidates:
        score = 0.0

        if hint_article_number and raw.get("article_number") == hint_article_number:
            score += 0.70

        score += _keyword_score(question, raw["content"])

        # Avoid weak random matches.
        if score < 0.30:
            continue

        payload = dict(raw)
        payload["score"] = min(score, 1.0)
        scored.append(Chunk(**payload))

    scored.sort(key=lambda chunk: chunk.score, reverse=True)
    return scored[:top_k]
