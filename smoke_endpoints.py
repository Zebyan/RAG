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
NAMESPACE_ID = f"legea_31_1990_endpoint_test_{RUN_SUFFIX}"
SOURCE_ID = f"s_47381_endpoint_test_{RUN_SUFFIX}"


def step(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def dump(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def request_json(
    method: str,
    path: str,
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    expect_status: int | None = None,
) -> tuple[int, Any]:
    url = f"{BASE_URL}{path}"
    final_headers = dict(headers or {})

    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        final_headers["Content-Type"] = "application/json; charset=utf-8"

    req = urllib.request.Request(
        url=url,
        data=data,
        headers=final_headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(req) as response:
            status = response.status
            raw = response.read()
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read()

    text = raw.decode("utf-8") if raw else ""
    payload = json.loads(text) if text else None

    if expect_status is not None and status != expect_status:
        print(f"Unexpected status. Expected {expect_status}, got {status}")
        print(text)
        raise AssertionError(f"{method} {path} returned {status}")

    return status, payload


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(f"ASSERTION FAILED: {message}")
    print(f"[OK] {message}")


def auth_headers(request_id: str | None = None, tenant_id: str | None = None) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {API_KEY}",
        "X-Request-ID": request_id or str(uuid4()),
        "X-Tenant-ID": tenant_id or TENANT_ID,
    }


def main() -> None:
    print(f"Base URL:     {BASE_URL}")
    print(f"Tenant ID:    {TENANT_ID}")
    print(f"Namespace ID: {NAMESPACE_ID}")
    print(f"Source ID:    {SOURCE_ID}")

    step("1. GET /v1/health")
    status, health = request_json("GET", "/v1/health", expect_status=200)
    dump(health)
    assert_true(health["status"] in {"ok", "degraded"}, "health status is ok/degraded")
    assert_true("vector_store" in health["dependencies"], "vector_store dependency is present")
    assert_true("llm" in health["dependencies"], "llm dependency is present")
    assert_true("object_store" in health["dependencies"], "object_store dependency is present")

    step("2. POST /v1/ingest")
    ingest_body = {
        "namespace_id": NAMESPACE_ID,
        "source_id": SOURCE_ID,
        "source_type": "url",
        "url": "https://legislatie.just.ro/Public/DetaliiDocument/47381",
        "mime_type_hint": "text/plain",
        "metadata": {
            "source_title": "Legea 31/1990 privind societățile comerciale",
            "text": (
                "Articolul 15. Aporturile în numerar sunt obligatorii la constituirea oricărei forme de societate.\n\n"
                "Articolul 16. Aporturile în natură trebuie să fie evaluabile din punct de vedere economic."
            ),
        },
    }

    ingest_headers = auth_headers()
    ingest_headers["Idempotency-Key"] = str(uuid4())
    status, ingest = request_json("POST", "/v1/ingest", headers=ingest_headers, body=ingest_body, expect_status=202)
    dump(ingest)
    assert_true(ingest["job_id"].startswith("j_"), "ingest returns job_id")
    assert_true(ingest["status"] == "queued", "ingest returns queued status")

    job_id = ingest["job_id"]

    step("3. GET /v1/ingest/{job_id}")
    status, job = request_json("GET", f"/v1/ingest/{job_id}", headers=auth_headers(), expect_status=200)
    dump(job)
    assert_true(job["job_id"] == job_id, "job status returns same job_id")
    assert_true(job["status"] == "done", "job status is done")
    assert_true(job["progress"]["percent"] == 100, "job progress is 100")
    assert_true(job["progress"]["chunks_created"] >= 2, "job created at least 2 chunks")

    step("4. POST /v1/query - exact article 15")
    query_15 = {
        "question": "Ce spune articolul 15 din Legea 31/1990?",
        "language": "ro",
        "namespaces": [NAMESPACE_ID],
        "top_k": 5,
        "hint_article_number": "15",
        "rerank": True,
        "include_answer": True,
    }

    status, response_15 = request_json("POST", "/v1/query", headers=auth_headers(), body=query_15, expect_status=200)
    dump(response_15)

    content_15 = response_15["citations"][0]["chunk"]["content"]
    assert_true(response_15["answer"] is not None, "article 15 answer is not null")
    assert_true("[1]" in response_15["answer"], "article 15 answer contains [1]")
    assert_true(len(response_15["citations"]) >= 1, "article 15 has at least one citation")
    assert_true(response_15["citations"][0]["chunk"]["article_number"] == "15", "first citation is article 15")
    assert_true("Aporturile în numerar" in content_15, "article 15 content is correct")
    assert_true(response_15["confidence"] > 0, "article 15 confidence is greater than zero")

    step("5. POST /v1/query - exact article 16")
    query_16 = {
        "question": "Ce spune articolul 16?",
        "language": "ro",
        "namespaces": [NAMESPACE_ID],
        "top_k": 5,
        "hint_article_number": "16",
        "include_answer": True,
    }

    status, response_16 = request_json("POST", "/v1/query", headers=auth_headers(), body=query_16, expect_status=200)
    dump(response_16)

    content_16 = response_16["citations"][0]["chunk"]["content"]
    assert_true(response_16["answer"] is not None, "article 16 answer is not null")
    assert_true(response_16["citations"][0]["chunk"]["article_number"] == "16", "first citation is article 16")
    assert_true("Aporturile în natură" in content_16, "article 16 content is correct")
    assert_true("Aporturile în numerar" not in content_16, "article 16 does not contain article 15 content")

    step("6. POST /v1/query - empty result / no hallucination")
    query_empty = {
        "question": "Care este programul primăriei Bălta Doamnei?",
        "language": "ro",
        "namespaces": [NAMESPACE_ID],
        "top_k": 5,
        "include_answer": True,
    }

    status, empty = request_json("POST", "/v1/query", headers=auth_headers(), body=query_empty, expect_status=200)
    dump(empty)
    assert_true(empty["answer"] is None, "empty query answer is null")
    assert_true(empty["citations"] == [], "empty query citations are empty")
    assert_true(empty["confidence"] == 0.0, "empty query confidence is 0.0")

    step("7. GET /v1/namespaces/{namespace_id}/stats")
    status, stats = request_json("GET", f"/v1/namespaces/{NAMESPACE_ID}/stats", headers=auth_headers(), expect_status=200)
    dump(stats)
    assert_true(stats["namespace_id"] == NAMESPACE_ID, "stats namespace_id is correct")
    assert_true(stats["chunk_count"] >= 2, "stats chunk_count >= 2")
    assert_true(stats["source_count"] >= 1, "stats source_count >= 1")

    step("8. Cross-tenant isolation")
    status, cross_tenant = request_json(
        "POST",
        "/v1/query",
        headers=auth_headers(tenant_id=f"another-tenant-{RUN_SUFFIX}"),
        body=query_15,
        expect_status=200,
    )
    dump(cross_tenant)
    assert_true(cross_tenant["answer"] is None, "other tenant cannot see answer")
    assert_true(cross_tenant["citations"] == [], "other tenant cannot see citations")
    assert_true(cross_tenant["confidence"] == 0.0, "other tenant confidence is 0.0")

    step("9. DELETE /v1/namespaces/{namespace_id}/sources/{source_id}")
    status, _ = request_json(
        "DELETE",
        f"/v1/namespaces/{NAMESPACE_ID}/sources/{SOURCE_ID}",
        headers=auth_headers(),
        expect_status=204,
    )
    assert_true(status == 204, "delete source returns 204")

    step("9.1 Verify source deletion")
    status, after_delete = request_json("POST", "/v1/query", headers=auth_headers(), body=query_15, expect_status=200)
    dump(after_delete)
    assert_true(after_delete["answer"] is None, "after delete answer is null")
    assert_true(after_delete["citations"] == [], "after delete citations are empty")
    assert_true(after_delete["confidence"] == 0.0, "after delete confidence is 0.0")

    step("10. GET /v1/openapi.json")
    status, openapi = request_json("GET", "/v1/openapi.json", expect_status=200)
    print(f"OpenAPI title: {openapi['info']['title']}")
    assert_true("openapi" in openapi, "OpenAPI version field is present")
    assert_true("paths" in openapi, "OpenAPI paths field is present")

    step("ALL ENDPOINT SMOKE TESTS PASSED")


if __name__ == "__main__":
    main()
