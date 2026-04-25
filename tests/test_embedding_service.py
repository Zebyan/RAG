from app.config import settings
from app.services.embedding_service import embed_text, embed_texts


def test_embed_text_returns_expected_dimension():
    vector = embed_text("Aporturile în numerar sunt obligatorii.")

    assert isinstance(vector, list)
    assert len(vector) == settings.embedding_dim
    assert all(isinstance(value, float) for value in vector)


def test_embed_texts_returns_multiple_vectors():
    texts = [
        "Aporturile în numerar sunt obligatorii.",
        "Aporturile în natură trebuie să fie evaluabile.",
    ]

    vectors = embed_texts(texts)

    assert len(vectors) == 2
    assert len(vectors[0]) == settings.embedding_dim
    assert len(vectors[1]) == settings.embedding_dim