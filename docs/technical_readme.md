# Technical README — CityDock / Lex-Advisor RAG Service

This document explains the internal implementation of the CityDock / Lex-Advisor RAG service in detail.

It covers:

- project purpose;
- architecture;
- folder structure;
- runtime configuration;
- API endpoint behavior;
- function/service call chains;
- request/response examples;
- ingest flow;
- URL ingest flow;
- multipart file ingest flow;
- oversized upload behavior;
- document extraction;
- legal chunking;
- embeddings;
- Qdrant vector indexing/search;
- hybrid retrieval;
- deterministic answer generation;
- error handling;
- tenant isolation;
- static OpenAPI contract serving;
- Docker/Compose behavior;
- expanded smoke testing strategy;
- current limitations and extension points.

---

## 1. Service purpose

The service implements a local Retrieval-Augmented Generation API for Romanian legal documents.

The service can:

1. receive legal source documents;
2. extract text from supported inputs;
3. reject invalid or oversized inputs with contract-aligned error responses;
4. split legal text into meaningful legal chunks;
5. generate embeddings locally;
6. store chunks in SQLite;
7. store vectors in Qdrant;
8. retrieve relevant chunks for a user question;
9. generate a grounded answer using retrieved citations;
10. avoid hallucinated answers when no relevant context exists;
11. delete source/namespace data and cleanup Qdrant vectors;
12. serve the static OpenAPI contract at runtime.

The current implementation does **not** use an external LLM by default. Answers are deterministic and citation-based.

---

## 2. High-level architecture

```text
Client
  |
  | HTTP /v1/*
  v
FastAPI application
  |
  +--> Middleware
  |      - X-Request-ID response propagation
  |      - X-Vendor-Trace-ID generation
  |      - Server-Timing header
  |
  +--> Authentication
  |      - Authorization: Bearer <api-key>
  |      - X-Request-ID required
  |      - X-Tenant-ID required
  |
  +--> Routes
  |      - /v1/health
  |      - /v1/ingest
  |      - /v1/ingest/{job_id}
  |      - /v1/query
  |      - /v1/namespaces/{namespace_id}/stats
  |      - /v1/namespaces/{namespace_id}/sources/{source_id}
  |      - /v1/namespaces/{namespace_id}
  |      - /v1/openapi.json
  |        - serves root openapi.yaml as static JSON contract
  |
  +--> Services
         |
         +--> ingest_service.py
         +--> url_fetcher.py
         +--> document_extractor.py
         +--> legal_chunker.py
         +--> embedding_service.py
         +--> vector_store.py
         +--> retrieval_service.py
         +--> answer_service.py
         +--> namespace_service.py
         +--> sqlite_store.py
```

External local dependencies:

```text
SQLite
  - stores jobs, idempotency records, sources, chunks, namespace stats

Qdrant
  - stores vector points and chunk payloads
```

---

## 3. Runtime configuration

Configuration is loaded from environment variables through `app/config.py`.

Important variables:

```env
APP_NAME=citydock-rag-mvp
APP_VERSION=0.1.0
RAG_API_KEY=test-api-key

DATABASE_PATH=./data/app.db

VECTOR_STORE=qdrant
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=rag_chunks

EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_DIM=384

URL_FETCH_TIMEOUT_SECONDS=60

LLM_PROVIDER=none
```

Local host execution:

```env
QDRANT_URL=http://localhost:6333
DATABASE_PATH=./data/app.db
```

Docker Compose execution:

```env
QDRANT_URL=http://qdrant:6333
DATABASE_PATH=/app/data/app.db
```

---

## 4. Application startup

The FastAPI application is created in `app/main.py`.

Startup responsibilities:

```text
create FastAPI app
→ register middleware
→ register exception handlers
→ include routers
→ initialize SQLite database
```

Middleware behavior:

```text
incoming request
→ read X-Request-ID if present
→ read or create X-Vendor-Trace-ID
→ call route handler
→ measure duration
→ add response headers
```

Response headers:

```text
X-Request-ID
X-Vendor-Trace-ID
Server-Timing
```

Query responses additionally include:

```text
X-Vendor-Retrieval-Strategy
```

---

## 5. Authentication and request context

Implemented in `app/auth.py`.

Most endpoints require:

```text
Authorization: Bearer test-api-key
X-Request-ID: <uuid>
X-Tenant-ID: <tenant-id>
```

The auth dependency returns an internal context similar to:

```python
AuthContext(
    request_id="11111111-1111-4111-8111-111111111111",
    tenant_id="test-tenant",
)
```

This context is passed to service functions so all data access is tenant-scoped.

Tenant isolation applies to:

```text
job
idempotency record
source
chunk
vector point
namespace stats
```

Qdrant search also filters by:

```text
tenant_id == X-Tenant-ID
namespace_id in request.namespaces
```

---

## 6. API endpoint overview

Public endpoint:

```text
GET /v1/health
```

Authenticated endpoints:

```text
POST   /v1/ingest
GET    /v1/ingest/{job_id}
POST   /v1/query
GET    /v1/namespaces/{namespace_id}/stats
DELETE /v1/namespaces/{namespace_id}/sources/{source_id}
DELETE /v1/namespaces/{namespace_id}
```

Static contract endpoint:

```text
GET /v1/openapi.json
```

---

## 7. Health endpoint

Function chain:

```text
GET /v1/health
→ routes/health.py
→ health route handler
→ checks configured dependency status
→ returns HealthResponse
```

Example response:

```json
{
  "status": "ok",
  "version": "0.1.0",
  "uptime_seconds": 14,
  "dependencies": {
    "vector_store": "ok",
    "llm": "ok",
    "object_store": "ok"
  }
}
```

---

## 8. Ingest endpoint

Endpoint:

```text
POST /v1/ingest
```

Supported content types:

```text
application/json
multipart/form-data
application/x-www-form-urlencoded for validation fallback
```

Required headers:

```text
Authorization: Bearer test-api-key
X-Request-ID: <uuid>
X-Tenant-ID: <tenant-id>
Idempotency-Key: <uuid>
```

---

## 9. JSON ingest flow

JSON ingest supports:

1. inline deterministic fixture text through `metadata.text`;
2. URL fetching if `metadata.text` is absent and `source_type=url`.

Function chain:

```text
POST /v1/ingest
→ routes/ingest.py::post_ingest()
→ routes/ingest.py::_parse_ingest_request()
→ models.py::IngestRequest.model_validate()
→ services/ingest_service.py::create_ingest_job()
→ services/ingest_service.py::_stable_body_hash()
→ sqlite_store.get_idem_record()
→ sqlite_store.set_job()
→ sqlite_store.set_idem_record()
→ services/ingest_service.py::_process_ingest_synchronously()
→ services/ingest_service.py::_resolve_ingest_text_and_metadata()
→ chunk_legal_text()
→ sqlite_store.set_chunk()
→ embedding_service.embed_texts()
→ vector_store.upsert_chunks()
→ sqlite_store.register_source()
→ sqlite_store.update_ns_stats()
→ sqlite_store.set_job(status="done")
→ returns IngestAcceptedResponse
```

The API returns `queued` for contract compatibility, but the local MVP processes synchronously. Polling the returned job should show `done`.

---

## 10. Ingest job polling

Endpoint:

```text
GET /v1/ingest/{job_id}
```

Function chain:

```text
GET /v1/ingest/{job_id}
→ routes/ingest.py::get_ingest_status()
→ ingest_service.get_ingest_job_status()
→ sqlite_store.get_job()
→ returns IngestJobStatus
```

Done response:

```json
{
  "job_id": "j_3f7a883ddd44",
  "namespace_id": "legea_31_1990",
  "source_id": "s_47381",
  "status": "done",
  "progress": {
    "stage": "indexing",
    "percent": 100,
    "chunks_created": 2
  },
  "submitted_at": "2026-04-26T18:20:36Z",
  "completed_at": "2026-04-26T18:20:37Z",
  "error": null
}
```

Failed response:

```json
{
  "job_id": "j_3f7a883ddd44",
  "namespace_id": "legea_31_1990",
  "source_id": "s_47381",
  "status": "failed",
  "progress": {
    "stage": "failed",
    "percent": 100,
    "chunks_created": 0
  },
  "submitted_at": "2026-04-26T18:20:36Z",
  "completed_at": "2026-04-26T18:20:37Z",
  "error": {
    "code": "ingest_failed",
    "message": "URL fetch failed."
  }
}
```

---

## 11. Idempotency behavior

Idempotency is tenant-scoped.

Function chain:

```text
create_ingest_job()
→ _stable_body_hash(request)
→ store.get_idem_record(tenant_id, idempotency_key)
    |
    +--> no record:
    |      create new job
    |
    +--> same body hash:
    |      return existing job response
    |
    +--> different body hash:
           raise 409 duplicate_job
```

Same key + same body returns the existing job metadata.

Same key + different body returns:

```json
{
  "error": {
    "code": "duplicate_job",
    "message": "Idempotency-Key reused with different body.",
    "request_id": "11111111-1111-4111-8111-111111111111",
    "details": {}
  }
}
```

Same key under a different tenant is accepted because idempotency is tenant-scoped.

---

## 12. URL ingest

URL ingest is used when:

```text
source_type=url
metadata.text is absent
url is present
```

Function chain:

```text
_process_ingest_synchronously()
→ _resolve_ingest_text_and_metadata()
→ url_fetcher.fetch_url_document()
→ httpx.Client.get(url)
→ normalize_mime_type(response.headers["content-type"])
→ document_extractor.extract_document_text(response.content, mime)
→ return extracted text + metadata
→ chunking
→ embedding
→ indexing
```

Supported MIME types:

```text
text/plain
text/markdown
text/html
application/pdf
```

URL fetch failures are represented as failed jobs:

```json
{
  "status": "failed",
  "error": {
    "code": "ingest_failed",
    "message": "URL fetch failed."
  }
}
```

---

## 13. Multipart file ingest

Multipart ingest is used for direct uploaded documents.

Endpoint:

```text
POST /v1/ingest
Content-Type: multipart/form-data
```

Form parts:

```text
payload: JSON string
file: binary uploaded document
```

Function chain:

```text
routes/ingest.py::post_ingest()
→ _parse_ingest_request()
→ await http_request.form()
→ read form["payload"]
→ read form["file"]
→ IngestRequest.model_validate(payload)
→ uploaded_file.read()
→ reject oversized files with HTTP 413 payload_too_large
→ compute uploaded_file_sha256
→ attach file metadata
→ create_ingest_job(... file_content, file_mime_type, filename)
→ _process_ingest_synchronously()
→ _resolve_ingest_text_and_metadata(... file_content ...)
→ document_extractor.extract_document_text()
→ chunking
→ embedding
→ Qdrant indexing
```

Uploaded file metadata stored:

```json
{
  "text_source": "uploaded_file",
  "uploaded_filename": "legea_31.txt",
  "uploaded_file_sha256": "...",
  "uploaded_file_size_bytes": 97,
  "effective_mime_type": "text/plain"
}
```

Multipart validation errors:

```text
missing payload → 422 validation_error
missing file → 422 validation_error
invalid payload JSON → 422 validation_error
oversized file → 413 payload_too_large
```

---

## 14. Document extraction

Implemented in:

```text
app/services/document_extractor.py
```

Main function:

```python
extract_document_text(
    content: bytes,
    mime_type: str | None,
) -> ExtractedDocument
```

Function chain:

```text
extract_document_text()
→ validate_document_size()
→ normalize_mime_type()
→ validate_mime_type()
→ branch by MIME:
    text/plain      → _extract_plain_text()
    text/markdown   → _extract_markdown()
    text/html       → _extract_html()
    application/pdf → _extract_pdf()
→ validate non-empty result
→ return ExtractedDocument
```

Oversized upload response:

```json
{
  "error": {
    "code": "payload_too_large",
    "message": "Uploaded file exceeds maximum allowed size of 50 MiB.",
    "request_id": "11111111-1111-4111-8111-111111111111",
    "details": {
      "max_size_bytes": 52428800,
      "actual_size_bytes": 52428801
    }
  }
}
```

Unsupported MIME response:

```json
{
  "error": {
    "code": "unsupported_media_type",
    "message": "Unsupported MIME type: application/json",
    "request_id": "11111111-1111-4111-8111-111111111111",
    "details": {
      "mime_type": "application/json"
    }
  }
}
```

---

## 15. Legal chunking

Implemented in:

```text
app/services/legal_chunker.py
```

Main function:

```python
chunk_legal_text(text: str) -> list[LegalChunk]
```

Supported legal structures:

```text
Articolul 15.
Art. 15
Articolul 15^1
Art. II
CAPITOLUL ...
SECȚIUNEA ...
(1)
(2)
a)
b)
```

Output chunk example:

```python
LegalChunk(
    content="Articolul 15. Aporturile în numerar sunt obligatorii...",
    article_number="15",
    section_title=None,
    point_number=None,
    page_number=None,
    metadata={
        "chunk_type": "legal_article",
        "headings": [...],
        "paragraph_number": "1",
        "chunk_part": 1,
        "chunk_total": 1
    }
)
```

Article-aware chunking is important because legal questions often reference exact article numbers.

---

## 16. Embedding generation

Implemented in:

```text
app/services/embedding_service.py
```

Main functions:

```python
embed_text(text: str) -> list[float]
embed_texts(texts: list[str]) -> list[list[float]]
```

Function chain:

```text
embed_texts()
→ get_embedding_model()
→ SentenceTransformer(settings.embedding_model)
→ model.encode(texts)
→ convert vectors to list[float]
```

Default model:

```text
paraphrase-multilingual-MiniLM-L12-v2
```

Embedding dimension:

```text
384
```

Local embeddings avoid sending Romanian legal documents and user questions to third-party embedding APIs.

---

## 17. Qdrant vector store

Implemented in:

```text
app/services/vector_store.py
```

Main responsibilities:

```text
create collection
upsert vectors
search vectors
delete by source
delete by namespace
```

Collection:

```text
rag_chunks
```

Vector upsert chain:

```text
_index_chunks_in_vector_store()
→ embed_texts([chunk.content])
→ vector_store.upsert_chunks(tenant_id, chunks, vectors)
→ ensure_collection()
→ Qdrant upsert(points)
```

Point payload:

```json
{
  "tenant_id": "test-tenant",
  "namespace_id": "legea_31_1990",
  "source_id": "s_47381",
  "source_url": "https://legislatie.just.ro/Public/DetaliiDocument/47381",
  "source_title": "Legea 31/1990 privind societățile comerciale",
  "article_number": "15",
  "content": "Articolul 15. ...",
  "metadata": {}
}
```

Vector search chain:

```text
retrieval_service.retrieve_chunks()
→ embed_text(question)
→ vector_store.search_chunks(tenant_id, namespaces, query_vector, limit)
→ Qdrant search with filters:
      tenant_id == request tenant
      namespace_id in request namespaces
→ convert results to chunk dicts
```

---

## 18. Hybrid retrieval

Implemented in:

```text
app/services/retrieval_service.py
```

Main function:

```python
retrieve_chunks(
    tenant_id: str,
    namespaces: list[str],
    question: str,
    top_k: int,
    hint_article_number: str | None,
) -> list[dict]
```

Retrieval chain:

```text
retrieve_chunks()
→ get lexical candidates from SQLite
→ if Qdrant enabled:
      embed question
      search Qdrant
→ merge candidates by chunk_id
→ apply scores:
      exact article match
      vector score
      lexical score
      phrase score
      normalized Romanian token overlap
→ enforce namespace diversity
→ sort by final score
→ return top_k chunks
```

Retrieval strategy values:

```text
hybrid_qdrant_article_keyword
article_keyword_mvp
```

Exact article hints prioritize chunks with matching `article_number`.

---

## 19. Query endpoint

Endpoint:

```text
POST /v1/query
```

Function chain:

```text
routes/query.py::post_query()
→ verify_auth()
→ retrieval_service.retrieve_chunks()
→ answer_service.build_answer_response()
→ create QueryResponse
→ set X-Vendor-Retrieval-Strategy header
→ return response
```

Request:

```json
{
  "question": "Ce spune articolul 15 din Legea 31/1990?",
  "language": "ro",
  "namespaces": ["legea_31_1990"],
  "top_k": 5,
  "hint_article_number": "15",
  "rerank": true,
  "include_answer": true
}
```

Response shape:

```json
{
  "request_id": "11111111-1111-4111-8111-111111111111",
  "answer": "Articolul 15 prevede următoarele: ... [1].",
  "citations": [
    {
      "marker": "[1]",
      "chunk": {
        "chunk_id": "...",
        "content": "Articolul 15. ...",
        "article_number": "15",
        "source_id": "s_47381",
        "source_title": "Legea 31/1990 privind societățile comerciale",
        "namespace_id": "legea_31_1990",
        "score": 0.7,
        "metadata": {}
      }
    }
  ],
  "usage": {
    "input_tokens": 0,
    "output_tokens": 0,
    "cost_usd": 0.0,
    "model_id": "mvp-local"
  },
  "latency_ms": 0,
  "model_version": "0.1.0",
  "retrieval_strategy": "hybrid_qdrant_article_keyword",
  "confidence": 0.7,
  "trace_id": "tr_..."
}
```

---

## 20. Deterministic answer generation

Implemented in:

```text
app/services/answer_service.py
```

Function behavior:

```text
if chunks empty:
    answer = None
    citations = []
    confidence = 0.0

else:
    citations = create [1], [2], ...
    answer = deterministic text using top citation(s)
    confidence = top chunk score
```

The deterministic answer service only uses retrieved chunk content and citation markers. This reduces hallucination risk.

---

## 21. No-answer behavior

If retrieval finds no relevant chunks, response is:

```json
{
  "answer": null,
  "citations": [],
  "confidence": 0.0
}
```

This is the intended anti-hallucination behavior.

---

## 22. Namespace stats endpoint

Endpoint:

```text
GET /v1/namespaces/{namespace_id}/stats
```

Function chain:

```text
routes/namespaces.py
→ namespace_service.get_namespace_stats_data()
→ sqlite_store.namespace_exists()
→ sqlite_store.get_ns_stats()
→ return NamespaceStats
```

Response:

```json
{
  "namespace_id": "legea_31_1990",
  "chunk_count": 2,
  "source_count": 1,
  "total_tokens_indexed": 27,
  "last_ingested_at": "2026-04-26T18:20:37Z",
  "embedding_model": "paraphrase-multilingual-MiniLM-L12-v2",
  "embedding_dim": 384
}
```

---

## 23. Source deletion

Endpoint:

```text
DELETE /v1/namespaces/{namespace_id}/sources/{source_id}
```

Function chain:

```text
routes/namespaces.py
→ namespace_service.delete_source_data()
→ sqlite_store.source_exists()
→ sqlite_store.delete_source()
→ vector_store.delete_source()
→ return 204
```

Qdrant deletion filter:

```text
tenant_id == tenant
namespace_id == namespace_id
source_id == source_id
```

Expected:

```text
HTTP/1.1 204 No Content
```

After deletion, querying the same namespace/source content should return no answer.

---

## 24. Namespace deletion

Endpoint:

```text
DELETE /v1/namespaces/{namespace_id}
```

Function chain:

```text
routes/namespaces.py
→ namespace_service.delete_namespace_data()
→ sqlite_store.namespace_exists()
→ sqlite_store.delete_namespace()
→ vector_store.delete_namespace()
→ return contract-aligned deletion acknowledgement
```

Qdrant deletion filter:

```text
tenant_id == tenant
namespace_id == namespace_id
```

Response shape:

```json
{
  "job_id": "del_...",
  "status": "queued",
  "sla": "24h"
}
```

Local deletion is executed immediately, but the public response follows the contract's asynchronous deletion acknowledgement.

---

## 25. Error responses

Validation error envelope:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed.",
    "request_id": "11111111-1111-4111-8111-111111111111",
    "details": {
      "errors": [
        {
          "loc": ["body", "question"],
          "msg": "Field required",
          "type": "missing"
        }
      ]
    }
  }
}
```

Multipart missing file:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Multipart field 'file' is required.",
    "request_id": "11111111-1111-4111-8111-111111111111",
    "details": {
      "errors": [
        {
          "loc": ["body", "file"],
          "msg": "Field required"
        }
      ]
    }
  }
}
```

Unsupported MIME:

```json
{
  "error": {
    "code": "unsupported_media_type",
    "message": "Unsupported MIME type: application/json",
    "request_id": "11111111-1111-4111-8111-111111111111",
    "details": {
      "mime_type": "application/json"
    }
  }
}
```

Oversized file:

```json
{
  "error": {
    "code": "payload_too_large",
    "message": "Uploaded file exceeds maximum allowed size of 50 MiB.",
    "request_id": "11111111-1111-4111-8111-111111111111",
    "details": {
      "max_size_bytes": 52428800,
      "actual_size_bytes": 52428801
    }
  }
}
```

---

## 26. Static OpenAPI contract serving

Static contract file:

```text
openapi.yaml
```

Runtime schema endpoint:

```text
GET /v1/openapi.json
```

Implementation:

```text
app/routes/openapi.py
→ loads root openapi.yaml with PyYAML
→ returns it as JSON
→ include_in_schema=False
```

This means `openapi.yaml` remains the source of truth, while `/v1/openapi.json` exposes the same contract to automated validators.

Generate snapshot:

```powershell
curl.exe http://localhost:8080/v1/openapi.json -o generated-openapi.local.json
```

Compare paths and response codes:

```powershell
python compare_openapi_paths.py
python compare_openapi_responses.py
```

Expected after alignment:

```text
Only in generated:

Only in openapi.yaml:

compare_openapi_responses.py produces no output
```

The generated file and comparison helper scripts are local debug artifacts and should not be committed.

---

## 27. Dockerfile behavior

The Dockerfile uses a multi-stage build and a pinned Python base image digest.

Builder stage:

```text
FROM python:3.12-slim@sha256:<digest> AS builder
→ copy requirements.txt
→ build wheels
```

Runtime stage:

```text
FROM python:3.12-slim@sha256:<digest> AS runtime
→ create non-root appuser
→ install wheels
→ copy app
→ copy openapi.yaml
→ expose 8080
→ healthcheck /v1/health
→ run uvicorn
```

CPU-only torch check:

```powershell
docker run --rm citydock-rag-mvp:cpu python -c "import torch; print(torch.cuda.is_available())"
```

Expected:

```text
False
```

Non-root user check:

```powershell
docker run --rm citydock-rag-mvp:cpu id
```

Expected:

```text
uid=1000(appuser)
```

---

## 28. Docker Compose files

`docker-compose.local.yml` is for development and includes API + Qdrant.

`docker-compose.service.yml` is a deployment fragment for the target stack. It defines the RAG API service only and joins external network:

```text
lex-advisor
```

It does not bind host ports.

Validate:

```powershell
docker compose -f docker-compose.service.yml config
```

---

## 29. Testing strategy

The project contains automated tests for:

```text
auth
health
validation errors
response headers
document extraction
URL fetching
multipart file upload
oversized upload 413
ingest
idempotency
ingest polling
legal chunking
vector store
hybrid retrieval
query behavior
tenant isolation
namespace stats
source deletion
namespace deletion
static OpenAPI serving
no-hallucination behavior
```

Run all tests:

```powershell
pytest
```

Run expanded smoke test:

```powershell
python smoke_endpoints.py --include-large-upload
```

Save smoke output:

```powershell
$env:PYTHONIOENCODING="utf-8"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
python smoke_endpoints.py --include-large-upload 2>&1 | Tee-Object -FilePath smoke-output-full.txt
```

---

## 30. Smoke test script behavior

`smoke_endpoints.py` validates the main API behavior and important edge cases:

```text
health
static OpenAPI contract serving
auth failures
validation failures
missing Idempotency-Key
JSON ingest
ingest polling
unknown job
cross-tenant job isolation
idempotency replay
idempotency conflict
same idempotency key under different tenant
unsupported MIME
missing URL
malformed JSON
URL fetch failure job
multipart upload
multipart validation failures
oversized upload 413
exact article query
semantic query
retrieval-only mode
top_k boundary
uploaded-file retrieval
no-answer behavior
cross-tenant query isolation
multi-namespace retrieval
namespace stats
missing namespace stats
cross-tenant stats isolation
source deletion
namespace deletion
post-delete verification
optional /metrics and /v1/eval probes
```

Expected final output:

```text
ALL ENDPOINT SMOKE TESTS PASSED
```

---

## 31. External LLM extension point

External LLM generation is not active by default.

Current setting:

```env
LLM_PROVIDER=none
```

Current answer flow:

```text
retrieved chunks
→ citations
→ deterministic answer
```

Future LLM flow:

```text
retrieved chunks
→ build grounded prompt
→ call LLM provider
→ return generated answer
→ preserve citations
→ fallback to deterministic answer on failure
```

Default no external LLM reasons:

```text
legal data privacy
no external API key requirement
no third-party data transfer
deterministic citation-grounded behavior
lower hallucination risk
```

---

## 32. Data privacy and isolation

The current local implementation keeps:

```text
documents
questions
embeddings
chunks
answers
```

inside the local stack.

No external embedding API is used.

No external LLM is used by default.

Tenant isolation applies to:

```text
SQLite jobs
SQLite chunks
SQLite sources
SQLite namespace stats
Qdrant vector payloads
Qdrant vector search filters
```

---

## 33. Final local verification checklist

Before sending repository for review:

```powershell
pytest
python smoke_endpoints.py --include-large-upload
python compare_openapi_paths.py
python compare_openapi_responses.py
docker compose -f docker-compose.service.yml config
git status
```

Do not commit:

```text
.env
.venv/
data/app.db
.pytest_cache/
generated-openapi.local.json
compare_openapi_paths.py
compare_openapi_responses.py
smoke-output*.txt
```

Allowed:

```text
.env.example
data/.gitkeep
```

Optional Docker verification:

```powershell
docker compose -f docker-compose.local.yml up --build
python smoke_endpoints.py http://localhost:8080 test-api-key docker-compose-test-tenant
```

---

## 34. Current known limitations

The following are not active locally:

```text
external LLM generation
Prometheus /metrics
OpenTelemetry
official Schemathesis / acceptance harness
official Bitbucket CI
official Artifact Registry push
official deployment
official evaluation suite
official performance/load verification
```

The service is ready for local functional review with the documented limitations.
