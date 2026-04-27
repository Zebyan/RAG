from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any
from uuid import uuid4

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
API_KEY = sys.argv[2] if len(sys.argv) > 2 else "test-api-key"
TENANT_ID = sys.argv[3] if len(sys.argv) > 3 else "endpoint-test-tenant"

RUN_SUFFIX = time.strftime("%Y%m%d%H%M%S")
MAIN_NAMESPACE_ID = f"legea_31_1990_endpoint_test_{RUN_SUFFIX}"
MAIN_SOURCE_ID = f"s_47381_endpoint_test_{RUN_SUFFIX}"
SECOND_NAMESPACE_ID = f"cod_civil_endpoint_test_{RUN_SUFFIX}"
SECOND_SOURCE_ID = f"s_cod_civil_endpoint_test_{RUN_SUFFIX}"
FILE_NAMESPACE_ID = f"file_upload_endpoint_test_{RUN_SUFFIX}"
FILE_SOURCE_ID = f"s_file_upload_endpoint_test_{RUN_SUFFIX}"
DELETE_NAMESPACE_ID = f"delete_namespace_endpoint_test_{RUN_SUFFIX}"
DELETE_NAMESPACE_SOURCE_ID = f"s_delete_namespace_endpoint_test_{RUN_SUFFIX}"


def step(title: str) -> None:
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def dump(obj: Any) -> None:
    if obj is None:
        print("<empty body>")
        return
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(f"ASSERTION FAILED: {message}")
    print(f"[OK] {message}")


def assert_error(payload: Any, expected_code: str) -> None:
    assert_true(isinstance(payload, dict), "error response is JSON object")
    assert_true("error" in payload, "error response has error object")
    error = payload["error"]
    assert_true(error.get("code") == expected_code, f"error code is {expected_code}")
    assert_true("message" in error, "error response has message")
    assert_true("request_id" in error, "error response has request_id")


def auth_headers(request_id: str | None = None, tenant_id: str | None = None, api_key: str | None = None) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key or API_KEY}",
        "X-Request-ID": request_id or str(uuid4()),
        "X-Tenant-ID": tenant_id or TENANT_ID,
    }


def ingest_headers(
    request_id: str | None = None,
    tenant_id: str | None = None,
    api_key: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, str]:
    headers = auth_headers(request_id=request_id, tenant_id=tenant_id, api_key=api_key)
    headers["Idempotency-Key"] = idempotency_key or str(uuid4())
    return headers


def request_json(
    method: str,
    path: str,
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    expect_status: int | None = None,
) -> tuple[int, Any, dict[str, str]]:
    url = f"{BASE_URL}{path}"
    final_headers = dict(headers or {})
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        final_headers["Content-Type"] = "application/json; charset=utf-8"

    req = urllib.request.Request(url=url, data=data, headers=final_headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            status = response.status
            raw = response.read()
            response_headers = dict(response.headers.items())
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read()
        response_headers = dict(exc.headers.items())

    text = raw.decode("utf-8") if raw else ""
    payload = json.loads(text) if text else None

    if expect_status is not None and status != expect_status:
        print(f"Unexpected status. Expected {expect_status}, got {status}")
        print(text)
        raise AssertionError(f"{method} {path} returned {status}")

    return status, payload, response_headers


def request_multipart(
    method: str,
    path: str,
    headers: dict[str, str] | None = None,
    fields: dict[str, str] | None = None,
    files: dict[str, tuple[str, bytes, str]] | None = None,
    expect_status: int | None = None,
) -> tuple[int, Any, dict[str, str]]:
    url = f"{BASE_URL}{path}"
    boundary = f"----SmokeBoundary{uuid4().hex}"
    body_parts: list[bytes] = []

    for name, value in (fields or {}).items():
        body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
        body_parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        body_parts.append(value.encode("utf-8"))
        body_parts.append(b"\r\n")

    for name, (filename, content, content_type) in (files or {}).items():
        body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
        body_parts.append(
            (
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                f"Content-Type: {content_type}\r\n\r\n"
            ).encode("utf-8")
        )
        body_parts.append(content)
        body_parts.append(b"\r\n")

    body_parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    data = b"".join(body_parts)

    final_headers = dict(headers or {})
    final_headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    final_headers["Content-Length"] = str(len(data))

    req = urllib.request.Request(url=url, data=data, headers=final_headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            status = response.status
            raw = response.read()
            response_headers = dict(response.headers.items())
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read()
        response_headers = dict(exc.headers.items())

    text = raw.decode("utf-8") if raw else ""
    payload = json.loads(text) if text else None

    if expect_status is not None and status != expect_status:
        print(f"Unexpected status. Expected {expect_status}, got {status}")
        print(text)
        raise AssertionError(f"{method} {path} returned {status}")

    return status, payload, response_headers


def assert_standard_headers(response_headers: dict[str, str], expected_request_id: str | None = None) -> None:
    normalized = {key.lower(): value for key, value in response_headers.items()}
    assert_true("x-vendor-trace-id" in normalized, "X-Vendor-Trace-ID header is present")
    assert_true("server-timing" in normalized, "Server-Timing header is present")
    if expected_request_id:
        assert_true(normalized.get("x-request-id") == expected_request_id, "X-Request-ID header is echoed")


def assert_query_headers(response_headers: dict[str, str]) -> None:
    normalized = {key.lower(): value for key, value in response_headers.items()}
    assert_true(
        normalized.get("x-vendor-retrieval-strategy") in {"hybrid_qdrant_article_keyword", "article_keyword_mvp"},
        "X-Vendor-Retrieval-Strategy header is present",
    )


def ingest_text_source(namespace_id: str, source_id: str, text: str, source_title: str, url: str) -> str:
    body = {
        "namespace_id": namespace_id,
        "source_id": source_id,
        "source_type": "url",
        "url": url,
        "mime_type_hint": "text/plain",
        "metadata": {"source_title": source_title, "text": text},
    }
    _, response, _ = request_json("POST", "/v1/ingest", headers=ingest_headers(), body=body, expect_status=202)
    assert_true(response["job_id"].startswith("j_"), "ingest returns job_id")
    assert_true(response["status"] == "queued", "ingest returns queued status")
    return response["job_id"]


def poll_job(job_id: str) -> dict[str, Any]:
    _, response, _ = request_json("GET", f"/v1/ingest/{job_id}", headers=auth_headers(), expect_status=200)
    return response


def main() -> None:
    print(f"Base URL:          {BASE_URL}")
    print(f"Tenant ID:         {TENANT_ID}")
    print(f"Main namespace:    {MAIN_NAMESPACE_ID}")
    print(f"Main source:       {MAIN_SOURCE_ID}")

    step("1. GET /v1/health")
    _, health, health_headers = request_json("GET", "/v1/health", expect_status=200)
    dump(health)
    assert_true(health["status"] in {"ok", "degraded"}, "health status is ok/degraded")
    assert_true("version" in health, "health response has version")
    assert_true("uptime_seconds" in health, "health response has uptime_seconds")
    assert_true("vector_store" in health["dependencies"], "vector_store dependency is present")
    assert_true("llm" in health["dependencies"], "llm dependency is present")
    assert_true("object_store" in health["dependencies"], "object_store dependency is present")
    assert_standard_headers(health_headers)

    step("2. GET /v1/openapi.json")
    _, openapi, _ = request_json("GET", "/v1/openapi.json", expect_status=200)
    print(f"OpenAPI title: {openapi['info']['title']}")
    assert_true("openapi" in openapi, "OpenAPI version field is present")
    assert_true("paths" in openapi, "OpenAPI paths field is present")

    step("3. POST /v1/query - missing Authorization returns 401")
    _, missing_auth, _ = request_json(
        "POST",
        "/v1/query",
        headers={"X-Request-ID": str(uuid4()), "X-Tenant-ID": TENANT_ID},
        body={"question": "Ce spune articolul 15?", "language": "ro", "namespaces": [MAIN_NAMESPACE_ID]},
        expect_status=401,
    )
    dump(missing_auth)
    assert_error(missing_auth, "unauthorized")

    step("4. POST /v1/query - invalid API key returns 401")
    _, invalid_key, _ = request_json(
        "POST",
        "/v1/query",
        headers=auth_headers(api_key="wrong-api-key"),
        body={"question": "Ce spune articolul 15?", "language": "ro", "namespaces": [MAIN_NAMESPACE_ID]},
        expect_status=401,
    )
    dump(invalid_key)
    assert_error(invalid_key, "unauthorized")

    step("5. POST /v1/query - validation error returns 422")
    _, validation_error, _ = request_json(
        "POST",
        "/v1/query",
        headers=auth_headers(),
        body={"language": "ro", "namespaces": [MAIN_NAMESPACE_ID]},
        expect_status=422,
    )
    dump(validation_error)
    assert_error(validation_error, "validation_error")
    assert_true("errors" in validation_error["error"]["details"], "validation error includes errors list")

    step("6. POST /v1/ingest - JSON with metadata.text")
    main_text = (
        "Articolul 15. Aporturile în numerar sunt obligatorii la constituirea oricărei forme de societate.\n\n"
        "Articolul 16. Aporturile în natură trebuie să fie evaluabile din punct de vedere economic."
    )
    main_job_id = ingest_text_source(
        namespace_id=MAIN_NAMESPACE_ID,
        source_id=MAIN_SOURCE_ID,
        text=main_text,
        source_title="Legea 31/1990 privind societățile comerciale",
        url="https://legislatie.just.ro/Public/DetaliiDocument/47381",
    )

    step("7. GET /v1/ingest/{job_id} - JSON ingest status")
    main_job = poll_job(main_job_id)
    dump(main_job)
    assert_true(main_job["job_id"] == main_job_id, "job status returns same job_id")
    assert_true(main_job["status"] == "done", "job status is done")
    assert_true(main_job["progress"]["percent"] == 100, "job progress is 100")
    assert_true(main_job["progress"]["chunks_created"] >= 2, "job created at least 2 chunks")

    step("8. POST /v1/ingest - idempotency same key + same body")
    idem_key = str(uuid4())
    idem_body = {
        "namespace_id": f"idempotency_namespace_{RUN_SUFFIX}",
        "source_id": f"s_idempotency_{RUN_SUFFIX}",
        "source_type": "url",
        "url": "https://example.com/idempotency",
        "mime_type_hint": "text/plain",
        "metadata": {"source_title": "Idempotency Test", "text": "Articolul 15. Aporturile în numerar sunt obligatorii."},
    }
    _, first_idem, _ = request_json("POST", "/v1/ingest", headers=ingest_headers(idempotency_key=idem_key), body=idem_body, expect_status=202)
    _, second_idem, _ = request_json("POST", "/v1/ingest", headers=ingest_headers(idempotency_key=idem_key), body=idem_body, expect_status=202)
    dump(second_idem)
    assert_true(first_idem["job_id"] == second_idem["job_id"], "same idempotency key and body returns same job_id")

    step("9. POST /v1/ingest - idempotency same key + different body returns 409")
    changed_body = dict(idem_body)
    changed_body["source_id"] = f"s_idempotency_changed_{RUN_SUFFIX}"
    _, idem_conflict, _ = request_json("POST", "/v1/ingest", headers=ingest_headers(idempotency_key=idem_key), body=changed_body, expect_status=409)
    dump(idem_conflict)
    assert_error(idem_conflict, "duplicate_job")

    step("10. POST /v1/ingest - unsupported MIME returns 415")
    _, unsupported_mime, _ = request_json(
        "POST",
        "/v1/ingest",
        headers=ingest_headers(),
        body={
            "namespace_id": f"bad_mime_namespace_{RUN_SUFFIX}",
            "source_id": f"s_bad_mime_{RUN_SUFFIX}",
            "source_type": "url",
            "url": "https://example.com/data.json",
            "mime_type_hint": "application/json",
            "metadata": {"source_title": "Bad MIME", "text": "{}"},
        },
        expect_status=415,
    )
    dump(unsupported_mime)
    assert_error(unsupported_mime, "unsupported_media_type")

    step("11. POST /v1/ingest - source_type=url without url returns 422")
    _, missing_url, _ = request_json(
        "POST",
        "/v1/ingest",
        headers=ingest_headers(),
        body={
            "namespace_id": f"missing_url_namespace_{RUN_SUFFIX}",
            "source_id": f"s_missing_url_{RUN_SUFFIX}",
            "source_type": "url",
            "mime_type_hint": "text/plain",
            "metadata": {"source_title": "Missing URL"},
        },
        expect_status=422,
    )
    dump(missing_url)
    assert_error(missing_url, "validation_error")

    step("12. POST /v1/ingest - multipart file upload")
    file_payload = {
        "namespace_id": FILE_NAMESPACE_ID,
        "source_id": FILE_SOURCE_ID,
        "source_type": "file",
        "mime_type_hint": "text/plain",
        "metadata": {"source_title": "Uploaded Legal Text"},
    }
    file_content = (
        "Articolul 15.\n"
        "Aporturile în numerar sunt obligatorii la constituirea oricărei forme de societate."
    ).encode("utf-8")
    _, file_ingest, _ = request_multipart(
        "POST",
        "/v1/ingest",
        headers=ingest_headers(),
        fields={"payload": json.dumps(file_payload, ensure_ascii=False)},
        files={"file": ("legea_31.txt", file_content, "text/plain")},
        expect_status=202,
    )
    dump(file_ingest)
    assert_true(file_ingest["job_id"].startswith("j_"), "multipart ingest returns job_id")

    step("13. GET /v1/ingest/{job_id} - multipart file status")
    file_job = poll_job(file_ingest["job_id"])
    dump(file_job)
    assert_true(file_job["status"] == "done", "multipart ingest job is done")

    step("14. POST /v1/ingest - multipart missing payload returns 422")
    _, missing_payload, _ = request_multipart(
        "POST",
        "/v1/ingest",
        headers=ingest_headers(),
        files={"file": ("legea_31.txt", b"Articolul 15.", "text/plain")},
        expect_status=422,
    )
    dump(missing_payload)
    assert_error(missing_payload, "validation_error")

    step("15. POST /v1/ingest - multipart missing file returns 422")
    _, missing_file, _ = request_multipart(
        "POST",
        "/v1/ingest",
        headers=ingest_headers(),
        fields={"payload": json.dumps(file_payload, ensure_ascii=False)},
        expect_status=422,
    )
    dump(missing_file)
    assert_error(missing_file, "validation_error")

    step("16. POST /v1/query - exact article 15")
    query_15 = {
        "question": "Ce spune articolul 15 din Legea 31/1990?",
        "language": "ro",
        "namespaces": [MAIN_NAMESPACE_ID],
        "top_k": 5,
        "hint_article_number": "15",
        "rerank": True,
        "include_answer": True,
    }
    query_request_id = str(uuid4())
    _, response_15, query_headers = request_json("POST", "/v1/query", headers=auth_headers(request_id=query_request_id), body=query_15, expect_status=200)
    dump(response_15)
    content_15 = response_15["citations"][0]["chunk"]["content"]
    assert_true(response_15["request_id"] == query_request_id, "query response request_id matches")
    assert_true(response_15["answer"] is not None, "article 15 answer is not null")
    assert_true("[1]" in response_15["answer"], "article 15 answer contains [1]")
    assert_true(len(response_15["citations"]) >= 1, "article 15 has at least one citation")
    assert_true(response_15["citations"][0]["chunk"]["article_number"] == "15", "first citation is article 15")
    assert_true("Aporturile în numerar" in content_15, "article 15 content is correct")
    assert_true(response_15["confidence"] > 0, "article 15 confidence is greater than zero")
    assert_standard_headers(query_headers, expected_request_id=query_request_id)
    assert_query_headers(query_headers)

    step("17. POST /v1/query - exact article 16")
    query_16 = {"question": "Ce spune articolul 16?", "language": "ro", "namespaces": [MAIN_NAMESPACE_ID], "top_k": 5, "hint_article_number": "16", "include_answer": True}
    _, response_16, _ = request_json("POST", "/v1/query", headers=auth_headers(), body=query_16, expect_status=200)
    dump(response_16)
    content_16 = response_16["citations"][0]["chunk"]["content"]
    assert_true(response_16["answer"] is not None, "article 16 answer is not null")
    assert_true(response_16["citations"][0]["chunk"]["article_number"] == "16", "first citation is article 16")
    assert_true("Aporturile în natură" in content_16, "article 16 content is correct")
    assert_true("Aporturile în numerar" not in content_16, "article 16 does not contain article 15 content")

    step("18. POST /v1/query - include_answer=false returns citations only")
    query_retrieval_only = {"question": "Ce spune articolul 15?", "language": "ro", "namespaces": [MAIN_NAMESPACE_ID], "top_k": 5, "hint_article_number": "15", "include_answer": False}
    _, retrieval_only, _ = request_json("POST", "/v1/query", headers=auth_headers(), body=query_retrieval_only, expect_status=200)
    dump(retrieval_only)
    assert_true(retrieval_only["answer"] is None, "retrieval-only answer is null")
    assert_true(len(retrieval_only["citations"]) >= 1, "retrieval-only returns citations")

    step("19. POST /v1/query - uploaded file namespace")
    query_file = {"question": "Ce spune articolul 15?", "language": "ro", "namespaces": [FILE_NAMESPACE_ID], "top_k": 5, "hint_article_number": "15", "include_answer": True}
    _, file_query, _ = request_json("POST", "/v1/query", headers=auth_headers(), body=query_file, expect_status=200)
    dump(file_query)
    assert_true(file_query["answer"] is not None, "uploaded file query returns answer")
    assert_true(file_query["citations"][0]["chunk"]["metadata"]["text_source"] == "uploaded_file", "citation metadata marks uploaded_file")
    assert_true(file_query["citations"][0]["chunk"]["metadata"]["uploaded_filename"] == "legea_31.txt", "citation metadata includes uploaded filename")

    step("20. POST /v1/query - empty result / no hallucination")
    query_empty = {"question": "Care este programul primăriei Bălta Doamnei?", "language": "ro", "namespaces": [MAIN_NAMESPACE_ID], "top_k": 5, "include_answer": True}
    _, empty, _ = request_json("POST", "/v1/query", headers=auth_headers(), body=query_empty, expect_status=200)
    dump(empty)
    assert_true(empty["answer"] is None, "empty query answer is null")
    assert_true(empty["citations"] == [], "empty query citations are empty")
    assert_true(empty["confidence"] == 0.0, "empty query confidence is 0.0")

    step("21. POST /v1/query - cross-tenant isolation")
    _, cross_tenant, _ = request_json("POST", "/v1/query", headers=auth_headers(tenant_id=f"another-tenant-{RUN_SUFFIX}"), body=query_15, expect_status=200)
    dump(cross_tenant)
    assert_true(cross_tenant["answer"] is None, "other tenant cannot see answer")
    assert_true(cross_tenant["citations"] == [], "other tenant cannot see citations")
    assert_true(cross_tenant["confidence"] == 0.0, "other tenant confidence is 0.0")

    step("22. POST /v1/query - multi-namespace retrieval")
    second_job_id = ingest_text_source(
        namespace_id=SECOND_NAMESPACE_ID,
        source_id=SECOND_SOURCE_ID,
        text="Articolul 200. Persoana juridică răspunde pentru obligațiile sale potrivit legii.",
        source_title="Codul Civil - Test",
        url="https://example.com/cod-civil",
    )
    second_job = poll_job(second_job_id)
    assert_true(second_job["status"] == "done", "second namespace ingest is done")
    multi_query = {"question": "Ce spune legea despre aporturi și obligații?", "language": "ro", "namespaces": [MAIN_NAMESPACE_ID, SECOND_NAMESPACE_ID], "top_k": 10, "include_answer": True}
    _, multi_response, _ = request_json("POST", "/v1/query", headers=auth_headers(), body=multi_query, expect_status=200)
    dump(multi_response)
    returned_namespaces = {citation["chunk"]["namespace_id"] for citation in multi_response["citations"]}
    assert_true(bool(returned_namespaces.intersection({MAIN_NAMESPACE_ID, SECOND_NAMESPACE_ID})), "multi-namespace query returns configured namespace")

    step("23. GET /v1/namespaces/{namespace_id}/stats")
    _, stats, _ = request_json("GET", f"/v1/namespaces/{MAIN_NAMESPACE_ID}/stats", headers=auth_headers(), expect_status=200)
    dump(stats)
    assert_true(stats["namespace_id"] == MAIN_NAMESPACE_ID, "stats namespace_id is correct")
    assert_true(stats["chunk_count"] >= 2, "stats chunk_count >= 2")
    assert_true(stats["source_count"] >= 1, "stats source_count >= 1")
    assert_true(stats["embedding_dim"] > 0, "stats embedding_dim is positive")

    step("24. GET /v1/namespaces/{namespace_id}/stats - missing namespace returns 404")
    _, missing_stats, _ = request_json("GET", f"/v1/namespaces/missing_namespace_{RUN_SUFFIX}/stats", headers=auth_headers(), expect_status=404)
    dump(missing_stats)
    assert_error(missing_stats, "namespace_not_found")

    step("25. DELETE /v1/namespaces/{namespace_id}/sources/{source_id}")
    status, _, _ = request_json("DELETE", f"/v1/namespaces/{MAIN_NAMESPACE_ID}/sources/{MAIN_SOURCE_ID}", headers=auth_headers(), expect_status=204)
    assert_true(status == 204, "delete source returns 204")

    step("26. Verify source deletion")
    _, after_source_delete, _ = request_json("POST", "/v1/query", headers=auth_headers(), body=query_15, expect_status=200)
    dump(after_source_delete)
    assert_true(after_source_delete["answer"] is None, "after source delete answer is null")
    assert_true(after_source_delete["citations"] == [], "after source delete citations are empty")
    assert_true(after_source_delete["confidence"] == 0.0, "after source delete confidence is 0.0")

    step("27. DELETE /v1/namespaces/{namespace_id}/sources/{source_id} - missing source returns 404")
    _, missing_source_delete, _ = request_json("DELETE", f"/v1/namespaces/{MAIN_NAMESPACE_ID}/sources/missing_source_{RUN_SUFFIX}", headers=auth_headers(), expect_status=404)
    dump(missing_source_delete)
    assert_error(missing_source_delete, "not_found")

    step("28. POST /v1/ingest - setup namespace delete test")
    delete_namespace_job_id = ingest_text_source(
        namespace_id=DELETE_NAMESPACE_ID,
        source_id=DELETE_NAMESPACE_SOURCE_ID,
        text="Articolul 15. Aporturile în numerar sunt obligatorii la constituirea oricărei forme de societate.",
        source_title="Delete Namespace Test",
        url="https://example.com/delete-namespace-test",
    )
    delete_namespace_job = poll_job(delete_namespace_job_id)
    assert_true(delete_namespace_job["status"] == "done", "delete namespace setup ingest is done")

    step("29. DELETE /v1/namespaces/{namespace_id}")
    _, delete_namespace_response, _ = request_json("DELETE", f"/v1/namespaces/{DELETE_NAMESPACE_ID}", headers=auth_headers(), expect_status=202)
    dump(delete_namespace_response)
    assert_true(delete_namespace_response.get("job_id", "").startswith("del_"), "delete namespace returns deletion job_id")
    assert_true(delete_namespace_response.get("status") == "queued", "delete namespace status is queued")
    assert_true(delete_namespace_response.get("sla") == "24h", "delete namespace sla is 24h")

    step("30. Verify namespace deletion")
    _, after_namespace_delete_query, _ = request_json(
        "POST",
        "/v1/query",
        headers=auth_headers(),
        body={"question": "Ce spune articolul 15?", "language": "ro", "namespaces": [DELETE_NAMESPACE_ID], "top_k": 5, "hint_article_number": "15", "include_answer": True},
        expect_status=200,
    )
    dump(after_namespace_delete_query)
    assert_true(after_namespace_delete_query["answer"] is None, "after namespace delete answer is null")
    assert_true(after_namespace_delete_query["citations"] == [], "after namespace delete citations are empty")
    assert_true(after_namespace_delete_query["confidence"] == 0.0, "after namespace delete confidence is 0.0")

    step("ALL ENDPOINT SMOKE TESTS PASSED")


if __name__ == "__main__":
    main()
