from app.services.legal_chunker import chunk_legal_text


def test_legal_chunker_splits_articles_and_extracts_numbers():
    text = (
        "Legea 31/1990 privind societățile comerciale\n\n"
        "Articolul 15.\n"
        "Aporturile în numerar sunt obligatorii.\n\n"
        "Articolul 16.\n"
        "Aporturile în natură trebuie să fie evaluabile."
    )

    chunks = chunk_legal_text(text)

    assert len(chunks) == 2
    assert chunks[0].article_number == "15"
    assert chunks[1].article_number == "16"
    assert "Aporturile în numerar" in chunks[0].content
    assert "Aporturile în natură" in chunks[1].content
    assert "document_preamble" in chunks[0].metadata


def test_legal_chunker_attaches_section_title():
    text = (
        "CAPITOLUL II\n"
        "Dispoziții privind constituirea societăților\n\n"
        "SECȚIUNEA 1\n"
        "Dispoziții generale\n\n"
        "Articolul 15.\n"
        "Aporturile în numerar sunt obligatorii."
    )

    chunks = chunk_legal_text(text)

    assert len(chunks) == 1
    assert chunks[0].article_number == "15"
    assert chunks[0].section_title == "SECȚIUNEA 1"
    assert "CAPITOLUL II" in chunks[0].metadata["headings"]
    assert "SECȚIUNEA 1" in chunks[0].metadata["headings"]


def test_legal_chunker_extracts_paragraph_and_point_metadata():
    text = (
        "Articolul 15.\n"
        "(1) Aporturile în numerar sunt obligatorii.\n"
        "a) primul punct;\n"
        "b) al doilea punct."
    )

    chunks = chunk_legal_text(text)

    assert len(chunks) == 1
    assert chunks[0].article_number == "15"
    assert chunks[0].metadata["paragraph_number"] == "1"
    assert chunks[0].point_number == "a"


def test_legal_chunker_splits_long_articles():
    repeated = "Aporturile în numerar sunt obligatorii la constituirea societății. " * 80

    text = (
        "Articolul 99.\n"
        f"{repeated}"
    )

    chunks = chunk_legal_text(
        text,
        max_chunk_chars=1000,
        overlap_chars=100,
    )

    assert len(chunks) > 1
    assert all(chunk.article_number == "99" for chunk in chunks)
    assert all(len(chunk.content) <= 1000 for chunk in chunks)
    assert chunks[0].metadata["chunk_total"] == len(chunks)