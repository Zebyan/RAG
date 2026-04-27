from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from typing import Any
from uuid import uuid4
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Full smoke test for the RAG /v1 API.")
    parser.add_argument("base_url", nargs="?", default="http://localhost:8080")
    parser.add_argument("api_key", nargs="?", default="test-api-key")
    parser.add_argument("tenant_id", nargs="?", default="endpoint-test-tenant")
    parser.add_argument(
        "--include-large-upload",
        action="store_true",
        help="Send a >50 MiB multipart upload and expect 413 payload_too_large.",
    )
    parser.add_argument(
        "--include-optional",
        action="store_true",
        help="Probe optional /metrics and /v1/eval endpoints. 404 is accepted.",
    )
    return parser.parse_args()


ARGS = parse_args()

BASE_URL = ARGS.base_url.rstrip("/")
API_KEY = ARGS.api_key
TENANT_ID = ARGS.tenant_id

RUN_SUFFIX = time.strftime("%Y%m%d%H%M%S")

MAIN_NAMESPACE_ID = f"legea_31_1990_smoke_{RUN_SUFFIX}"
MAIN_SOURCE_ID = f"s_legea_31_1990_smoke_{RUN_SUFFIX}"

SECOND_NAMESPACE_ID = f"cod_civil_smoke_{RUN_SUFFIX}"
SECOND_SOURCE_ID = f"s_cod_civil_smoke_{RUN_SUFFIX}"

FILE_NAMESPACE_ID = f"file_upload_smoke_{RUN_SUFFIX}"
FILE_SOURCE_ID = f"s_file_upload_smoke_{RUN_SUFFIX}"

DELETE_NAMESPACE_ID = f"delete_namespace_smoke_{RUN_SUFFIX}"
DELETE_NAMESPACE_SOURCE_ID = f"s_delete_namespace_smoke_{RUN_SUFFIX}"

URL_FETCH_NAMESPACE_ID = f"url_fetch_smoke_{RUN_SUFFIX}"
URL_FETCH_SOURCE_ID = f"s_url_fetch_smoke_{RUN_SUFFIX}"

MAX_DOCUMENT_BYTES = 50 * 1024 * 1024


def step(title: str) -> None:
    print()
    print("=" * 88)
    print(title)
    print("=" * 88)


def dump(obj: Any) -> None:
    if obj is None:
        print("<empty body>")
    else:
        print(json.dumps(obj, ensure_ascii=False, indent=2))


def ok(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(f"ASSERTION FAILED: {message}")
    print(f"[OK] {message}")


def expect_error(payload: Any, code: str) -> None:
    ok(isinstance(payload, dict), "error response is JSON object")
    ok("error" in payload, "error response has error object")
    err = payload["error"]
    ok(err.get("code") == code, f"error code is {code}")
    ok("message" in err, "error response has message")
    ok("request_id" in err, "error response has request_id")


def auth_headers(
    request_id: str | None = None,
    tenant_id: str | None = None,
    api_key: str | None = None,
) -> dict[str, str]:
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
    expect_status: int | set[int] | None = None,
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

    text = raw.decode("utf-8", errors="replace") if raw else ""
    payload = json.loads(text) if text else None

    if expect_status is not None:
        allowed = {expect_status} if isinstance(expect_status, int) else set(expect_status)
        if status not in allowed:
            print(f"Unexpected status. Expected {sorted(allowed)}, got {status}")
            print(text)
            raise AssertionError(f"{method} {path} returned {status}")

    return status, payload, response_headers


def request_raw(
    method: str,
    path: str,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    content_type: str | None = None,
    expect_status: int | set[int] | None = None,
) -> tuple[int, str, dict[str, str]]:
    final_headers = dict(headers or {})
    if content_type:
        final_headers["Content-Type"] = content_type

    req = urllib.request.Request(
        url=f"{BASE_URL}{path}",
        data=body,
        headers=final_headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(req) as response:
            status = response.status
            raw = response.read()
            response_headers = dict(response.headers.items())
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read()
        response_headers = dict(exc.headers.items())

    text = raw.decode("utf-8", errors="replace") if raw else ""

    if expect_status is not None:
        allowed = {expect_status} if isinstance(expect_status, int) else set(expect_status)
        if status not in allowed:
            print(f"Unexpected status. Expected {sorted(allowed)}, got {status}")
            print(text)
            raise AssertionError(f"{method} {path} returned {status}")

    return status, text, response_headers


def request_multipart(
    method: str,
    path: str,
    headers: dict[str, str] | None = None,
    fields: dict[str, str] | None = None,
    files: dict[str, tuple[str, bytes, str]] | None = None,
    expect_status: int | set[int] | None = None,
) -> tuple[int, Any, dict[str, str]]:
    boundary = f"----SmokeBoundary{uuid4().hex}"
    parts: list[bytes] = []

    for name, value in (fields or {}).items():
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        parts.append(value.encode("utf-8"))
        parts.append(b"\r\n")

    for name, (filename, content, content_type) in (files or {}).items():
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(
            (
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                f"Content-Type: {content_type}\r\n\r\n"
            ).encode()
        )
        parts.append(content)
        parts.append(b"\r\n")

    parts.append(f"--{boundary}--\r\n".encode())
    data = b"".join(parts)

    final_headers = dict(headers or {})
    final_headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    final_headers["Content-Length"] = str(len(data))

    req = urllib.request.Request(
        url=f"{BASE_URL}{path}",
        data=data,
        headers=final_headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(req) as response:
            status = response.status
            raw = response.read()
            response_headers = dict(response.headers.items())
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read()
        response_headers = dict(exc.headers.items())

    text = raw.decode("utf-8", errors="replace") if raw else ""
    payload = json.loads(text) if text else None

    if expect_status is not None:
        allowed = {expect_status} if isinstance(expect_status, int) else set(expect_status)
        if status not in allowed:
            print(f"Unexpected status. Expected {sorted(allowed)}, got {status}")
            print(text)
            raise AssertionError(f"{method} {path} returned {status}")

    return status, payload, response_headers


def assert_standard_headers(headers: dict[str, str], expected_request_id: str | None = None) -> None:
    normalized = {k.lower(): v for k, v in headers.items()}
    ok("x-vendor-trace-id" in normalized, "X-Vendor-Trace-ID header is present")
    ok("server-timing" in normalized, "Server-Timing header is present")
    if expected_request_id:
        ok(normalized.get("x-request-id") == expected_request_id, "X-Request-ID header is echoed")


def assert_query_headers(headers: dict[str, str]) -> None:
    normalized = {k.lower(): v for k, v in headers.items()}
    ok(
        normalized.get("x-vendor-retrieval-strategy")
        in {"hybrid_qdrant_article_keyword", "article_keyword_mvp"},
        "X-Vendor-Retrieval-Strategy header is present",
    )


def assert_chunk_shape(chunk: dict[str, Any]) -> None:
    for key in {
        "chunk_id",
        "content",
        "article_number",
        "section_title",
        "point_number",
        "page_number",
        "source_id",
        "source_url",
        "source_title",
        "namespace_id",
        "score",
        "metadata",
    }:
        ok(key in chunk, f"chunk has {key}")


def assert_query_shape(payload: dict[str, Any]) -> None:
    for key in {
        "request_id",
        "answer",
        "citations",
        "usage",
        "latency_ms",
        "model_version",
        "retrieval_strategy",
        "confidence",
        "trace_id",
    }:
        ok(key in payload, f"query response has {key}")
    for key in {"input_tokens", "output_tokens", "cost_usd", "model_id"}:
        ok(key in payload["usage"], f"usage has {key}")


def ingest_text_source(
    namespace_id: str,
    source_id: str,
    text: str,
    source_title: str,
    url: str = "https://example.com/legal",
    tenant_id: str | None = None,
) -> str:
    _, response, _ = request_json(
        "POST",
        "/v1/ingest",
        headers=ingest_headers(tenant_id=tenant_id),
        body={
            "namespace_id": namespace_id,
            "source_id": source_id,
            "source_type": "url",
            "url": url,
            "mime_type_hint": "text/plain",
            "metadata": {
                "source_title": source_title,
                "text": text,
            },
        },
        expect_status=202,
    )
    ok(response["job_id"].startswith("j_"), "ingest returns job_id")
    ok(response["status"] == "queued", "ingest returns queued status")
    return response["job_id"]


def poll_job(job_id: str, tenant_id: str | None = None) -> dict[str, Any]:
    _, response, _ = request_json(
        "GET",
        f"/v1/ingest/{job_id}",
        headers=auth_headers(tenant_id=tenant_id),
        expect_status=200,
    )
    return response


def main() -> None:
    print(f"Base URL:                {BASE_URL}")
    print(f"Tenant ID:               {TENANT_ID}")
    print(f"Main namespace:          {MAIN_NAMESPACE_ID}")
    print(f"Main source:             {MAIN_SOURCE_ID}")
    print(f"Include large upload:    {ARGS.include_large_upload}")
    print(f"Include optional probes: {ARGS.include_optional}")

    step("1. GET /v1/health")
    _, health, health_headers = request_json("GET", "/v1/health", expect_status=200)
    dump(health)
    ok(health["status"] in {"ok", "degraded"}, "health status is ok/degraded")
    ok("version" in health, "health response has version")
    ok("uptime_seconds" in health, "health response has uptime_seconds")
    ok("dependencies" in health, "health response has dependencies")
    ok("vector_store" in health["dependencies"], "vector_store dependency is present")
    ok("llm" in health["dependencies"], "llm dependency is present")
    ok("object_store" in health["dependencies"], "object_store dependency is present")
    assert_standard_headers(health_headers)

    step("2. GET /v1/openapi.json")
    _, openapi, _ = request_json("GET", "/v1/openapi.json", expect_status=200)
    print(f"OpenAPI title: {openapi['info']['title']}")
    ok("openapi" in openapi, "OpenAPI version field is present")
    ok("info" in openapi, "OpenAPI info field is present")
    ok("paths" in openapi, "OpenAPI paths field is present")
    ok(any(path.endswith("/query") for path in openapi["paths"]), "OpenAPI includes query path")
    ok(any(path.endswith("/ingest") for path in openapi["paths"]), "OpenAPI includes ingest path")
    ok(any(path.endswith("/health") for path in openapi["paths"]), "OpenAPI includes health path")

    step("3. POST /v1/query - missing Authorization returns 401")
    _, missing_auth, _ = request_json(
        "POST",
        "/v1/query",
        headers={"X-Request-ID": str(uuid4()), "X-Tenant-ID": TENANT_ID},
        body={"question": "Ce spune articolul 15?", "language": "ro", "namespaces": [MAIN_NAMESPACE_ID]},
        expect_status=401,
    )
    dump(missing_auth)
    expect_error(missing_auth, "unauthorized")

    step("4. POST /v1/query - wrong auth scheme returns 401")
    _, wrong_scheme, _ = request_json(
        "POST",
        "/v1/query",
        headers={
            "Authorization": f"Basic {API_KEY}",
            "X-Request-ID": str(uuid4()),
            "X-Tenant-ID": TENANT_ID,
        },
        body={"question": "Ce spune articolul 15?", "language": "ro", "namespaces": [MAIN_NAMESPACE_ID]},
        expect_status=401,
    )
    dump(wrong_scheme)
    expect_error(wrong_scheme, "unauthorized")

    step("5. POST /v1/query - invalid API key returns 401")
    _, invalid_key, _ = request_json(
        "POST",
        "/v1/query",
        headers=auth_headers(api_key="wrong-api-key"),
        body={"question": "Ce spune articolul 15?", "language": "ro", "namespaces": [MAIN_NAMESPACE_ID]},
        expect_status=401,
    )
    dump(invalid_key)
    expect_error(invalid_key, "unauthorized")

    step("6. POST /v1/query - missing X-Tenant-ID returns error")
    status, missing_tenant, _ = request_json(
        "POST",
        "/v1/query",
        headers={"Authorization": f"Bearer {API_KEY}", "X-Request-ID": str(uuid4())},
        body={"question": "Ce spune articolul 15?", "language": "ro", "namespaces": [MAIN_NAMESPACE_ID]},
        expect_status={400, 422},
    )
    dump(missing_tenant)
    ok(status in {400, 422}, "missing tenant returns 400 or 422")

    step("7. POST /v1/query - validation error returns 422")
    _, validation_error, _ = request_json(
        "POST",
        "/v1/query",
        headers=auth_headers(),
        body={"language": "ro", "namespaces": [MAIN_NAMESPACE_ID]},
        expect_status=422,
    )
    dump(validation_error)
    expect_error(validation_error, "validation_error")
    ok("errors" in validation_error["error"]["details"], "validation error includes errors list")

    step("8. POST /v1/ingest - missing Idempotency-Key returns 422")
    _, missing_idem, _ = request_json(
        "POST",
        "/v1/ingest",
        headers=auth_headers(),
        body={
            "namespace_id": f"missing_idem_{RUN_SUFFIX}",
            "source_id": f"s_missing_idem_{RUN_SUFFIX}",
            "source_type": "url",
            "url": "https://example.com/missing-idempotency",
            "mime_type_hint": "text/plain",
            "metadata": {"text": "Articolul 15. Text test."},
        },
        expect_status=422,
    )
    dump(missing_idem)
    expect_error(missing_idem, "validation_error")

    step("9. POST /v1/ingest - JSON with metadata.text")
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

    step("10. GET /v1/ingest/{job_id} - JSON ingest status")
    main_job = poll_job(main_job_id)
    dump(main_job)
    ok(main_job["job_id"] == main_job_id, "job status returns same job_id")
    ok(main_job["namespace_id"] == MAIN_NAMESPACE_ID, "job namespace_id is correct")
    ok(main_job["source_id"] == MAIN_SOURCE_ID, "job source_id is correct")
    ok(main_job["status"] == "done", "job status is done")
    ok(main_job["progress"]["percent"] == 100, "job progress is 100")
    ok(main_job["progress"]["chunks_created"] >= 2, "job created at least 2 chunks")
    ok(main_job["error"] is None, "job error is null")

    step("11. GET /v1/ingest/{job_id} - unknown job returns 404")
    _, missing_job, _ = request_json(
        "GET",
        f"/v1/ingest/j_missing_{RUN_SUFFIX}",
        headers=auth_headers(),
        expect_status=404,
    )
    dump(missing_job)
    expect_error(missing_job, "not_found")

    step("12. GET /v1/ingest/{job_id} - cross-tenant isolation")
    _, cross_tenant_job, _ = request_json(
        "GET",
        f"/v1/ingest/{main_job_id}",
        headers=auth_headers(tenant_id=f"another-tenant-{RUN_SUFFIX}"),
        expect_status=404,
    )
    dump(cross_tenant_job)
    expect_error(cross_tenant_job, "not_found")

    step("13. POST /v1/ingest - idempotency same key + same body")
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
    ok(first_idem["job_id"] == second_idem["job_id"], "same idempotency key and body returns same job_id")

    step("14. POST /v1/ingest - idempotency same key + different body returns 409")
    changed_body = dict(idem_body)
    changed_body["source_id"] = f"s_idempotency_changed_{RUN_SUFFIX}"
    _, idem_conflict, _ = request_json(
        "POST",
        "/v1/ingest",
        headers=ingest_headers(idempotency_key=idem_key),
        body=changed_body,
        expect_status=409,
    )
    dump(idem_conflict)
    expect_error(idem_conflict, "duplicate_job")

    step("15. POST /v1/ingest - same idempotency key in different tenant is isolated")
    _, tenant_b_idem, _ = request_json(
        "POST",
        "/v1/ingest",
        headers=ingest_headers(idempotency_key=idem_key, tenant_id=f"tenant-b-{RUN_SUFFIX}"),
        body=changed_body,
        expect_status=202,
    )
    dump(tenant_b_idem)
    ok(tenant_b_idem["job_id"].startswith("j_"), "same idempotency key under different tenant is accepted")

    step("16. POST /v1/ingest - unsupported MIME returns 415")
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
    expect_error(unsupported_mime, "unsupported_media_type")

    step("17. POST /v1/ingest - source_type=url without url returns 422")
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
    expect_error(missing_url, "validation_error")

    step("18. POST /v1/ingest - malformed JSON returns validation error")
    status, malformed_body, _ = request_raw(
        "POST",
        "/v1/ingest",
        headers=ingest_headers(),
        body=b'{"namespace_id":',
        content_type="application/json",
        expect_status={400, 422},
    )
    print(malformed_body)
    ok(status in {400, 422}, "malformed JSON returns 400 or 422")

    step("19. POST /v1/ingest - URL fetch failure creates failed job")
    _, url_fetch_ingest, _ = request_json(
        "POST",
        "/v1/ingest",
        headers=ingest_headers(),
        body={
            "namespace_id": URL_FETCH_NAMESPACE_ID,
            "source_id": URL_FETCH_SOURCE_ID,
            "source_type": "url",
            "url": "https://example.invalid/nonexistent-legal-doc.txt",
            "mime_type_hint": "text/plain",
            "metadata": {"source_title": "URL Fetch Failure Test"},
        },
        expect_status=202,
    )
    dump(url_fetch_ingest)
    url_fetch_job = poll_job(url_fetch_ingest["job_id"])
    dump(url_fetch_job)
    ok(url_fetch_job["status"] in {"failed", "done"}, "URL fetch job reaches terminal state")
    if url_fetch_job["status"] == "failed":
        ok(url_fetch_job["error"] is not None, "failed URL fetch job has error")

    step("20. POST /v1/ingest - multipart file upload")
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
    ok(file_ingest["job_id"].startswith("j_"), "multipart ingest returns job_id")

    step("21. GET /v1/ingest/{job_id} - multipart file status")
    file_job = poll_job(file_ingest["job_id"])
    dump(file_job)
    ok(file_job["status"] == "done", "multipart ingest job is done")
    ok(file_job["progress"]["chunks_created"] >= 1, "multipart ingest created at least one chunk")

    step("22. POST /v1/ingest - multipart missing payload returns 422")
    _, missing_payload, _ = request_multipart(
        "POST",
        "/v1/ingest",
        headers=ingest_headers(),
        files={"file": ("legea_31.txt", b"Articolul 15.", "text/plain")},
        expect_status=422,
    )
    dump(missing_payload)
    expect_error(missing_payload, "validation_error")

    step("23. POST /v1/ingest - multipart missing file returns 422")
    _, missing_file, _ = request_multipart(
        "POST",
        "/v1/ingest",
        headers=ingest_headers(),
        fields={"payload": json.dumps(file_payload, ensure_ascii=False)},
        expect_status=422,
    )
    dump(missing_file)
    expect_error(missing_file, "validation_error")

    step("24. POST /v1/ingest - multipart invalid payload returns 422")
    _, invalid_payload, _ = request_multipart(
        "POST",
        "/v1/ingest",
        headers=ingest_headers(),
        fields={"payload": '{"namespace_id":'},
        files={"file": ("legea_31.txt", b"Articolul 15.", "text/plain")},
        expect_status=422,
    )
    dump(invalid_payload)
    expect_error(invalid_payload, "validation_error")

    if ARGS.include_large_upload:
        step("25. POST /v1/ingest - multipart oversized file returns 413")
        oversized_content = b"x" * (MAX_DOCUMENT_BYTES + 1)
        large_payload = {
            "namespace_id": f"large_upload_namespace_{RUN_SUFFIX}",
            "source_id": f"s_large_upload_{RUN_SUFFIX}",
            "source_type": "file",
            "mime_type_hint": "text/plain",
            "metadata": {"source_title": "Large Upload"},
        }
        _, large_upload, _ = request_multipart(
            "POST",
            "/v1/ingest",
            headers=ingest_headers(),
            fields={"payload": json.dumps(large_payload, ensure_ascii=False)},
            files={"file": ("large.txt", oversized_content, "text/plain")},
            expect_status=413,
        )
        dump(large_upload)
        expect_error(large_upload, "payload_too_large")
    else:
        step("25. SKIP multipart oversized file")
        print("Run with --include-large-upload to send ~50 MiB and verify 413.")

    step("26. POST /v1/query - exact article 15")
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
    _, response_15, query_headers = request_json(
        "POST",
        "/v1/query",
        headers=auth_headers(request_id=query_request_id),
        body=query_15,
        expect_status=200,
    )
    dump(response_15)
    assert_query_shape(response_15)
    content_15 = response_15["citations"][0]["chunk"]["content"]
    ok(response_15["request_id"] == query_request_id, "query response request_id matches")
    ok(response_15["answer"] is not None, "article 15 answer is not null")
    ok("[1]" in response_15["answer"], "article 15 answer contains [1]")
    ok(len(response_15["citations"]) >= 1, "article 15 has at least one citation")
    assert_chunk_shape(response_15["citations"][0]["chunk"])
    ok(response_15["citations"][0]["chunk"]["article_number"] == "15", "first citation is article 15")
    ok("Aporturile în numerar" in content_15, "article 15 content is correct")
    ok(response_15["confidence"] > 0, "article 15 confidence is greater than zero")
    assert_standard_headers(query_headers, expected_request_id=query_request_id)
    assert_query_headers(query_headers)

    step("27. POST /v1/query - exact article 16")
    query_16 = {
        "question": "Ce spune articolul 16?",
        "language": "ro",
        "namespaces": [MAIN_NAMESPACE_ID],
        "top_k": 5,
        "hint_article_number": "16",
        "include_answer": True,
    }
    _, response_16, _ = request_json("POST", "/v1/query", headers=auth_headers(), body=query_16, expect_status=200)
    dump(response_16)
    content_16 = response_16["citations"][0]["chunk"]["content"]
    ok(response_16["answer"] is not None, "article 16 answer is not null")
    ok(response_16["citations"][0]["chunk"]["article_number"] == "16", "first citation is article 16")
    ok("Aporturile în natură" in content_16, "article 16 content is correct")
    ok("Aporturile în numerar" not in content_16, "article 16 does not contain article 15 content")

    step("28. POST /v1/query - semantic retrieval without article hint")
    semantic_query = {
        "question": "Ce prevede legea despre evaluarea aporturilor?",
        "language": "ro",
        "namespaces": [MAIN_NAMESPACE_ID],
        "top_k": 5,
        "include_answer": True,
    }
    _, semantic_response, _ = request_json("POST", "/v1/query", headers=auth_headers(), body=semantic_query, expect_status=200)
    dump(semantic_response)
    ok(semantic_response["answer"] is not None, "semantic query returns answer")
    ok(len(semantic_response["citations"]) >= 1, "semantic query returns citations")

    step("29. POST /v1/query - include_answer=false returns citations only")
    query_retrieval_only = dict(query_15)
    query_retrieval_only["include_answer"] = False
    _, retrieval_only, _ = request_json("POST", "/v1/query", headers=auth_headers(), body=query_retrieval_only, expect_status=200)
    dump(retrieval_only)
    ok(retrieval_only["answer"] is None, "retrieval-only answer is null")
    ok(len(retrieval_only["citations"]) >= 1, "retrieval-only returns citations")

    step("30. POST /v1/query - top_k=1 limits citations")
    top_one_query = dict(query_15)
    top_one_query["top_k"] = 1
    _, top_one, _ = request_json("POST", "/v1/query", headers=auth_headers(), body=top_one_query, expect_status=200)
    dump(top_one)
    ok(len(top_one["citations"]) <= 1, "top_k=1 returns at most one citation")

    step("31. POST /v1/query - invalid top_k=0 returns 422")
    invalid_top_k_query = dict(query_15)
    invalid_top_k_query["top_k"] = 0
    _, invalid_top_k, _ = request_json("POST", "/v1/query", headers=auth_headers(), body=invalid_top_k_query, expect_status=422)
    dump(invalid_top_k)
    expect_error(invalid_top_k, "validation_error")

    step("32. POST /v1/query - uploaded file namespace")
    query_file = {
        "question": "Ce spune articolul 15?",
        "language": "ro",
        "namespaces": [FILE_NAMESPACE_ID],
        "top_k": 5,
        "hint_article_number": "15",
        "include_answer": True,
    }
    _, file_query, _ = request_json("POST", "/v1/query", headers=auth_headers(), body=query_file, expect_status=200)
    dump(file_query)
    ok(file_query["answer"] is not None, "uploaded file query returns answer")
    ok(file_query["citations"][0]["chunk"]["metadata"]["text_source"] == "uploaded_file", "citation metadata marks uploaded_file")
    ok(file_query["citations"][0]["chunk"]["metadata"]["uploaded_filename"] == "legea_31.txt", "citation metadata includes uploaded filename")

    step("33. POST /v1/query - empty result / no hallucination")
    query_empty = {
        "question": "Care este programul primăriei Bălta Doamnei?",
        "language": "ro",
        "namespaces": [MAIN_NAMESPACE_ID],
        "top_k": 5,
        "include_answer": True,
    }
    _, empty, _ = request_json("POST", "/v1/query", headers=auth_headers(), body=query_empty, expect_status=200)
    dump(empty)
    ok(empty["answer"] is None, "empty query answer is null")
    ok(empty["citations"] == [], "empty query citations are empty")
    ok(empty["confidence"] == 0.0, "empty query confidence is 0.0")

    step("34. POST /v1/query - cross-tenant isolation")
    _, cross_tenant, _ = request_json(
        "POST",
        "/v1/query",
        headers=auth_headers(tenant_id=f"another-tenant-{RUN_SUFFIX}"),
        body=query_15,
        expect_status=200,
    )
    dump(cross_tenant)
    ok(cross_tenant["answer"] is None, "other tenant cannot see answer")
    ok(cross_tenant["citations"] == [], "other tenant cannot see citations")
    ok(cross_tenant["confidence"] == 0.0, "other tenant confidence is 0.0")

    step("35. POST /v1/query - multi-namespace retrieval")
    second_job_id = ingest_text_source(
        namespace_id=SECOND_NAMESPACE_ID,
        source_id=SECOND_SOURCE_ID,
        text="Articolul 200. Persoana juridică răspunde pentru obligațiile sale potrivit legii.",
        source_title="Codul Civil - Test",
        url="https://example.com/cod-civil",
    )
    ok(poll_job(second_job_id)["status"] == "done", "second namespace ingest is done")
    multi_query = {
        "question": "Ce spune legea despre aporturi și obligații?",
        "language": "ro",
        "namespaces": [MAIN_NAMESPACE_ID, SECOND_NAMESPACE_ID],
        "top_k": 10,
        "include_answer": True,
    }
    _, multi_response, _ = request_json("POST", "/v1/query", headers=auth_headers(), body=multi_query, expect_status=200)
    dump(multi_response)
    returned_namespaces = {citation["chunk"]["namespace_id"] for citation in multi_response["citations"]}
    ok(
        MAIN_NAMESPACE_ID in returned_namespaces or SECOND_NAMESPACE_ID in returned_namespaces,
        "multi-namespace query returns at least one configured namespace",
    )

    step("36. GET /v1/namespaces/{namespace_id}/stats")
    _, stats, _ = request_json("GET", f"/v1/namespaces/{MAIN_NAMESPACE_ID}/stats", headers=auth_headers(), expect_status=200)
    dump(stats)
    ok(stats["namespace_id"] == MAIN_NAMESPACE_ID, "stats namespace_id is correct")
    ok(stats["chunk_count"] >= 2, "stats chunk_count >= 2")
    ok(stats["source_count"] >= 1, "stats source_count >= 1")
    ok(stats["embedding_dim"] > 0, "stats embedding_dim is positive")
    ok(stats["embedding_model"], "stats embedding_model is present")

    step("37. GET /v1/namespaces/{namespace_id}/stats - missing namespace returns 404")
    _, missing_stats, _ = request_json(
        "GET",
        f"/v1/namespaces/missing_namespace_{RUN_SUFFIX}/stats",
        headers=auth_headers(),
        expect_status=404,
    )
    dump(missing_stats)
    expect_error(missing_stats, "namespace_not_found")

    step("38. GET /v1/namespaces/{namespace_id}/stats - cross-tenant isolation")
    _, cross_tenant_stats, _ = request_json(
        "GET",
        f"/v1/namespaces/{MAIN_NAMESPACE_ID}/stats",
        headers=auth_headers(tenant_id=f"another-tenant-{RUN_SUFFIX}"),
        expect_status=404,
    )
    dump(cross_tenant_stats)
    expect_error(cross_tenant_stats, "namespace_not_found")

    step("39. DELETE /v1/namespaces/{namespace_id}/sources/{source_id}")
    status, _, _ = request_json(
        "DELETE",
        f"/v1/namespaces/{MAIN_NAMESPACE_ID}/sources/{MAIN_SOURCE_ID}",
        headers=auth_headers(),
        expect_status=204,
    )
    ok(status == 204, "delete source returns 204")

    step("40. Verify source deletion")
    _, after_source_delete, _ = request_json("POST", "/v1/query", headers=auth_headers(), body=query_15, expect_status=200)
    dump(after_source_delete)
    ok(after_source_delete["answer"] is None, "after source delete answer is null")
    ok(after_source_delete["citations"] == [], "after source delete citations are empty")
    ok(after_source_delete["confidence"] == 0.0, "after source delete confidence is 0.0")

    step("41. DELETE /v1/namespaces/{namespace_id}/sources/{source_id} - missing source returns 404")
    _, missing_source_delete, _ = request_json(
        "DELETE",
        f"/v1/namespaces/{MAIN_NAMESPACE_ID}/sources/missing_source_{RUN_SUFFIX}",
        headers=auth_headers(),
        expect_status=404,
    )
    dump(missing_source_delete)
    expect_error(missing_source_delete, "not_found")

    step("42. POST /v1/ingest - setup namespace delete test")
    delete_namespace_job_id = ingest_text_source(
        namespace_id=DELETE_NAMESPACE_ID,
        source_id=DELETE_NAMESPACE_SOURCE_ID,
        text="Articolul 15. Aporturile în numerar sunt obligatorii la constituirea oricărei forme de societate.",
        source_title="Delete Namespace Test",
        url="https://example.com/delete-namespace-test",
    )
    ok(poll_job(delete_namespace_job_id)["status"] == "done", "delete namespace setup ingest is done")

    step("43. DELETE /v1/namespaces/{namespace_id}")
    _, delete_namespace_response, _ = request_json(
        "DELETE",
        f"/v1/namespaces/{DELETE_NAMESPACE_ID}",
        headers=auth_headers(),
        expect_status=202,
    )
    dump(delete_namespace_response)
    ok(delete_namespace_response.get("job_id", "").startswith("del_"), "delete namespace returns deletion job_id")
    ok(delete_namespace_response.get("status") == "queued", "delete namespace status is queued")
    ok(delete_namespace_response.get("sla") == "24h", "delete namespace sla is 24h")

    step("44. Verify namespace deletion through query")
    _, after_namespace_delete_query, _ = request_json(
        "POST",
        "/v1/query",
        headers=auth_headers(),
        body={
            "question": "Ce spune articolul 15?",
            "language": "ro",
            "namespaces": [DELETE_NAMESPACE_ID],
            "top_k": 5,
            "hint_article_number": "15",
            "include_answer": True,
        },
        expect_status=200,
    )
    dump(after_namespace_delete_query)
    ok(after_namespace_delete_query["answer"] is None, "after namespace delete answer is null")
    ok(after_namespace_delete_query["citations"] == [], "after namespace delete citations are empty")
    ok(after_namespace_delete_query["confidence"] == 0.0, "after namespace delete confidence is 0.0")

    step("45. Verify namespace deletion through stats")
    _, stats_after_namespace_delete, _ = request_json(
        "GET",
        f"/v1/namespaces/{DELETE_NAMESPACE_ID}/stats",
        headers=auth_headers(),
        expect_status=404,
    )
    dump(stats_after_namespace_delete)
    expect_error(stats_after_namespace_delete, "namespace_not_found")

    step("46. DELETE /v1/namespaces/{namespace_id} - missing namespace returns 404")
    _, missing_namespace_delete, _ = request_json(
        "DELETE",
        f"/v1/namespaces/missing_delete_namespace_{RUN_SUFFIX}",
        headers=auth_headers(),
        expect_status=404,
    )
    dump(missing_namespace_delete)
    expect_error(missing_namespace_delete, "namespace_not_found")

    if ARGS.include_optional:
        step("47. OPTIONAL GET /metrics")
        metrics_status, metrics_text, _ = request_raw("GET", "/metrics", expect_status={200, 404})
        print(metrics_text[:1000])
        if metrics_status == 200:
            ok("http_" in metrics_text or "# HELP" in metrics_text, "metrics output looks like Prometheus text")
        else:
            print("[OK] /metrics is optional/not implemented in this local MVP")

        step("48. OPTIONAL POST /v1/eval")
        eval_status, eval_payload, _ = request_json(
            "POST",
            "/v1/eval",
            headers=auth_headers(),
            body={
                "question": "Ce spune articolul 15 din Legea 31/1990?",
                "language": "ro",
                "namespaces": [MAIN_NAMESPACE_ID],
                "expected_answer_keywords": ["aporturi", "numerar"],
                "expected_citations": [],
            },
            expect_status={200, 404, 422},
        )
        dump(eval_payload)
        ok(eval_status in {200, 404, 422}, "/v1/eval optional probe returned accepted status")
    else:
        step("47. SKIP optional endpoints")
        print("Skipped optional /metrics and /v1/eval probes. Run with --include-optional to probe them.")

    step("ALL ENDPOINT SMOKE TESTS PASSED")


if __name__ == "__main__":
    main()
