from __future__ import annotations

import re
import unicodedata
from collections import defaultdict

from app.models import Chunk
from app.services import sqlite_store as store


ROMANIAN_STOPWORDS = {
    "ce", "spune", "din", "si", "și", "sau", "la", "de", "in", "în",
    "care", "este", "sunt", "un", "o", "cu", "pe", "pentru", "articolul",
    "art", "despre", "cum", "se", "al", "ai", "ale", "prin", "privind",
    "legea", "codul", "au", "are", "ceea", "cel", "cea", "cei", "cele",
}


def _normalize(text: str) -> str:
    lowered = text.lower()
    normalized = unicodedata.normalize("NFD", lowered)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _tokens(text: str) -> set[str]:
    normalized = _normalize(text)
    words = re.findall(r"\w+", normalized, flags=re.UNICODE)
    return {w for w in words if len(w) > 2 and w not in ROMANIAN_STOPWORDS}


def _rough_stem(token: str) -> str:
    """
    Very small Romanian-friendly stemming approximation for MVP scoring.
    It is only used for retrieval scoring, not for modifying citation content.
    """
    suffixes = [
        "urilor", "elor", "ilor", "ului", "ului",
        "ele", "ile", "ului", "ului", "lor",
        "atea", "ului", "ului", "ului",
        "ul", "le", "ii", "ei", "ea", "a", "e", "i",
    ]

    for suffix in suffixes:
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            return token[: -len(suffix)]

    return token


def _expanded_tokens(text: str) -> set[str]:
    base = _tokens(text)
    expanded = set(base)

    for token in base:
        stem = _rough_stem(token)
        expanded.add(stem)

    return expanded


def _soft_overlap(question_tokens: set[str], content_tokens: set[str]) -> float:
    if not question_tokens:
        return 0.0

    matches = 0

    for q in question_tokens:
        for c in content_tokens:
            if q == c:
                matches += 1
                break

            # Prefix matching for close Romanian forms:
            # societate / societatea, persoana / persoane, obligatie / obligatii
            if len(q) >= 5 and len(c) >= 5:
                if q.startswith(c[:5]) or c.startswith(q[:5]):
                    matches += 1
                    break

    return matches / len(question_tokens)


def _keyword_score(question: str, content: str) -> float:
    q = _expanded_tokens(question)
    c = _expanded_tokens(content)

    if not q:
        return 0.0

    overlap = _soft_overlap(q, c)

    # More permissive lexical score for Romanian legal MVP retrieval.
    return min(overlap * 0.55, 0.55)


def _phrase_score(question: str, content: str) -> float:
    q_norm = _normalize(question)
    c_norm = _normalize(content)

    q_tokens = [
        t for t in re.findall(r"\w+", q_norm)
        if len(t) > 2 and t not in ROMANIAN_STOPWORDS
    ]

    if len(q_tokens) < 2:
        return 0.0

    score = 0.0

    for i in range(len(q_tokens) - 1):
        phrase = f"{q_tokens[i]} {q_tokens[i + 1]}"
        if phrase in c_norm:
            score += 0.08

    for i in range(len(q_tokens) - 2):
        phrase = f"{q_tokens[i]} {q_tokens[i + 1]} {q_tokens[i + 2]}"
        if phrase in c_norm:
            score += 0.12

    return min(score, 0.25)


def _article_score(chunk_article: str | None, hint_article_number: str | None) -> float:
    if not hint_article_number or not chunk_article:
        return 0.0

    return 0.70 if chunk_article == hint_article_number else 0.0


def _final_score(
    question: str,
    content: str,
    chunk_article: str | None,
    hint_article_number: str | None,
) -> float:
    article = _article_score(chunk_article, hint_article_number)
    keyword = _keyword_score(question, content)
    phrase = _phrase_score(question, content)

    score = article + keyword + phrase
    return min(score, 1.0)


def _ensure_namespace_diversity(chunks: list[Chunk], requested_namespaces: list[str], top_k: int) -> list[Chunk]:
    if len(requested_namespaces) <= 1:
        return chunks[:top_k]

    by_namespace: dict[str, list[Chunk]] = defaultdict(list)
    for chunk in chunks:
        by_namespace[chunk.namespace_id].append(chunk)

    diversified: list[Chunk] = []
    used_ids: set[str] = set()

    for namespace in requested_namespaces:
        namespace_chunks = by_namespace.get(namespace, [])
        if namespace_chunks:
            best = namespace_chunks[0]
            diversified.append(best)
            used_ids.add(best.chunk_id)

    for chunk in chunks:
        if chunk.chunk_id not in used_ids:
            diversified.append(chunk)
            used_ids.add(chunk.chunk_id)

        if len(diversified) >= top_k:
            break

    return diversified[:top_k]


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
        score = _final_score(
            question=question,
            content=raw["content"],
            chunk_article=raw.get("article_number"),
            hint_article_number=hint_article_number,
        )

        # More tolerant threshold for MVP keyword retrieval.
        # Exact no-answer behavior is still preserved because completely unrelated
        # chunks score close to 0.
        if score < 0.15:
            continue

        payload = dict(raw)
        payload["score"] = score
        scored.append(Chunk(**payload))

    scored.sort(key=lambda chunk: chunk.score, reverse=True)

    return _ensure_namespace_diversity(scored, namespaces, top_k)