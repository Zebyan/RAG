# Lex-Advisor RAG Service — Technical Blueprint

**Version:** 1.2  
**Date:** 2026-04-25  
**Scope:** Pre-Bitbucket-access implementation blueprint for a local MVP that can later be pushed into the CityDock-provided repository.

This document describes the architecture, project structure, implementation workflow, modules, functions, inputs, outputs, API behavior, tests, and compliance boundaries for a FastAPI-based RAG service implementation.

The goal is to prepare everything that can reasonably be completed before CityDock grants access to their Bitbucket repository and deployment pipeline.

---

## 1. Scope and Delivery Boundary

### 1.1 What this blueprint covers

This blueprint covers the local implementation of a functional RAG service MVP:

```text
FastAPI service
/v1 API contract
Pydantic schemas
API-key authentication
X-Request-ID handling
X-Tenant-ID isolation
Idempotency-Key support for ingest
Document ingestion
Text extraction
Legal-aware chunking
Embeddings
ChromaDB vector storage
Article-number retrieval boost
Citation-based answer generation
No-hallucination empty-result behavior
Namespace stats
Source deletion
Namespace deletion
Local tests
Dockerfile
docker-compose.service.yml
README
openapi.yaml
/v1/openapi.json
```

### 1.2 What cannot be completed before CityDock access

The following items depend on CityDock infrastructure and cannot be fully completed locally:

```text
Push to their Bitbucket organization
Create the official semver tag in their repository
Trigger their self-hosted Bitbucket Pipelines runner
Produce official CI logs from their runner
Push the image to their GCP Artifact Registry
Deploy into their stack
Confirm the tagged pipeline is green in their environment
Complete the official handoff inside their organization
```

### 1.3 MVP versus production

The implementation can be production-shaped, but the local version should be presented as an MVP unless a formal collaboration exists.

Implemented locally:

```text
Core API behavior
Core RAG behavior
Local persistence
Local Docker execution
Local contract-oriented tests
Smoke tests
```

Production/vendor scope:

```text
Formal SLO guarantees
Full Trivy reports
Full OpenTelemetry pipeline
Prometheus production dashboards
DPA/IP/legal handoff
30-day support SOW
24/7 on-call
Status page
EU data residency attestation
Official CI logs from their infrastructure
```

---

## 2. High-Level Architecture

### 2.1 System overview

```text
Client / Lex-Advisor Platform
        |
        | HTTP / JSON / multipart
        v
FastAPI Application
        |
        +--> Auth Layer
        |       - Authorization: Bearer <api_key>
        |       - X-Request-ID
        |       - X-Tenant-ID
        |       - Idempotency-Key for ingest
        |
        +--> API Routers
        |       - /v1/health
        |       - /v1/openapi.json
        |       - /v1/ingest
        |       - /v1/ingest/{job_id}
        |       - /v1/query
        |       - /v1/namespaces/{namespace_id}/stats
        |       - DELETE source
        |       - DELETE namespace
        |
        +--> Service Layer
        |       - Ingest service
        |       - RAG service
        |       - Retrieval service
        |       - Answer generation service
        |       - Namespace service
        |
        +--> Persistence Layer
        |       - Thread-safe store or SQLite for jobs/sources/stats
        |       - ChromaDB for vector chunks
        |       - Local filesystem for persistent data
        |
        +--> Optional External Services
                - Anthropic / Claude for answer generation
                - Optional webhook callback target
```

### 2.2 Logical components

| Component | Responsibility |
|---|---|
| FastAPI app | HTTP routing, schema validation, response generation |
| Auth layer | Validates API key, request ID, tenant ID, idempotency key |
| Models | Pydantic request/response schemas matching the contract |
| Store | Tracks jobs, sources, namespace stats, idempotency records |
| ChromaDB | Stores embedded chunks and metadata |
| Embedding model | Converts chunks/questions into vectors |
| Ingest worker | Fetches/extracts/chunks/embeds/indexes documents |
| Retrieval service | Finds relevant chunks scoped by tenant and namespace |
| Answer service | Generates answer text and citations |
| Tests | Verifies API contract behavior and RAG domain behavior |
| Docker | Runs the service on port 8080 with healthcheck |

---

## 3. Core Workflows

## 3.1 Query workflow

```text
POST /v1/query
  |
  v
Validate Authorization, X-Request-ID, X-Tenant-ID
  |
  v
Validate QueryRequest with Pydantic
  |
  v
Filter candidate chunks by tenant_id + namespaces
  |
  v
If hint_article_number exists:
  search exact article candidates first
  |
  v
Run vector search / keyword search / BM25 fallback
  |
  v
Merge and deduplicate candidates
  |
  v
Score candidates
  |
  v
If no reliable candidates:
  return answer=null, citations=[], confidence=0.0
  |
  v
Build citations [1], [2], ...
  |
  v
If include_answer=false:
  return citations only, answer=null
  |
  v
Generate answer deterministically or with LLM
  |
  v
Return QueryResponse
```

### Query guarantees

```text
No global search without tenant filtering
No hallucination if no relevant source exists
Plain Romanian text only
No Markdown in answer
Citation markers must match citation order
Every cited statement must be grounded in returned chunks
```

---

## 3.2 Ingest workflow

```text
POST /v1/ingest
  |
  v
Validate Authorization, X-Request-ID, X-Tenant-ID, Idempotency-Key
  |
  v
Hash request body
  |
  v
Check idempotency by tenant_id + idempotency_key
  |
  +--> same key + same body: return existing job
  |
  +--> same key + different body: return 409 duplicate_job
  |
  v
Validate source_type, URL/file, MIME, file size
  |
  v
Create job status=queued
  |
  v
Start background ingest worker
  |
  v
Return 202 IngestAcceptedResponse
```

Background worker:

```text
queued
  -> fetching
  -> extracting
  -> chunking
  -> embedding
  -> indexing
  -> done
```

On failure:

```text
failed + error={code,message,retryable}
```

---

## 3.3 Ingest polling workflow

```text
GET /v1/ingest/{job_id}
  |
  v
Validate Authorization and X-Tenant-ID
  |
  v
Find job by tenant_id + job_id
  |
  +--> not found: 404 not_found
  |
  v
If non-terminal status:
  add Retry-After header
  |
  v
Return full IngestJobStatus
```

---

## 3.4 Delete source workflow

```text
DELETE /v1/namespaces/{namespace_id}/sources/{source_id}
  |
  v
Validate Authorization, X-Request-ID, X-Tenant-ID
  |
  v
Find source by tenant_id + namespace_id + source_id
  |
  +--> not found: 404 not_found
  |
  v
Delete source registry entry
  |
  v
Delete all associated chunks from ChromaDB
  |
  v
Update namespace stats
  |
  v
Return 204 No Content
```

---

## 3.5 Delete namespace workflow

```text
DELETE /v1/namespaces/{namespace_id}
  |
  v
Validate Authorization, X-Request-ID, X-Tenant-ID
  |
  v
Find namespace by tenant_id + namespace_id
  |
  +--> not found: 404 not_found
  |
  v
Create deletion job del_...
  |
  v
Delete all sources, chunks, embeddings, stats for tenant_id + namespace_id
  |
  v
Return 202 { job_id, status: "queued", sla: "24h" }
```

---

## 3.6 Namespace stats workflow

```text
GET /v1/namespaces/{namespace_id}/stats
  |
  v
Validate Authorization and X-Tenant-ID
  |
  v
Find namespace by tenant_id + namespace_id
  |
  +--> not found: 404 not_found
  |
  v
Read or compute stats
  |
  v
Return NamespaceStats
```

---

## 4. Project Structure

```text
lex-advisor-rag/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   ├── errors.py
│   ├── auth.py
│   ├── logging_config.py
│   ├── utils.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── store.py
│   │   ├── rag.py
│   │   ├── ingest_worker.py
│   │   ├── retrieval.py
│   │   ├── answer.py
│   │   └── namespace.py
│   │
│   └── routers/
│       ├── __init__.py
│       ├── health.py
│       ├── openapi.py
│       ├── query.py
│       ├── ingest.py
│       └── namespace.py
│
├── fixtures/
│   ├── legea_31_1990.txt
│   ├── cod_civil.txt
│   └── primaria_balta_doamnei.txt
│
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_health.py
│   ├── test_ingest.py
│   ├── test_query.py
│   ├── test_namespace.py
│   ├── test_domain.py
│   └── test_tenant_isolation.py
│
├── scripts/
│   ├── smoke_health.sh
│   ├── smoke_ingest.sh
│   ├── smoke_query_article15.sh
│   ├── smoke_empty_result.sh
│   └── smoke_stats.sh
│
├── data/
│   └── .gitkeep
│
├── docs/
│   ├── smoke-tests.md
│   └── local-eval.md
│
├── openapi.yaml
├── generated-openapi.local.json
├── requirements.txt
├── Dockerfile
├── docker-compose.service.yml
├── bitbucket-pipelines.yml
├── .env.example
├── .gitignore
├── README.md
├── DELIVERY_NOTES.md
└── technical-blueprint.md
```

---

## 5. Repository-Level Files

## 5.1 `README.md`

Purpose:

```text
Main user/developer documentation.
```

Must include:

```text
Project overview
MVP scope
Production scope not implemented
Architecture summary
Endpoint list
Environment variables
Local run instructions
Docker run instructions
Smoke test commands
Troubleshooting
Known limitations
```

---

## 5.2 `openapi.yaml`

Purpose:

```text
Committed OpenAPI contract at repository root.
```

Recommendation:

```text
Use the provided rag-api-spec.yaml as openapi.yaml.
Expose /v1/openapi.json from the running service.
Optionally save FastAPI-generated schema as generated-openapi.local.json for comparison.
```

---

## 5.3 `Dockerfile`

MVP requirements:

```text
Python 3.12
Service listens on port 8080
Non-root runtime user appuser uid 1000
HEALTHCHECK calling GET /v1/health
Logs to stdout
```

Production requirements to prepare or document as TODO:

```text
Multi-stage build
Pinned base image by SHA-256 digest
Final image size under 500 MB
Graceful SIGTERM handling
```

---

## 5.4 `docker-compose.service.yml`

Purpose:

```text
Compose fragment showing how the service runs inside their stack.
```

Rules:

```text
One main service
No host ports exposed
Use expose: "8080"
Join external network lex-advisor
Use env vars, no hardcoded secrets
Declare own volumes/services if needed
```

Example:

```yaml
services:
  rag-service:
    build:
      context: .
      dockerfile: Dockerfile
    env_file:
      - .env
    expose:
      - "8080"
    volumes:
      - rag_data:/app/data
    networks:
      - lex-advisor
    restart: unless-stopped

volumes:
  rag_data:

networks:
  lex-advisor:
    external: true
```

---

## 5.5 `.env.example`

```env
RAG_API_KEY=test-api-key
APP_VERSION=0.1.0
APP_ENV=local
CHROMA_PERSIST_PATH=./data/chroma
EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_DIM=384
LLM_PROVIDER=none
ANTHROPIC_API_KEY=
WEBHOOK_SECRET=
LOG_LEVEL=INFO
```

---

## 5.6 `requirements.txt`

Minimum:

```text
fastapi
uvicorn[standard]
pydantic
python-dotenv
httpx
chromadb
sentence-transformers
beautifulsoup4
pypdf
pytest
```

Optional:

```text
rank-bm25
anthropic
prometheus-client
opentelemetry-distro
```

---

## 5.7 `DELIVERY_NOTES.md`

Purpose:

```text
Explain what was implemented locally and what requires CityDock infrastructure.
```

Should include:

```text
Implemented locally
Simplified locally
Out of scope for MVP
Cannot be completed without Bitbucket access
How to run local smoke tests
How to push once repository access is granted
```

---

## 6. Application Modules

---

## 6.1 `app/main.py`

Application entry point.

Responsibilities:

```text
Create FastAPI app
Configure title/version
Include routers
Register exception handlers
Initialize store/ChromaDB on startup
Expose /v1/openapi.json
Configure logging
```

Expected routers:

```text
health_router
openapi_router
query_router
ingest_router
namespace_router
```

---

## 6.2 `app/config.py`

Centralized configuration.

Recommended `Settings` fields:

```text
APP_VERSION: str
APP_ENV: str
RAG_API_KEY: str
CHROMA_PERSIST_PATH: str | None
EMBEDDING_MODEL: str
EMBEDDING_DIM: int
LLM_PROVIDER: str
ANTHROPIC_API_KEY: str | None
WEBHOOK_SECRET: str | None
LOG_LEVEL: str
MAX_FILE_SIZE_BYTES: int = 50 * 1024 * 1024
URL_FETCH_TIMEOUT_SECONDS: int = 60
```

---

## 6.3 `app/models.py`

Contains all Pydantic schemas. No business logic.

### Common models

#### `ErrorDetail`

```text
Fields:
  code: str
  message: str
  request_id: str | null
  details: dict
```

#### `ErrorResponse`

```text
Fields:
  error: ErrorDetail
```

All non-2xx responses must use this shape.

#### `Usage`

```text
Fields:
  input_tokens: int
  output_tokens: int
  cost_usd: float
  model_id: str
```

If no external LLM is used:

```json
{
  "input_tokens": 0,
  "output_tokens": 0,
  "cost_usd": 0,
  "model_id": "mvp-local"
}
```

---

### Query models

#### `ConversationTurn`

```text
Fields:
  role: "user" | "assistant"
  content: str
```

#### `StyleHints`

```text
Fields:
  answer_max_chars: int = 2000
  cite_inline: bool = true
  tone: "formal" | "casual" = "formal"
```

#### `QueryRequest`

Required:

```text
question: str, max 2000 chars
language: "ro"
namespaces: list[str], min 1, max 10
```

Optional:

```text
top_k: int = 10, min 1, max 50
hint_article_number: str | null
rerank: bool = true
include_answer: bool = true
conversation_history: list[ConversationTurn], max 15
style_hints: StyleHints | null
```

#### `Chunk`

Required:

```text
chunk_id: UUID string
content: str, max 4000 chars
source_id: str
namespace_id: str
score: float, 0.0-1.0
```

Optional:

```text
article_number: str | null
section_title: str | null
point_number: str | null
page_number: int | null
source_url: str | null
source_title: str | null
metadata: dict
```

#### `Citation`

```text
marker: str
chunk: Chunk
```

Example marker:

```text
[1]
[2]
```

#### `QueryResponse`

Required:

```text
request_id: UUID string
citations: list[Citation]
usage: Usage
latency_ms: int
model_version: str
```

Optional:

```text
answer: str | null
retrieval_strategy: str | null
confidence: float | null
trace_id: str | null
```

Empty-result response:

```json
{
  "answer": null,
  "citations": [],
  "confidence": 0.0
}
```

---

### Ingest models

#### `IngestRequest`

Required:

```text
namespace_id: str
source_id: str
source_type: "url" | "file"
```

Conditional:

```text
url: required when source_type="url"
mime_type_hint: recommended
```

Optional:

```text
metadata: dict
callback_url: str | null
```

#### `IngestAcceptedResponse`

Used by `POST /v1/ingest`.

```text
job_id: str
status: "queued"
submitted_at: ISO 8601 UTC string
estimated_completion_at: ISO 8601 UTC string | null
```

#### `IngestProgress`

```text
stage: queued | fetching | extracting | chunking | embedding | indexing | done
percent: int, 0-100
chunks_created: int
```

#### `IngestJobStatus`

Used by `GET /v1/ingest/{job_id}`.

```text
job_id: str
namespace_id: str
source_id: str
status: queued | fetching | extracting | chunking | embedding | indexing | done | failed | cancelled
progress: IngestProgress
submitted_at: ISO 8601 UTC string
completed_at: ISO 8601 UTC string | null
error: dict | null
```

---

### Namespace models

#### `NamespaceStats`

```text
namespace_id: str
chunk_count: int
source_count: int
total_tokens_indexed: int
last_ingested_at: ISO 8601 UTC string | null
embedding_model: str
embedding_dim: int
```

#### `DeleteNamespaceResponse`

```text
job_id: str
status: "queued"
sla: "24h"
```

---

### Health models

#### `HealthStatus`

```text
status: "ok" | "degraded" | "down"
version: str
uptime_seconds: int
dependencies: dict
```

Expected dependencies:

```json
{
  "vector_store": "ok",
  "llm": "ok",
  "object_store": "ok"
}
```

---

## 6.4 `app/errors.py`

Builds standardized API errors.

### `error_response(code, message, request_id, details, status_code) -> JSONResponse`

Input:

```text
code: str
message: str
request_id: str | null
details: dict
status_code: int
```

Output:

```json
{
  "error": {
    "code": "invalid_request",
    "message": "Missing X-Request-ID header.",
    "request_id": "11111111-1111-4111-8111-111111111111",
    "details": {}
  }
}
```

Recommended helpers:

```text
invalid_request()
unauthorized()
forbidden()
not_found()
namespace_not_found()
duplicate_job()
payload_too_large()
unsupported_media_type()
validation_error()
rate_limited()
internal_error()
upstream_error()
service_unavailable()
timeout_error()
```

---

## 6.5 `app/auth.py`

Authentication and request context dependency.

### `AuthContext`

```text
request_id: str
tenant_id: str
```

### `verify_auth(authorization, x_request_id, x_tenant_id) -> AuthContext`

Input headers:

```text
Authorization
X-Request-ID
X-Tenant-ID
```

Logic:

```text
1. If Authorization is missing: 401 unauthorized
2. Parse "Bearer <token>"
3. If scheme is not bearer: 401 unauthorized
4. Compare token with RAG_API_KEY
5. If invalid: 401 unauthorized
6. Validate X-Request-ID as UUID
7. If invalid: 400 invalid_request
8. Validate X-Tenant-ID is non-empty
9. Return AuthContext
```

Health endpoint does not use this dependency.

---

## 6.6 `app/services/store.py`

Thread-safe local store for jobs, sources, namespace stats, delete jobs, and idempotency records.

MVP implementation:

```text
In-memory dictionaries + threading.Lock()
```

Better local implementation:

```text
SQLite
```

### Mandatory tenant isolation rule

Every stored item must be scoped by tenant where applicable.

```text
tenant_id + namespace_id + source_id
tenant_id + idempotency_key
tenant_id + job_id
tenant_id + namespace_id
```

No operation should use only `namespace_id` globally.

---

### Job functions

#### `set_job(tenant_id, job_id, data) -> None`

Stores a serialized ingest job.

Input:

```text
tenant_id: str
job_id: str
data: dict
```

Output:

```text
None
```

#### `get_job(tenant_id, job_id) -> dict | None`

Returns job for the current tenant only.

#### `update_job(tenant_id, job_id, **kwargs) -> None`

Updates fields of an existing job.

---

### Idempotency functions

#### `get_idem_job(tenant_id, key) -> str | None`

Checks whether the idempotency key was already used by this tenant.

#### `set_idem_job(tenant_id, key, job_id, body_hash) -> None`

Stores idempotency record.

#### `get_idem_body_hash(tenant_id, key) -> str | None`

Used to detect:

```text
same tenant + same key + different body = 409 duplicate_job
```

Two different tenants may use the same idempotency key without conflict.

---

### Source and namespace functions

#### `register_source(tenant_id, namespace_id, source_id, chunk_ids, meta) -> None`

Registers indexed source.

#### `namespace_exists(tenant_id, namespace_id) -> bool`

Checks namespace existence for current tenant.

#### `source_exists(tenant_id, namespace_id, source_id) -> bool`

Checks source existence for current tenant.

#### `delete_source(tenant_id, namespace_id, source_id) -> list[str]`

Deletes source registry entry and returns chunk IDs that must be removed from ChromaDB.

#### `delete_namespace(tenant_id, namespace_id) -> list[str]`

Deletes all source records and stats for this tenant + namespace.

#### `update_ns_stats(tenant_id, namespace_id, stats) -> None`

Stores namespace stats.

#### `get_ns_stats(tenant_id, namespace_id) -> dict | None`

Returns namespace stats for current tenant.

#### `uptime_seconds() -> int`

Returns process uptime.

---

## 6.7 `app/services/rag.py`

Core RAG module.

Responsible for:

```text
Embedding model loading
ChromaDB client loading
Chunking
Article extraction
Vector indexing
Retrieval
Reranking
Answer generation coordination
```

---

### `_get_embed_model() -> SentenceTransformer`

Lazy-loads embedding model.

Recommended model:

```text
paraphrase-multilingual-MiniLM-L12-v2
```

Output:

```text
SentenceTransformer instance
```

Notes:

```text
Loads once on first use
Cached afterward
Embedding dimension: 384
Supports Romanian reasonably for MVP
```

---

### `_get_chroma() -> chromadb.Client`

Lazy-loads ChromaDB client.

Behavior:

```text
If CHROMA_PERSIST_PATH is set:
  use PersistentClient
Else:
  use EphemeralClient
```

### Chroma tenant isolation

Do not use only `namespace_id` as the collection name.

Acceptable option A:

```text
collection_name = sanitize(tenant_id) + "__" + sanitize(namespace_id)
```

Acceptable option B:

```text
single global collection
always filter metadata by tenant_id and namespace_id
```

For MVP, option A is simpler.

---

### `embed_texts(texts) -> list[list[float]]`

Input:

```text
texts: list[str]
```

Output:

```text
list of 384-dimensional vectors
```

---

### `chunk_text(text, chunk_size=800, overlap=100) -> list[str]`

Splits text into chunks.

MVP recommendation:

```text
First split by legal articles if possible.
If article splitting fails, fallback to sliding window by words.
```

Input:

```text
text: str
chunk_size: int
overlap: int
```

Output:

```text
list[str]
```

---

### `chunk_legal_text_by_articles(text) -> list[str]`

Recommended legal-aware chunking function.

Detects:

```text
Articolul 15
Art. 15
Art. 15^1
Articolul II
```

Each article should become one or more chunks while preserving the article number.

---

### `_extract_article_number(text) -> str | None`

Extracts legal article number.

Recommended regex:

```regex
(?i)\b(?:articolul|art\.?)\s+([0-9]+(?:\^[0-9]+)?|[IVXLCDM]+)\b
```

Input:

```text
text: str
```

Output:

```text
"15" | "15^1" | "II" | None
```

---

### `index_chunks(tenant_id, namespace_id, source_id, source_url, source_title, chunks_text, metadata) -> list[str]`

Embeds and stores chunks in ChromaDB.

Input:

```text
tenant_id: str
namespace_id: str
source_id: str
source_url: str | None
source_title: str | None
chunks_text: list[str]
metadata: dict
```

Logic:

```text
1. Generate UUID for each chunk.
2. Embed all chunks in batch.
3. Extract article_number from each chunk.
4. Get Chroma collection scoped by tenant + namespace.
5. Add vectors, documents, IDs, and metadata.
6. Metadata must include tenant_id, namespace_id, source_id, article_number.
```

Output:

```text
list[str] chunk IDs
```

---

### `retrieve(tenant_id, namespaces, question, top_k, hint_article_number) -> list[Chunk]`

Retrieves chunks for query.

Input:

```text
tenant_id: str
namespaces: list[str]
question: str
top_k: int
hint_article_number: str | None
```

Logic:

```text
1. Filter only collections/chunks belonging to tenant_id.
2. Filter only requested namespaces.
3. If hint_article_number exists:
     search exact article candidates first.
4. Run vector search with over-fetch:
     n_results = min(top_k * 5, 50)
5. Run keyword/BM25 fallback over tenant + namespace chunks.
6. Merge exact article candidates + vector candidates + keyword candidates.
7. Deduplicate by chunk_id.
8. Score candidates.
9. Sort by final score descending.
10. Return top_k.
```

Recommended score formula:

```text
final_score =
  0.55 * article_score +
  0.30 * vector_score +
  0.15 * keyword_score
```

Article score:

```text
1.0 if chunk.article_number == hint_article_number
0.0 otherwise
```

Reason:

```text
For legal RAG, exact article matching is more important than semantic similarity.
```

---

### `rerank(chunks, question) -> list[Chunk]`

Reorders chunks.

MVP implementation:

```text
Use score formula from retrieve.
```

Optional implementation:

```text
Cross-encoder reranker
LLM-based relevance check
```

---

### `generate_answer(question, chunks, style_hints, conversation_history) -> tuple[str | None, Usage]`

Generates final answer.

Input:

```text
question: str
chunks: list[Chunk]
style_hints: StyleHints | None
conversation_history: list[ConversationTurn]
```

Logic:

```text
1. If chunks is empty: return None + zero usage.
2. If LLM_PROVIDER=none: use deterministic answer generation.
3. If LLM_PROVIDER=anthropic: build strict grounded prompt and call Claude.
4. Return answer + usage.
```

Strict prompt rules:

```text
Answer in Romanian.
Use plain text only.
Do not use Markdown.
Use only the provided context.
Use citation markers [1], [2].
If the answer is not supported by context, return no answer.
```

Output:

```text
answer: str | None
usage: Usage
```

---

## 6.8 `app/services/ingest_worker.py`

Processes documents after `POST /v1/ingest` returns `202`.

### `run_ingest_job(job_id, request, tenant_id) -> None`

Input:

```text
job_id: str
request: IngestRequest
tenant_id: str
```

Workflow:

```text
[queued -> fetching]
- If source_type=url: fetch content with httpx, timeout 60s.
- If source_type=file: use uploaded bytes.

[fetching -> extracting]
- text/html: BeautifulSoup visible text extraction.
- application/pdf: pypdf extraction.
- text/plain: direct text.
- text/markdown: strip markdown or use direct text.

[extracting -> chunking]
- Prefer legal article chunking.
- Fallback to sliding-window chunking.

[chunking -> embedding]
- Batch embed chunks.

[embedding -> indexing]
- index_chunks(tenant_id, ...)
- register_source(tenant_id, ...)
- update_ns_stats(tenant_id, ...)

[indexing -> done]
- status="done"
- percent=100
- completed_at=now

On exception:
- status="failed"
- error={code,message,retryable}
```

---

### `_send_callback(callback_url, job_id, namespace_id, source_id, status, chunks_created) -> None`

Optional webhook delivery.

Input:

```text
callback_url: str
job_id: str
namespace_id: str
source_id: str
status: str
chunks_created: int
```

Body:

```json
{
  "event": "ingest.completed",
  "job_id": "j_...",
  "namespace_id": "legea_31_1990",
  "source_id": "s_47381",
  "status": "done",
  "chunks_created": 327,
  "at": "2026-04-22T13:49:12Z"
}
```

Header:

```text
X-Vendor-Signature: sha256=<hmac>
```

Retry policy:

```text
Spec-compatible: exponential backoff up to 24h.
MVP option: document as optional / not implemented.
```

---

## 6.9 `app/services/answer.py`

Builds final query response.

### `build_citations(chunks) -> list[Citation]`

Input:

```text
chunks: list[Chunk]
```

Output:

```text
Citation list with markers [1], [2], ...
```

---

### `build_deterministic_answer(question, citations, style_hints) -> str | None`

Used when `LLM_PROVIDER=none`.

Logic:

```text
1. If citations empty: return None.
2. Use first citation or multiple citations.
3. Produce short Romanian answer using only citation content.
4. Include marker [1].
5. Respect answer_max_chars.
```

Example:

```text
Articolul 15 prevede că aporturile în numerar sunt obligatorii la constituirea oricărei forme de societate. [1].
```

---

### `compute_confidence(chunks) -> float`

Suggested logic:

```text
0.91 exact article match + strong keyword overlap
0.70 exact article match
0.50 strong keyword/vector match
0.30 weak match
0.00 no reliable match
```

No-answer threshold:

```text
if best_score < 0.30:
    answer = None
    citations = []
    confidence = 0.0
```

---

## 7. Routers

---

## 7.1 `app/routers/health.py`

### `GET /v1/health`

Unauthenticated.

### `get_health() -> HealthStatus`

Logic:

```text
1. Check ChromaDB/list collections.
2. Check LLM mode:
   - LLM_PROVIDER=none means deterministic answer generation is available.
   - If anthropic, check API key presence.
3. Check object_store:
   - local data directory or CHROMA_PERSIST_PATH is accessible.
4. Return status:
   - ok
   - degraded
   - down
```

Response code:

```text
200 for ok/degraded
503 for down
```

---

## 7.2 `app/routers/openapi.py`

### `GET /v1/openapi.json`

Purpose:

```text
Serve live OpenAPI schema.
```

Options:

```text
Return app.openapi()
or load openapi.yaml and convert to JSON.
```

Recommendation:

```text
Keep openapi.yaml at repo root.
Expose /v1/openapi.json.
Document any differences between generated schema and committed contract.
```

---

## 7.3 `app/routers/query.py`

### `POST /v1/query`

Requires authentication.

### `post_query(request, auth) -> QueryResponse`

Input:

```text
request: QueryRequest
auth: AuthContext
```

Logic:

```text
1. Start latency timer.
2. Call retrieve(auth.tenant_id, request.namespaces, request.question, request.top_k, request.hint_article_number).
3. If request.rerank=true and chunks exist: rerank.
4. If chunks empty or below threshold:
     answer=None
     citations=[]
     confidence=0.0
5. Else build citations.
6. If include_answer=false:
     answer=None
     usage=zero
7. Else generate answer.
8. Compute latency_ms.
9. Return QueryResponse.
```

Errors:

```text
400 invalid_request
401 unauthorized
403 forbidden
422 validation_error
500 internal_error
502 upstream_error
504 timeout
```

---

## 7.4 `app/routers/ingest.py`

### `POST /v1/ingest`

Requires:

```text
Authorization
X-Request-ID
X-Tenant-ID
Idempotency-Key
```

Supports:

```text
application/json for URL ingest
multipart/form-data for file ingest
```

### `post_ingest(request, idempotency_key, auth) -> IngestAcceptedResponse`

Logic:

```text
1. Compute canonical JSON body hash.
2. Check store.get_idem_job(auth.tenant_id, idempotency_key).
3. If same key + same body: return existing accepted job response.
4. If same key + different body: 409 duplicate_job.
5. Validate source_type.
6. Validate MIME allowlist.
7. Validate max file size 50 MiB for uploads.
8. Create job with status=queued.
9. Store idempotency record tenant-scoped.
10. Start background task run_ingest_job().
11. Return 202 IngestAcceptedResponse.
```

---

### `GET /v1/ingest/{job_id}`

### `get_ingest_status(job_id, auth) -> IngestJobStatus`

Logic:

```text
1. Find job by auth.tenant_id + job_id.
2. If not found: 404 not_found.
3. If non-terminal: add Retry-After header.
4. Return full job status.
```

---

## 7.5 `app/routers/namespace.py`

### `DELETE /v1/namespaces/{namespace_id}/sources/{source_id}`

Logic:

```text
1. Check source_exists(auth.tenant_id, namespace_id, source_id).
2. If not found: 404.
3. Delete source registry entry.
4. Delete Chroma chunks by chunk IDs.
5. Update stats.
6. Return 204.
```

---

### `DELETE /v1/namespaces/{namespace_id}`

Logic:

```text
1. Check namespace_exists(auth.tenant_id, namespace_id).
2. If not found: 404.
3. Create delete job.
4. Delete tenant-scoped namespace data.
5. Return { job_id, status: "queued", sla: "24h" }.
```

---

### `GET /v1/namespaces/{namespace_id}/stats`

Logic:

```text
1. Check namespace exists for tenant.
2. Return stored stats if available.
3. Otherwise compute stats from source/chunk registry.
```

---

## 8. Multipart File Ingest and MIME Validation

### URL ingest

```text
Content-Type: application/json
source_type="url"
url is required
```

### File ingest

```text
Content-Type: multipart/form-data
payload: JSON IngestRequest with source_type="file"
file: binary upload
```

FastAPI shape:

```python
async def post_ingest_file(
    payload: str = Form(...),
    file: UploadFile = File(...),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    auth: AuthContext = Depends(verify_auth),
):
    ...
```

Allowed MIME types:

```text
text/html
application/pdf
text/plain
text/markdown
```

Validation behavior:

```text
Unsupported MIME -> 415 unsupported_media_type
File > 50 MiB -> 413 payload_too_large
Invalid source_type -> 422 validation_error
source_type=url without url -> 422 validation_error
```

If multipart upload is not implemented in the MVP, state clearly:

```text
Implemented:
- JSON URL/text ingest

Out of scope for MVP:
- multipart file upload
```

---

## 9. Tenant Isolation Rule

Tenant isolation is mandatory.

Every operation touching indexed data must use:

```text
X-Tenant-ID
```

Scope all access by:

```text
tenant_id + namespace_id
```

and where applicable:

```text
tenant_id + namespace_id + source_id
tenant_id + job_id
tenant_id + idempotency_key
```

Applies to:

```text
ingest
query
job polling
idempotency
stats
delete source
delete namespace
ChromaDB collections
ChromaDB metadata filters
```

Security rules:

```text
No query searches globally by namespace_id only.
No delete operation deletes globally by namespace_id only.
No Idempotency-Key is global across tenants.
No job ID lookup ignores tenant_id.
```

---

## 10. Error Format

Universal non-2xx response shape:

```json
{
  "error": {
    "code": "<error_code>",
    "message": "<human-readable message>",
    "request_id": "<X-Request-ID or null>",
    "details": {}
  }
}
```

Supported error codes:

```text
invalid_request
unauthorized
forbidden
not_found
namespace_not_found
duplicate_job
payload_too_large
unsupported_media_type
validation_error
rate_limited
internal_error
upstream_error
service_unavailable
timeout
```

---

## 11. Tests

---

## 11.1 `tests/conftest.py`

Fixtures:

```text
app
client
auth_headers
ingest_headers
sample_query_request
sample_ingest_request
```

Example `auth_headers`:

```python
{
  "Authorization": "Bearer test-api-key",
  "X-Request-ID": "11111111-1111-4111-8111-111111111111",
  "X-Tenant-ID": "test-tenant"
}
```

---

## 11.2 `tests/test_auth.py`

Tests:

```text
test_missing_authorization_header
test_invalid_bearer_token
test_missing_x_request_id
test_invalid_x_request_id
test_missing_x_tenant_id
test_request_id_echoed_in_error
test_health_no_auth_required
```

---

## 11.3 `tests/test_ingest.py`

Tests:

```text
test_valid_ingest_returns_202
test_idempotent_same_key_same_body
test_conflict_same_key_different_body
test_idempotency_is_tenant_scoped
test_missing_idempotency_key
test_url_source_without_url_field
test_unsupported_mime_type_returns_415
test_file_too_large_returns_413
test_poll_existing_job
test_poll_nonexistent_job
test_poll_nonterminal_has_retry_after_header
```

---

## 11.4 `tests/test_query.py`

Tests:

```text
test_valid_query_returns_200
test_language_not_ro_returns_422
test_empty_namespaces_returns_422
test_top_k_over_50_returns_422
test_retrieval_only_mode
test_unknown_namespace_no_hallucination
test_response_plain_text_no_markdown
test_latency_ms_positive
test_usage_fields_present
```

---

## 11.5 `tests/test_namespace.py`

Tests:

```text
test_delete_source_returns_204
test_delete_nonexistent_source_returns_404
test_delete_namespace_returns_202
test_delete_nonexistent_namespace_returns_404
test_stats_returns_required_fields
test_stats_nonexistent_namespace_returns_404
test_cross_tenant_namespace_isolation
test_cross_tenant_delete_does_not_affect_other_tenant
```

---

## 11.6 `tests/test_domain.py`

Domain tests based on the Romanian legal cases.

### `test_exact_article_hint`

Setup:

```text
Ingest a document containing Articolul 15.
```

Request:

```json
{
  "question": "Ce spune articolul 15 din Legea 31/1990?",
  "language": "ro",
  "namespaces": ["legea_31_1990"],
  "hint_article_number": "15"
}
```

Assert:

```text
response 200
citations[0].chunk.article_number == "15"
citations[0].chunk.namespace_id == "legea_31_1990"
content contains "aporturile în numerar"
answer contains [1]
answer is plain text
answer ends with a full stop
diacritics are preserved
```

---

### `test_multi_namespace`

Request:

```json
{
  "question": "Cum se constituie o societate cu răspundere limitată și ce responsabilități au asociații?",
  "language": "ro",
  "namespaces": ["legea_31_1990", "cod_civil"]
}
```

Assert:

```text
At least one citation from legea_31_1990 if relevant fixture exists
At least one citation from cod_civil if relevant fixture exists
source_id values are preserved
diacritics are preserved
```

---

### `test_no_hallucination`

Request:

```json
{
  "question": "Care este programul primăriei Bălta Doamnei?",
  "language": "ro",
  "namespaces": ["legea_31_1990"]
}
```

Assert:

```text
response 200
answer == null
citations == []
confidence == 0.0
```

---

## 12. Local Fixtures

### `fixtures/legea_31_1990.txt`

```text
Legea 31/1990 privind societățile comerciale

Articolul 15.
Aporturile în numerar sunt obligatorii la constituirea oricărei forme de societate.

Articolul 16.
Aporturile în natură trebuie să fie evaluabile din punct de vedere economic.
```

### `fixtures/cod_civil.txt`

```text
Codul civil

Articolul 1350.
Orice persoană trebuie să își execute obligațiile pe care le-a contractat.

Articolul 1357.
Cel care cauzează altuia un prejudiciu printr-o faptă ilicită este obligat să îl repare.
```

### `fixtures/primaria_balta_doamnei.txt`

```text
Primăria Bălta Doamnei

Programul de lucru cu publicul este de luni până vineri, între orele 08:00 și 16:00.
```

---

## 13. Implementation Order

### Phase 1 — Project skeleton

```text
1. Create repository structure.
2. Add requirements.txt.
3. Add .env.example.
4. Add app/main.py.
5. Add app/config.py.
6. Add app/routers/health.py.
7. Confirm GET /v1/health works locally.
```

Expected result:

```text
uvicorn app.main:app --host 0.0.0.0 --port 8080
curl http://localhost:8080/v1/health
```

---

### Phase 2 — Models and errors

```text
1. Implement app/models.py.
2. Implement ErrorResponse models.
3. Implement app/errors.py.
4. Register exception handlers in main.py.
5. Add tests for validation and error shape.
```

Expected result:

```text
Invalid requests return {"error": {...}}
```

---

### Phase 3 — Authentication and request context

```text
1. Implement AuthContext.
2. Implement verify_auth dependency.
3. Validate Authorization bearer token.
4. Validate X-Request-ID UUID.
5. Validate X-Tenant-ID.
6. Add auth tests.
```

Expected result:

```text
Protected endpoints reject missing/invalid headers.
/v1/health remains unauthenticated.
```

---

### Phase 4 — Store layer

```text
1. Implement thread-safe store or SQLite.
2. Add tenant-scoped job storage.
3. Add tenant-scoped idempotency storage.
4. Add tenant-scoped source registry.
5. Add namespace stats registry.
6. Add delete job registry.
```

Expected result:

```text
No store function operates globally by namespace_id only.
```

---

### Phase 5 — Ingest endpoint

```text
1. Implement POST /v1/ingest.
2. Require Idempotency-Key.
3. Compute canonical body hash.
4. Implement same-key same-body behavior.
5. Implement same-key different-body 409 behavior.
6. Return IngestAcceptedResponse.
7. Implement GET /v1/ingest/{job_id}.
```

Expected result:

```text
Ingest creates a job and polling returns status.
```

---

### Phase 6 — Text extraction and chunking

```text
1. Implement URL fetch with httpx.
2. Implement MIME allowlist.
3. Implement text/html extraction.
4. Implement text/plain direct extraction.
5. Implement text/markdown direct/clean extraction.
6. Implement basic PDF extraction.
7. Implement legal article chunking.
8. Implement fallback sliding-window chunking.
```

Expected result:

```text
Text is converted into chunks with article_number where possible.
```

---

### Phase 7 — Embeddings and ChromaDB

```text
1. Add sentence-transformers.
2. Lazy-load embedding model.
3. Lazy-load ChromaDB client.
4. Use tenant-scoped Chroma collections.
5. Implement index_chunks().
6. Store metadata: tenant_id, namespace_id, source_id, article_number.
```

Expected result:

```text
Chunks are embedded and retrievable from ChromaDB.
```

---

### Phase 8 — Retrieval

```text
1. Implement retrieve().
2. Filter by tenant_id.
3. Filter by requested namespaces.
4. Search exact article candidates first.
5. Run vector search with over-fetch.
6. Add keyword fallback.
7. Merge and dedupe results.
8. Score and sort results.
```

Expected result:

```text
Article 15 query retrieves article_number == "15".
```

---

### Phase 9 — Answer generation

```text
1. Implement deterministic answer builder.
2. Implement citation builder.
3. Implement confidence calculation.
4. Implement include_answer=false behavior.
5. Implement empty-result contract.
6. Optionally add Anthropic/Claude provider.
```

Expected result:

```text
Query returns answer + citations or answer=null when unsupported.
```

---

### Phase 10 — Namespace endpoints

```text
1. Implement GET /v1/namespaces/{namespace_id}/stats.
2. Implement DELETE source.
3. Implement DELETE namespace.
4. Add tenant-isolation tests.
```

Expected result:

```text
Stats and deletes are tenant-scoped.
```

---

### Phase 11 — OpenAPI and documentation

```text
1. Add openapi.yaml at root.
2. Add /v1/openapi.json.
3. Add README.md.
4. Add DELIVERY_NOTES.md.
5. Add smoke test scripts.
```

Expected result:

```text
Contract and documentation are ready before Bitbucket access.
```

---

### Phase 12 — Docker and local package

```text
1. Add Dockerfile.
2. Add docker-compose.service.yml.
3. Build image locally.
4. Run container locally.
5. Run smoke tests against container.
```

Expected result:

```text
Service runs on port 8080 in Docker.
```

---

### Phase 13 — Tests and local tag

```text
1. Add pytest tests.
2. Add domain tests.
3. Add tenant isolation tests.
4. Run pytest.
5. Create local git commits.
6. Create local tag v0.1.0.
```

Expected result:

```text
Project is ready to push once CityDock provides the Bitbucket repository.
```

---

## 14. Smoke Test Order

```text
1. GET /v1/health
2. POST /v1/ingest for Legea 31/1990 fixture
3. GET /v1/ingest/{job_id}
4. POST /v1/query exact article 15
5. POST /v1/query out-of-domain no hallucination
6. GET /v1/namespaces/{namespace_id}/stats
7. DELETE /v1/namespaces/{namespace_id}/sources/{source_id}
8. DELETE /v1/namespaces/{namespace_id}
```

---

## 15. Local Compliance Checklist

```text
[ ] FastAPI runs on port 8080
[ ] GET /v1/health works without auth
[ ] GET /v1/openapi.json exists
[ ] openapi.yaml exists at repo root
[ ] QueryRequest schema implemented
[ ] QueryResponse schema implemented
[ ] IngestRequest schema implemented
[ ] IngestAcceptedResponse implemented
[ ] IngestJobStatus implemented
[ ] ErrorResponse shape implemented
[ ] Authorization bearer token validated
[ ] X-Request-ID validated and echoed
[ ] X-Tenant-ID required
[ ] Idempotency-Key required on ingest
[ ] Idempotency is tenant-scoped
[ ] Same key + same body returns same job
[ ] Same key + different body returns 409
[ ] URL ingest works
[ ] MIME allowlist exists
[ ] File size limit exists if multipart implemented
[ ] Text extraction works
[ ] Legal article chunking works
[ ] Embeddings generated
[ ] ChromaDB stores tenant-scoped chunks
[ ] Retrieval filters by tenant
[ ] Retrieval filters by namespace
[ ] hint_article_number exact match works
[ ] Citations use [1], [2] markers
[ ] Answer is plain Romanian text
[ ] include_answer=false returns citations only
[ ] Empty result returns answer=null, citations=[], confidence=0.0
[ ] Namespace stats work
[ ] Delete source works
[ ] Delete namespace works
[ ] Cross-tenant isolation tests pass
[ ] Dockerfile builds
[ ] docker-compose.service.yml runs locally
[ ] README exists
[ ] DELIVERY_NOTES.md exists
[ ] Smoke tests pass locally
```

---

## 16. Final Notes

The strongest technical signal in this implementation is not the number of DevOps files. It is the correctness of the RAG behavior:

```text
exact article retrieval
correct citations
tenant isolation
no hallucination
plain Romanian answer format
```

The project should be ready to push to the CityDock Bitbucket repository once access is granted, but the official deployment flow cannot be completed without their repository and runner.

