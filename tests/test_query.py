from pathlib import Path

def test_query_empty_without_ingest(client, auth_headers):
    response = client.post(
        "/v1/query",
        headers=auth_headers,
        json={
            "question": "Care este programul primăriei Bălta Doamnei?",
            "language": "ro",
            "namespaces": ["legea_31_1990"],
            "top_k": 5,
            "include_answer": True,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] is None
    assert data["citations"] == []
    assert data["confidence"] == 0.0


def test_query_exact_article_after_ingest(client, auth_headers):
    ingest_headers = {
        **auth_headers,
        "Idempotency-Key": "44444444-4444-4444-8444-444444444444",
    }

    ingest_response = client.post(
        "/v1/ingest",
        headers=ingest_headers,
        json={
            "namespace_id": "legea_31_1990",
            "source_id": "s_47381",
            "source_type": "url",
            "url": "https://legislatie.just.ro/Public/DetaliiDocument/47381",
            "mime_type_hint": "text/plain",
            "metadata": {
                "source_title": "Legea 31/1990 privind societățile comerciale",
                "text": "Articolul 15. Aporturile în numerar sunt obligatorii la constituirea oricărei forme de societate.",
            },
        },
    )
    assert ingest_response.status_code == 202

    query_response = client.post(
        "/v1/query",
        headers=auth_headers,
        json={
            "question": "Ce spune articolul 15 din Legea 31/1990?",
            "language": "ro",
            "namespaces": ["legea_31_1990"],
            "top_k": 5,
            "hint_article_number": "15",
            "rerank": True,
            "include_answer": True,
        },
    )

    assert query_response.status_code == 200
    data = query_response.json()
    assert data["answer"] is not None
    assert "[1]" in data["answer"]
    assert data["citations"][0]["chunk"]["article_number"] == "15"
    assert "aporturile în numerar" in data["citations"][0]["chunk"]["content"].lower()

def test_wrong_namespace_returns_empty_result(client, auth_headers):
    ingest_headers = {
        **auth_headers,
        "Idempotency-Key": "23232323-2323-4232-8232-232323232323",
    }

    client.post(
        "/v1/ingest",
        headers=ingest_headers,
        json={
            "namespace_id": "legea_31_1990",
            "source_id": "s_wrong_namespace_test",
            "source_type": "url",
            "url": "https://example.com/legea31",
            "mime_type_hint": "text/plain",
            "metadata": {
                "text": "Articolul 15. Aporturile în numerar sunt obligatorii la constituirea oricărei forme de societate."
            },
        },
    )

    response = client.post(
        "/v1/query",
        headers=auth_headers,
        json={
            "question": "Ce spune articolul 15?",
            "language": "ro",
            "namespaces": ["cod_civil"],
            "top_k": 5,
            "hint_article_number": "15",
            "include_answer": True,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] is None
    assert data["citations"] == []
    assert data["confidence"] == 0.0

def test_cross_tenant_isolation(client):
    tenant_a_headers = {
        "Authorization": "Bearer test-api-key",
        "X-Request-ID": "67676767-6767-4676-8676-676767676767",
        "X-Tenant-ID": "tenant-a",
    }
    tenant_a_ingest_headers = {
        **tenant_a_headers,
        "Idempotency-Key": "67676767-6767-4676-8676-676767676768",
    }

    tenant_b_headers = {
        "Authorization": "Bearer test-api-key",
        "X-Request-ID": "78787878-7878-4787-8787-787878787878",
        "X-Tenant-ID": "tenant-b",
    }

    ingest = client.post(
        "/v1/ingest",
        headers=tenant_a_ingest_headers,
        json={
            "namespace_id": "shared_namespace",
            "source_id": "s_tenant_a",
            "source_type": "url",
            "url": "https://example.com/tenant-a",
            "mime_type_hint": "text/plain",
            "metadata": {
                "text": "Articolul 15. Acest text aparține doar tenantului A."
            },
        },
    )
    assert ingest.status_code == 202

    response = client.post(
        "/v1/query",
        headers=tenant_b_headers,
        json={
            "question": "Ce spune articolul 15?",
            "language": "ro",
            "namespaces": ["shared_namespace"],
            "top_k": 5,
            "hint_article_number": "15",
            "include_answer": True,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] is None
    assert data["citations"] == []
    assert data["confidence"] == 0.0

def test_language_not_ro_returns_422(client, auth_headers):
    response = client.post(
        "/v1/query",
        headers=auth_headers,
        json={
            "question": "What does article 15 say?",
            "language": "en",
            "namespaces": ["legea_31_1990"],
        },
    )

    assert response.status_code == 422


def test_top_k_over_50_returns_422(client, auth_headers):
    response = client.post(
        "/v1/query",
        headers=auth_headers,
        json={
            "question": "Ce spune articolul 15?",
            "language": "ro",
            "namespaces": ["legea_31_1990"],
            "top_k": 100,
        },
    )

    assert response.status_code == 422


def test_empty_namespaces_returns_422(client, auth_headers):
    response = client.post(
        "/v1/query",
        headers=auth_headers,
        json={
            "question": "Ce spune articolul 15?",
            "language": "ro",
            "namespaces": [],
        },
    )

    assert response.status_code == 422

def test_diacritics_are_preserved_in_citation_content(client, auth_headers):
    ingest_headers = {
        **auth_headers,
        "Idempotency-Key": "91919191-9191-4919-8919-919191919191",
    }

    ingest_response = client.post(
        "/v1/ingest",
        headers=ingest_headers,
        json={
            "namespace_id": "diacritics_test",
            "source_id": "s_diacritics_test",
            "source_type": "url",
            "url": "https://example.com/diacritics",
            "mime_type_hint": "text/plain",
            "metadata": {
                "source_title": "Legea 31/1990 privind societățile comerciale",
                "text": "Articolul 15. Aporturile în numerar sunt obligatorii la constituirea oricărei forme de societate.",
            },
        },
    )

    assert ingest_response.status_code == 202

    query_response = client.post(
        "/v1/query",
        headers=auth_headers,
        json={
            "question": "Ce spune articolul 15?",
            "language": "ro",
            "namespaces": ["diacritics_test"],
            "top_k": 5,
            "hint_article_number": "15",
            "include_answer": True,
        },
    )

    assert query_response.status_code == 200

    data = query_response.json()
    content = data["citations"][0]["chunk"]["content"]

    assert "în numerar" in content
    assert "oricărei forme" in content
    assert "societate" in content
    assert "in numerar" not in content
    assert "oricarei" not in content

def test_query_without_article_hint_uses_keyword_and_phrase_matching(client, auth_headers):
    ingest_headers = {
        **auth_headers,
        "Idempotency-Key": "72727272-7272-4727-8727-727272727272",
    }

    ingest_response = client.post(
        "/v1/ingest",
        headers=ingest_headers,
        json={
            "namespace_id": "keyword_phrase_test",
            "source_id": "s_keyword_phrase_test",
            "source_type": "url",
            "url": "https://example.com/keyword-phrase",
            "mime_type_hint": "text/plain",
            "metadata": {
                "source_title": "Legea 31/1990 privind societățile comerciale",
                "text": (
                    "Articolul 15.\n"
                    "Aporturile în numerar sunt obligatorii la constituirea oricărei forme de societate.\n\n"
                    "Articolul 16.\n"
                    "Aporturile în natură trebuie să fie evaluabile din punct de vedere economic."
                ),
            },
        },
    )

    assert ingest_response.status_code == 202

    query_response = client.post(
        "/v1/query",
        headers=auth_headers,
        json={
            "question": "Ce sunt aporturile în natură?",
            "language": "ro",
            "namespaces": ["keyword_phrase_test"],
            "top_k": 5,
            "include_answer": True,
        },
    )

    assert query_response.status_code == 200

    data = query_response.json()

    assert data["answer"] is not None
    assert data["citations"][0]["chunk"]["article_number"] == "16"
    assert "Aporturile în natură" in data["citations"][0]["chunk"]["content"]

def test_query_without_diacritics_matches_content_with_diacritics(client, auth_headers):
    ingest_headers = {
        **auth_headers,
        "Idempotency-Key": "73737373-7373-4737-8737-737373737373",
    }

    ingest_response = client.post(
        "/v1/ingest",
        headers=ingest_headers,
        json={
            "namespace_id": "diacritic_normalization_test",
            "source_id": "s_diacritic_normalization_test",
            "source_type": "url",
            "url": "https://example.com/diacritic-normalization",
            "mime_type_hint": "text/plain",
            "metadata": {
                "source_title": "Legea 31/1990 privind societățile comerciale",
                "text": (
                    "Articolul 15.\n"
                    "Aporturile în numerar sunt obligatorii la constituirea oricărei forme de societate.\n\n"
                    "Articolul 16.\n"
                    "Aporturile în natură trebuie să fie evaluabile din punct de vedere economic."
                ),
            },
        },
    )

    assert ingest_response.status_code == 202

    query_response = client.post(
        "/v1/query",
        headers=auth_headers,
        json={
            "question": "Ce sunt aporturile in numerar?",
            "language": "ro",
            "namespaces": ["diacritic_normalization_test"],
            "top_k": 5,
            "include_answer": True,
        },
    )

    assert query_response.status_code == 200

    data = query_response.json()

    assert data["answer"] is not None
    assert data["citations"][0]["chunk"]["article_number"] == "15"
    assert "Aporturile în numerar" in data["citations"][0]["chunk"]["content"]

def test_multi_namespace_retrieval_returns_citations_from_both_namespaces(client, auth_headers):
    fixtures_dir = Path(__file__).resolve().parents[1] / "fixtures"
    lege_text = (fixtures_dir / "legea_31_1990_multi.txt").read_text(encoding="utf-8")
    cod_civil_text = (fixtures_dir / "cod_civil_multi.txt").read_text(encoding="utf-8")

    lege_headers = {
        **auth_headers,
        "Idempotency-Key": "83838383-8383-4838-8838-838383838383",
    }

    cod_civil_headers = {
        **auth_headers,
        "Idempotency-Key": "84848484-8484-4848-8848-848484848484",
    }

    lege_response = client.post(
        "/v1/ingest",
        headers=lege_headers,
        json={
            "namespace_id": "legea_31_1990_multi",
            "source_id": "s_legea_31_multi",
            "source_type": "url",
            "url": "https://example.com/legea-31",
            "mime_type_hint": "text/plain",
            "metadata": {
                "source_title": "Legea 31/1990 privind societățile comerciale",
                "text": lege_text,
            },
        },
    )

    assert lege_response.status_code == 202

    cod_response = client.post(
        "/v1/ingest",
        headers=cod_civil_headers,
        json={
            "namespace_id": "cod_civil_multi",
            "source_id": "s_cod_civil_multi",
            "source_type": "url",
            "url": "https://example.com/cod-civil",
            "mime_type_hint": "text/plain",
            "metadata": {
                "source_title": "Codul civil",
                "text": cod_civil_text,
            },
        },
    )

    assert cod_response.status_code == 202

    query_response = client.post(
        "/v1/query",
        headers=auth_headers,
        json={
            "question": "Cum se constituie o societate cu răspundere limitată și ce obligații au persoanele?",
            "language": "ro",
            "namespaces": ["legea_31_1990_multi", "cod_civil_multi"],
            "top_k": 5,
            "include_answer": True,
        },
    )

    assert query_response.status_code == 200

    data = query_response.json()

    namespaces = {
        citation["chunk"]["namespace_id"]
        for citation in data["citations"]
    }

    assert "legea_31_1990_multi" in namespaces
    assert "cod_civil_multi" in namespaces

    source_ids = {
        citation["chunk"]["source_id"]
        for citation in data["citations"]
    }

    assert "s_legea_31_multi" in source_ids
    assert "s_cod_civil_multi" in source_ids

def test_cod_civil_namespace_retrieval_alone(client, auth_headers):
    from pathlib import Path

    fixtures_dir = Path(__file__).resolve().parents[1] / "fixtures"
    cod_civil_text = (fixtures_dir / "cod_civil_multi.txt").read_text(encoding="utf-8")

    ingest_headers = {
        **auth_headers,
        "Idempotency-Key": "85858585-8585-4858-8858-858585858585",
    }

    ingest_response = client.post(
        "/v1/ingest",
        headers=ingest_headers,
        json={
            "namespace_id": "cod_civil_alone_test",
            "source_id": "s_cod_civil_alone_test",
            "source_type": "url",
            "url": "https://example.com/cod-civil-alone",
            "mime_type_hint": "text/plain",
            "metadata": {
                "source_title": "Codul civil",
                "text": cod_civil_text,
            },
        },
    )

    assert ingest_response.status_code == 202

    query_response = client.post(
        "/v1/query",
        headers=auth_headers,
        json={
            "question": "Ce obligații au persoanele?",
            "language": "ro",
            "namespaces": ["cod_civil_alone_test"],
            "top_k": 5,
            "include_answer": True,
        },
    )

    assert query_response.status_code == 200

    data = query_response.json()

    assert data["answer"] is not None
    assert data["citations"]
    assert data["citations"][0]["chunk"]["namespace_id"] == "cod_civil_alone_test"
    assert "obligațiile" in data["citations"][0]["chunk"]["content"]