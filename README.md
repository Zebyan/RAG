# CityDock / Lex-Advisor RAG Service

FastAPI-based implementation of a Romanian legal-domain RAG service aligned with the CityDock `/v1` RAG API contract.

The service implements local RAG behavior with:

- authenticated `/v1` endpoints;
- tenant isolation;
- tenant-scoped idempotent ingest;
- JSON URL ingest;
- multipart file ingest;
- document extraction;
- article-aware Romanian legal chunking;
- SQLite persistence;
- Qdrant vector database;
- local `sentence-transformers` embeddings;
- hybrid retrieval;
- citation-grounded deterministic answers;
- no-hallucination fallback behavior;
- contract-aligned lowercase error envelopes;
- static OpenAPI contract serving at `/v1/openapi.json`;
- Docker and Docker Compose support;
- pinned Docker base image digest;
- automated tests and expanded endpoint smoke tests.

---

## Current status

Implemented and verified locally:

- FastAPI service.
- `/v1` endpoint surface.
- Bearer API-key validation.
- Required `X-Request-ID`.
- Required `X-Tenant-ID`.
- Tenant-scoped data isolation.
- Tenant-scoped `Idempotency-Key` handling.
- Persistent SQLite storage.
- URL ingest.
- Multipart file upload ingest.
- Document extraction for:
  - `text/plain`;
  - `text/markdown`;
  - `text/html`;
  - `application/pdf`.
- Oversized multipart upload rejection with `413 payload_too_large`.
- MIME validation with `415 unsupported_media_type`.
- Romanian legal article-aware chunking.
- Qdrant vector database.
- Local embeddings with `sentence-transformers`.
- Hybrid retrieval:
  - exact article match;
  - vector search;
  - lexical scoring;
  - phrase matching;
  - Romanian/diacritic normalization;
  - namespace diversity.
- Citation-based deterministic answers.
- No-answer fallback:
  - `answer: null`;
  - `citations: []`;
  - `confidence: 0.0`.
- Namespace stats.
- Source deletion with `204 No Content`.
- Namespace deletion with contract-aligned `202 Accepted`:
  - `job_id: del_...`;
  - `status: queued`;
  - `sla: 24h`.
- Standard response headers:
  - `X-Request-ID`;
  - `X-Vendor-Trace-ID`;
  - `X-Vendor-Retrieval-Strategy`;
  - `Server-Timing`.
- Static `openapi.yaml` contract served as JSON at `/v1/openapi.json`.
- Runtime OpenAPI path and response-code comparison verified against `openapi.yaml`.
- Dockerfile with pinned Python base image digest.
- `docker-compose.local.yml`.
- `docker-compose.service.yml`.
- Local tests and expanded smoke tests.

Not active locally:

- external LLM answer generation;
- Prometheus `/metrics`;
- OpenTelemetry;
- official CityDock CI/deployment;
- official CityDock acceptance/evaluation suite.

The default answer generation is deterministic and citation-based. No external LLM is called by default.

---

## Repository structure

```text
citydock-rag-service/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   ├── errors.py
│   ├── auth.py
│   ├── routes/
│   │   ├── health.py
│   │   ├── openapi.py
│   │   ├── query.py
│   │   ├── ingest.py
│   │   └── namespaces.py
│   └── services/
│       ├── answer_service.py
│       ├── document_extractor.py
│       ├── embedding_service.py
│       ├── ingest_service.py
│       ├── legal_chunker.py
│       ├── namespace_service.py
│       ├── retrieval_service.py
│       ├── sqlite_store.py
│       ├── store.py
│       ├── url_fetcher.py
│       └── vector_store.py
├── data/
│   └── .gitkeep
├── docs/
├── examples/
├── fixtures/
├── scripts/
├── tests/
├── .env.example
├── .gitignore
├── DELIVERY_NOTES.md
├── Dockerfile
├── README.md
├── docker-compose.local.yml
├── docker-compose.service.yml
├── openapi.yaml
├── pytest.ini
├── requirements.txt
├── requirements-dev.txt
└── smoke_endpoints.py
```

---

## Architecture

```text
Client
  |
  | HTTP /v1
  v
FastAPI routes
  |
  +--> auth.py
  |      - Authorization validation
  |      - X-Request-ID validation
  |      - X-Tenant-ID scoping
  |
  +--> routes/ingest.py
  |      - JSON ingest
  |      - multipart ingest
  |      - 413 oversized upload rejection
  |      - ingest job polling
  |
  +--> routes/query.py
  |      - hybrid retrieval
  |      - citation response
  |
  +--> routes/namespaces.py
  |      - namespace stats
  |      - source delete
  |      - namespace delete
  |
  +--> routes/openapi.py
  |      - serves root openapi.yaml as JSON
  |
  +--> services/
         |
         +--> ingest_service.py
         |      - idempotency
         |      - URL/file text resolution
         |      - job status
         |      - chunking
         |      - embedding
         |      - indexing
         |
         +--> url_fetcher.py
         |      - HTTP URL fetching
         |      - MIME handling
         |      - extraction handoff
         |
         +--> document_extractor.py
         |      - text/plain extraction
         |      - text/markdown extraction
         |      - text/html visible text extraction
         |      - application/pdf extraction
         |      - document size validation
         |
         +--> legal_chunker.py
         |      - Romanian legal article chunking
         |      - section/chapter metadata
         |      - paragraph/point metadata
         |
         +--> embedding_service.py
         |      - sentence-transformers model loading
         |      - text to 384-dimensional vectors
         |
         +--> vector_store.py
         |      - Qdrant collection management
         |      - vector upsert
         |      - vector search
         |      - source/namespace vector deletion
         |
         +--> retrieval_service.py
         |      - exact article boost
         |      - vector retrieval
         |      - lexical retrieval
         |      - reranking
         |
         +--> answer_service.py
         |      - deterministic grounded answer
         |      - citation markers
         |      - no-answer behavior
         |
         +--> sqlite_store.py
                - jobs
                - idempotency records
                - sources
                - chunks
                - namespace stats
```

Local infrastructure:

```text
SQLite
  - ./data/app.db

Qdrant
  - http://localhost:6333
  - collection: rag_chunks
```

---

## Requirements

Recommended:

```text
Python 3.12.x
Docker Desktop
PowerShell or compatible shell
```

Runtime dependencies are in:

```text
requirements.txt
```

Development/test dependencies are in:

```text
requirements-dev.txt
```

Runtime dependencies include `PyYAML`, used to serve the static `openapi.yaml` contract as JSON at `/v1/openapi.json`.

---

## Clone and run locally

### 1. Clone repository

```powershell
git clone <repo-url>
cd <repo-folder>
```

### 2. Create virtual environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

On Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```powershell
pip install -r requirements-dev.txt
```

### 4. Create local environment file

```powershell
copy .env.example .env
```

For local Python execution, make sure `.env` contains:

```env
RAG_API_KEY=test-api-key
DATABASE_PATH=./data/app.db
VECTOR_STORE=qdrant
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=rag_chunks
EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_DIM=384
LLM_PROVIDER=none
```

### 5. Start Qdrant

```powershell
docker compose -f docker-compose.local.yml up qdrant
```

Verify Qdrant:

```powershell
curl.exe http://localhost:6333/collections
```

### 6. Start the API

In another terminal:

```powershell
.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

Health check:

```powershell
curl.exe http://localhost:8080/v1/health
```

Expected response:

```json
{
  "status": "ok",
  "version": "0.1.0",
  "uptime_seconds": 12,
  "dependencies": {
    "vector_store": "ok",
    "llm": "ok",
    "object_store": "ok"
  }
}
```

---

## Run with Docker Compose

For Docker Compose, the API container must use:

```env
QDRANT_URL=http://qdrant:6333
DATABASE_PATH=/app/data/app.db
```

Run:

```powershell
docker compose -f docker-compose.local.yml up --build
```

Then test:

```powershell
curl.exe http://localhost:8080/v1/health
python smoke_endpoints.py http://localhost:8080 test-api-key docker-compose-test-tenant
```

Expected final smoke test output:

```text
ALL ENDPOINT SMOKE TESTS PASSED
```

---

## Run tests

Make sure Qdrant is running locally:

```powershell
curl.exe http://localhost:6333/collections
```

Then run:

```powershell
pytest
```

Expected result:

```text
all tests passed
```

The test suite covers:

- auth validation;
- validation error envelopes;
- response headers;
- ingest;
- URL fetcher;
- multipart file upload;
- oversized upload `413`;
- document extraction;
- idempotency;
- ingest polling;
- legal chunking;
- Qdrant vector store;
- hybrid retrieval;
- tenant isolation;
- namespace stats;
- source deletion;
- namespace deletion;
- static OpenAPI contract serving;
- no-answer behavior.

---

## Endpoint smoke test

With Qdrant and API running:

```powershell
python smoke_endpoints.py
```

Optional explicit arguments:

```powershell
python smoke_endpoints.py http://localhost:8080 test-api-key endpoint-test-tenant
```

Run the expanded suite including the 50 MiB oversized upload check:

```powershell
python smoke_endpoints.py --include-large-upload
```

Probe optional endpoints such as `/metrics` and `/v1/eval`:

```powershell
python smoke_endpoints.py --include-optional
```

Save smoke output in PowerShell:

```powershell
$env:PYTHONIOENCODING="utf-8"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
python smoke_endpoints.py --include-large-upload 2>&1 | Tee-Object -FilePath smoke-output-full.txt
```

Expected final output:

```text
ALL ENDPOINT SMOKE TESTS PASSED
```

The expanded smoke script validates:

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

---

## API authentication headers

Most `/v1` endpoints require:

```text
Authorization: Bearer test-api-key
X-Request-ID: <uuid>
X-Tenant-ID: <tenant-id>
```

Ingest also requires:

```text
Idempotency-Key: <uuid>
```

Example headers:

```powershell
-H "Authorization: Bearer test-api-key"
-H "X-Request-ID: 11111111-1111-4111-8111-111111111111"
-H "X-Tenant-ID: ph-balta-doamnei"
```

---

## Contract-aligned error behavior

All non-2xx responses use the standard envelope:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed.",
    "request_id": "11111111-1111-4111-8111-111111111111",
    "details": {}
  }
}
```

Implemented lowercase error codes include:

```text
invalid_request
unauthorized
not_found
namespace_not_found
duplicate_job
payload_too_large
unsupported_media_type
validation_error
```

Examples verified by smoke tests:

```text
401 unauthorized
409 duplicate_job
413 payload_too_large
415 unsupported_media_type
422 validation_error
404 not_found / namespace_not_found
```

---

## API examples with curl

### 1. Health

```powershell
curl.exe http://localhost:8080/v1/health
```

Expected response:

```json
{
  "status": "ok",
  "version": "0.1.0",
  "uptime_seconds": 12,
  "dependencies": {
    "vector_store": "ok",
    "llm": "ok",
    "object_store": "ok"
  }
}
```

### 2. JSON ingest with inline fixture text

Create `examples/ingest.json`:

```json
{
  "namespace_id": "legea_31_1990",
  "source_id": "s_47381",
  "source_type": "url",
  "url": "https://legislatie.just.ro/Public/DetaliiDocument/47381",
  "mime_type_hint": "text/plain",
  "metadata": {
    "source_title": "Legea 31/1990 privind societățile comerciale",
    "text": "Articolul 15. Aporturile în numerar sunt obligatorii la constituirea oricărei forme de societate.\n\nArticolul 16. Aporturile în natură trebuie să fie evaluabile din punct de vedere economic."
  }
}
```

Run:

```powershell
curl.exe -X POST http://localhost:8080/v1/ingest `
  -H "Authorization: Bearer test-api-key" `
  -H "Content-Type: application/json" `
  -H "X-Request-ID: 22222222-2222-4222-8222-222222222222" `
  -H "X-Tenant-ID: ph-balta-doamnei" `
  -H "Idempotency-Key: 99999999-9999-4999-8999-999999999999" `
  --data-binary "@examples/ingest.json"
```

Expected response:

```json
{
  "job_id": "j_...",
  "status": "queued",
  "submitted_at": "2026-04-26T18:00:00Z",
  "estimated_completion_at": "2026-04-26T18:05:00Z"
}
```

Although the response says `queued`, the MVP processes the job synchronously and the job status should become `done`.

### 3. Poll ingest job

```powershell
curl.exe -X GET http://localhost:8080/v1/ingest/j_... `
  -H "Authorization: Bearer test-api-key" `
  -H "X-Request-ID: 33333333-3333-4333-8333-333333333333" `
  -H "X-Tenant-ID: ph-balta-doamnei"
```

Expected response:

```json
{
  "job_id": "j_...",
  "namespace_id": "legea_31_1990",
  "source_id": "s_47381",
  "status": "done",
  "progress": {
    "stage": "indexing",
    "percent": 100,
    "chunks_created": 2
  },
  "submitted_at": "2026-04-26T18:00:00Z",
  "completed_at": "2026-04-26T18:00:01Z",
  "error": null
}
```

### 4. Query article 15

Create `examples/query.json`:

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

Run:

```powershell
curl.exe -X POST http://localhost:8080/v1/query `
  -H "Authorization: Bearer test-api-key" `
  -H "Content-Type: application/json" `
  -H "X-Request-ID: 11111111-1111-4111-8111-111111111111" `
  -H "X-Tenant-ID: ph-balta-doamnei" `
  --data-binary "@examples/query.json"
```

Expected response shape:

```json
{
  "request_id": "11111111-1111-4111-8111-111111111111",
  "answer": "Articolul 15 prevede următoarele: Articolul 15. Aporturile în numerar sunt obligatorii la constituirea oricărei forme de societate. [1].",
  "citations": [
    {
      "marker": "[1]",
      "chunk": {
        "content": "Articolul 15. Aporturile în numerar sunt obligatorii la constituirea oricărei forme de societate.",
        "article_number": "15",
        "source_id": "s_47381",
        "source_title": "Legea 31/1990 privind societățile comerciale",
        "namespace_id": "legea_31_1990",
        "score": 0.7
      }
    }
  ],
  "usage": {
    "input_tokens": 0,
    "output_tokens": 0,
    "cost_usd": 0.0,
    "model_id": "mvp-local"
  },
  "retrieval_strategy": "hybrid_qdrant_article_keyword",
  "confidence": 0.7
}
```

Expected response headers include:

```text
X-Request-ID: 11111111-1111-4111-8111-111111111111
X-Vendor-Trace-ID: tr_...
X-Vendor-Retrieval-Strategy: hybrid_qdrant_article_keyword
Server-Timing: app;dur=...
```

### 5. Query empty/no-answer behavior

Create `examples/query_empty.json`:

```json
{
  "question": "Care este programul primăriei Bălta Doamnei?",
  "language": "ro",
  "namespaces": ["legea_31_1990"],
  "top_k": 5,
  "include_answer": true
}
```

Run:

```powershell
curl.exe -X POST http://localhost:8080/v1/query `
  -H "Authorization: Bearer test-api-key" `
  -H "Content-Type: application/json" `
  -H "X-Request-ID: 55555555-5555-4555-8555-555555555555" `
  -H "X-Tenant-ID: ph-balta-doamnei" `
  --data-binary "@examples/query_empty.json"
```

Expected response:

```json
{
  "answer": null,
  "citations": [],
  "confidence": 0.0
}
```

### 6. URL ingest

Create `examples/ingest_url.json`:

```json
{
  "namespace_id": "url_demo_namespace",
  "source_id": "url_demo_source",
  "source_type": "url",
  "url": "https://example.com/legal.txt",
  "mime_type_hint": "text/plain",
  "metadata": {
    "source_title": "Fetched Legal Text"
  }
}
```

Run:

```powershell
curl.exe -X POST http://localhost:8080/v1/ingest `
  -H "Authorization: Bearer test-api-key" `
  -H "Content-Type: application/json" `
  -H "X-Request-ID: 66666666-6666-4666-8666-666666666666" `
  -H "X-Tenant-ID: ph-balta-doamnei" `
  -H "Idempotency-Key: 66666666-6666-4666-8666-666666666667" `
  --data-binary "@examples/ingest_url.json"
```

Expected success response:

```json
{
  "job_id": "j_...",
  "status": "queued",
  "submitted_at": "...",
  "estimated_completion_at": "..."
}
```

If the URL is unreachable, has unsupported MIME type, or contains no extractable text, the job is marked as `failed` when polled.

### 7. Multipart file ingest

Create `examples/file_payload.json`:

```json
{
  "namespace_id": "uploaded_legea_31",
  "source_id": "uploaded_s_001",
  "source_type": "file",
  "mime_type_hint": "text/plain",
  "metadata": {
    "source_title": "Uploaded Legal Text"
  }
}
```

Create `examples/legea_31.txt`:

```text
Articolul 15.
Aporturile în numerar sunt obligatorii la constituirea oricărei forme de societate.
```

Run:

```powershell
curl.exe -X POST http://localhost:8080/v1/ingest `
  -H "Authorization: Bearer test-api-key" `
  -H "X-Request-ID: 77777777-7777-4777-8777-777777777777" `
  -H "X-Tenant-ID: ph-balta-doamnei" `
  -H "Idempotency-Key: 77777777-7777-4777-8777-777777777778" `
  -F "payload=<examples/file_payload.json;type=application/json" `
  -F "file=@examples/legea_31.txt;type=text/plain"
```

Expected response:

```json
{
  "job_id": "j_...",
  "status": "queued",
  "submitted_at": "...",
  "estimated_completion_at": "..."
}
```

Then query the uploaded namespace.

### 8. Oversized multipart upload

The API rejects uploaded files larger than 50 MiB before job creation:

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

This is covered by:

```powershell
python smoke_endpoints.py --include-large-upload
```

### 9. Namespace stats

```powershell
curl.exe -X GET http://localhost:8080/v1/namespaces/legea_31_1990/stats `
  -H "Authorization: Bearer test-api-key" `
  -H "X-Request-ID: 99999999-9999-4999-8999-999999999999" `
  -H "X-Tenant-ID: ph-balta-doamnei"
```

Expected response:

```json
{
  "namespace_id": "legea_31_1990",
  "chunk_count": 2,
  "source_count": 1,
  "total_tokens_indexed": 27,
  "last_ingested_at": "...",
  "embedding_model": "paraphrase-multilingual-MiniLM-L12-v2",
  "embedding_dim": 384
}
```

### 10. Delete source

```powershell
curl.exe -X DELETE http://localhost:8080/v1/namespaces/legea_31_1990/sources/s_47381 `
  -H "Authorization: Bearer test-api-key" `
  -H "X-Request-ID: aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa" `
  -H "X-Tenant-ID: ph-balta-doamnei" `
  -i
```

Expected:

```text
HTTP/1.1 204 No Content
```

A later query should return no answer.

### 11. Delete namespace

```powershell
curl.exe -X DELETE http://localhost:8080/v1/namespaces/legea_31_1990 `
  -H "Authorization: Bearer test-api-key" `
  -H "X-Request-ID: bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb" `
  -H "X-Tenant-ID: ph-balta-doamnei"
```

Expected response shape:

```json
{
  "job_id": "del_...",
  "status": "queued",
  "sla": "24h"
}
```

Although local deletion is performed immediately, the response shape follows the contract's asynchronous delete acknowledgement.

---

## OpenAPI

The repository contains:

```text
openapi.yaml
```

The running service exposes the static contract as JSON:

```text
GET /v1/openapi.json
```

Implementation:

```text
openapi.yaml
→ app/routes/openapi.py
→ PyYAML loads the static YAML contract
→ JSONResponse returns it at /v1/openapi.json
```

Generate a local runtime schema snapshot:

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

The generated snapshot and comparison helper scripts are local artifacts and should not normally be committed.

---

## Docker image size note

The Dockerfile uses a pinned Python base image digest for reproducible builds.

The Docker image includes a local multilingual embedding runtime using `sentence-transformers` and CPU-only PyTorch.

This keeps Romanian legal documents and user questions inside the deployed stack and avoids third-party embedding APIs, but increases image size beyond a minimal FastAPI-only image.

A production optimization path is to move embeddings to an internal embedding service or replace the embedding runtime with ONNX/FastEmbed after quality validation.

---

## External LLM status

External LLM generation is not active by default.

Current response generation is deterministic and citation-based.

Current flow:

```text
query
→ retrieve chunks
→ build citations
→ build deterministic answer from retrieved citation text
```

Planned optional flow:

```text
query
→ retrieve chunks
→ build grounded prompt
→ external/internal LLM generation
→ preserve citations
→ fallback to deterministic answer on LLM failure
```

Default configuration:

```env
LLM_PROVIDER=none
```

---

## Troubleshooting

### Qdrant connection refused

Start Qdrant:

```powershell
docker compose -f docker-compose.local.yml up qdrant
```

Verify:

```powershell
curl.exe http://localhost:6333/collections
```

### Local tests cannot reach Qdrant

For local `pytest`, use:

```env
QDRANT_URL=http://localhost:6333
```

For Docker Compose, use:

```env
QDRANT_URL=http://qdrant:6333
```

### Sentence-transformers model download is slow

The first embedding test or first ingest may take longer because the model is downloaded and cached locally.

Model:

```text
paraphrase-multilingual-MiniLM-L12-v2
```

### PowerShell corrupts diacritics

For Unicode-safe endpoint tests:

```powershell
$env:PYTHONIOENCODING="utf-8"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
python smoke_endpoints.py --include-large-upload 2>&1 | Tee-Object -FilePath smoke-output-full.txt
```

---

