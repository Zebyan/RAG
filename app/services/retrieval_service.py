from __future__ import annotations

import re
import unicodedata
from collections import defaultdict

from app.config import settings
from app.models import Chunk
from app.services import sqlite_store as store
from app.services.embedding_service import embed_text
from app.services import vector_store


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
    suffixes = [
        "urilor", "elor", "ilor", "ului",
        "ele", "ile", "lor", "atea",
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
        expanded.add(_rough_stem(token))

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
    return min(overlap * 0.55, 0.55)


def _phrase_score(question: str, content: str) -> float:
    q_norm = _normalize(question)
    c_norm = _normalize(content)

    q_tokens = [
        token for token in re.findall(r"\w+", q_norm)
        if len(token) > 2 and token not in ROMANIAN_STOPWORDS
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

    return 0.85 if chunk_article == hint_article_number else 0.0


def _clamp_score(value: float) -> float:
    return max(0.0, min(value, 1.0))


def _lexical_final_score(
    question: str,
    content: str,
    chunk_article: str | None,
    hint_article_number: str | None,
) -> float:
    article = _article_score(chunk_article, hint_article_number)
    keyword = _keyword_score(question, content)
    phrase = _phrase_score(question, content)

    return _clamp_score(article + keyword + phrase)


def _vector_score(raw_score: float) -> float:
    """
    Qdrant cosine scores are higher-is-better.
    Clamp to [0, 1] for consistent final scoring.
    """
    return _clamp_score(raw_score)


def _sqlite_candidates(
    tenant_id: str,
    namespaces: list[str],
    question: str,
    hint_article_number: str | None,
) -> list[Chunk]:
    raw_chunks = store.list_chunks(tenant_id=tenant_id, namespaces=namespaces)

    candidates: list[Chunk] = []

    for raw in raw_chunks:
        score = _lexical_final_score(
            question=question,
            content=raw["content"],
            chunk_article=raw.get("article_number"),
            hint_article_number=hint_article_number,
        )

        # Keep only relevant lexical/article candidates.
        if score < 0.15:
            continue

        payload = dict(raw)
        payload["score"] = score
        candidates.append(Chunk(**payload))

    return candidates


def _qdrant_candidates(
    tenant_id: str,
    namespaces: list[str],
    question: str,
    top_k: int,
) -> list[Chunk]:
    if settings.vector_store.lower() != "qdrant":
        return []

    if not namespaces:
        return []

    query_vector = embed_text(question)

    vector_chunks = vector_store.search_chunks(
        tenant_id=tenant_id,
        namespaces=namespaces,
        query_vector=query_vector,
        top_k=max(top_k * 2, 10),
    )

    candidates: list[Chunk] = []

    for chunk in vector_chunks:
        score = _vector_score(chunk.score)

        # Avoid hallucination from weak vector-only matches.
        if score < 0.45:
            continue

        chunk.score = score
        candidates.append(chunk)

    return candidates


def _merge_and_rerank(
    question: str,
    hint_article_number: str | None,
    lexical_chunks: list[Chunk],
    vector_chunks: list[Chunk],
) -> list[Chunk]:
    by_chunk_id: dict[str, Chunk] = {}
    vector_scores: dict[str, float] = {}
    lexical_scores: dict[str, float] = {}

    for chunk in vector_chunks:
        by_chunk_id[chunk.chunk_id] = chunk
        vector_scores[chunk.chunk_id] = chunk.score

    for chunk in lexical_chunks:
        by_chunk_id[chunk.chunk_id] = chunk
        lexical_scores[chunk.chunk_id] = chunk.score

    reranked: list[Chunk] = []

    for chunk_id, chunk in by_chunk_id.items():
        lexical = lexical_scores.get(chunk_id)

        if lexical is None:
            lexical = _lexical_final_score(
                question=question,
                content=chunk.content,
                chunk_article=chunk.article_number,
                hint_article_number=hint_article_number,
            )

        vector = vector_scores.get(chunk_id, 0.0)
        article = _article_score(chunk.article_number, hint_article_number)

        # Hybrid score:
        # - exact article match is strongest for legal documents
        # - vector search helps semantic retrieval
        # - lexical/phrase score protects against vector-only false positives
        if article > 0:
            final_score = max(article, lexical) + 0.10 * vector
        elif vector > 0:
            final_score = 0.65 * vector + 0.35 * lexical
        else:
            final_score = lexical

        chunk.score = _clamp_score(final_score)

        if chunk.score >= 0.25:
            reranked.append(chunk)

    reranked.sort(key=lambda item: item.score, reverse=True)
    return reranked


def _ensure_namespace_diversity(
    chunks: list[Chunk],
    requested_namespaces: list[str],
    top_k: int,
) -> list[Chunk]:
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
    lexical_chunks = _sqlite_candidates(
        tenant_id=tenant_id,
        namespaces=namespaces,
        question=question,
        hint_article_number=hint_article_number,
    )

    vector_chunks = _qdrant_candidates(
        tenant_id=tenant_id,
        namespaces=namespaces,
        question=question,
        top_k=top_k,
    )

    merged = _merge_and_rerank(
        question=question,
        hint_article_number=hint_article_number,
        lexical_chunks=lexical_chunks,
        vector_chunks=vector_chunks,
    )

    return _ensure_namespace_diversity(
        chunks=merged,
        requested_namespaces=namespaces,
        top_k=top_k,
    )