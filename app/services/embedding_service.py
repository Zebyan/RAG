from __future__ import annotations

from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.config import settings


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    """
    Lazily load the embedding model once per process.

    This keeps application startup fast and loads the model only when
    embeddings are actually needed.
    """
    return SentenceTransformer(settings.embedding_model)


def embed_text(text: str) -> list[float]:
    """
    Embed one text string into a dense vector.
    """
    model = get_embedding_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.astype(float).tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embed multiple text strings into dense vectors.
    """
    if not texts:
        return []

    model = get_embedding_model()
    vectors = model.encode(texts, normalize_embeddings=True)
    return [vector.astype(float).tolist() for vector in vectors]