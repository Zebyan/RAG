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
- document extraction;
- legal chunking;
- embeddings;
- Qdrant vector indexing/search;
- hybrid retrieval;
- deterministic answer generation;
- error handling;
- tenant isolation;
- Docker/Compose behavior;
- testing strategy;
- current limitations and extension points.

---

## 1. Service purpose

The service implements a local Retrieval-Augmented Generation API for Romanian legal documents.

The service can:

1. receive legal source documents;
2. extract text from supported inputs;
3. split the legal text into meaningful legal chunks;
4. generate embeddings locally;
5. store chunks in SQLite;
6. store vectors in Qdrant;
7. retrieve relevant chunks for a user question;
8. generate a grounded answer using retrieved citations;
9. avoid hallucinated answers when no relevant context exists.

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

## 3. Project structure

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
│   │   ├── ingest.py
│   │   ├── query.py
│   │   ├── namespaces.py
│   │   └── openapi.py
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

## 4. Runtime configuration

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

### Local execution

When running Python directly on the host:

```env
QDRANT_URL=http://localhost:6333
DATABASE_PATH=./data/app.db
```

### Docker Compose execution

When running API inside Docker Compose:

```env
QDRANT_URL=http://qdrant:6333
DATABASE_PATH=/app/data/app.db
```

Reason:

- from the host, Qdrant is reachable through `localhost`;
- from the API container, Qdrant is reachable by Docker service name `qdrant`.

---

## 5. Application startup

The FastAPI application is created in `app/main.py`.

Typical startup responsibilities:

```text
create FastAPI app
→ register middleware
→ register exception handlers
→ include routers
→ initialize SQLite database
```

### Middleware behavior

The response header middleware performs:

```text
incoming request
→ read X-Request-ID if present
→ read or create X-Vendor-Trace-ID
→ call route handler
→ measure duration
→ add response headers
```

Response headers added:

```text
X-Request-ID
X-Vendor-Trace-ID
Server-Timing
```

For query responses, the query route additionally adds:

```text
X-Vendor-Retrieval-Strategy
```

Example:

```text
X-Request-ID: 11111111-1111-4111-8111-111111111111
X-Vendor-Trace-ID: tr_ddeea83d9b8843f28a2f35fa322fba2f
X-Vendor-Retrieval-Strategy: hybrid_qdrant_article_keyword
Server-Timing: app;dur=21.34
```

---

## 6. Authentication and request context

Implemented in `app/auth.py`.

Most endpoints require:

```text
Authorization: Bearer test-api-key
X-Request-ID: <uuid>
X-Tenant-ID: <tenant-id>
```

The auth dependency returns an internal context object similar to:

```python
AuthContext(
    request_id="11111111-1111-4111-8111-111111111111",
    tenant_id="test-tenant",
)
```

This context is passed to service functions so all data access is tenant-scoped.

### Why tenant scoping matters

Every persisted object is associated with a tenant:

```text
job
idempotency record
source
chunk
vector point
namespace stats
```

Vector search also filters by tenant:

```text
tenant_id == X-Tenant-ID
```

This prevents a user from retrieving another tenant's data.

---

## 7. API endpoint overview

### Public endpoint

```text
GET /v1/health
```

No authentication required.

### Authenticated endpoints

```text
POST   /v1/ingest
GET    /v1/ingest/{job_id}
POST   /v1/query
GET    /v1/namespaces/{namespace_id}/stats
DELETE /v1/namespaces/{namespace_id}/sources/{source_id}
DELETE /v1/namespaces/{namespace_id}
GET    /v1/openapi.json
```

---

## 8. Health endpoint

### Endpoint

```text
GET /v1/health
```

### Function chain

```text
routes/health.py
→ health route handler
→ checks configured dependency status
→ returns HealthResponse
```

### Example request

```powershell
curl.exe http://localhost:8080/v1/health
```

### Example response

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

### Notes

- `vector_store` should be `ok` when Qdrant is reachable.
- `llm` is `ok` because the default provider is `none`; no external LLM is required.
- `object_store` is `ok` as a local MVP placeholder.

---

## 9. Ingest endpoint

### Endpoint

```text
POST /v1/ingest
```

### Supported content types

```text
application/json
multipart/form-data
application/x-www-form-urlencoded for validation fallback
```

### Required headers

```text
Authorization: Bearer test-api-key
X-Request-ID: <uuid>
X-Tenant-ID: <tenant-id>
Idempotency-Key: <uuid>
```

---

## 10. JSON ingest flow

JSON ingest supports:

1. inline deterministic fixture text through `metadata.text`;
2. URL fetching if `metadata.text` is absent and `source_type=url`.

### Function chain

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

### Request with `metadata.text`

```json
{
  "namespace_id": "legea_31_1990",
  "source_id": "s_47381",
  "source_type": "url",
  "url": "https://legislatie.just.ro/Public/DetaliiDocument/47381",
  "mime_type_hint": "text/plain",
  "metadata": {
    "source_title": "Legea 31/1990 privind societățile comerciale",
    "text": "Articolul 15. Aporturile în numerar sunt obligatorii la constituirea oricărei forme de societate."
  }
}
```

### Curl request

```powershell
curl.exe -X POST http://localhost:8080/v1/ingest `
  -H "Authorization: Bearer test-api-key" `
  -H "Content-Type: application/json" `
  -H "X-Request-ID: 22222222-2222-4222-8222-222222222222" `
  -H "X-Tenant-ID: ph-balta-doamnei" `
  -H "Idempotency-Key: 99999999-9999-4999-8999-999999999999" `
  --data-binary "@examples/ingest.json"
```

### Response

```json
{
  "job_id": "j_3f7a883ddd44",
  "status": "queued",
  "submitted_at": "2026-04-26T18:20:36Z",
  "estimated_completion_at": "2026-04-26T18:25:36Z"
}
```

### Important behavior

The API returns `queued` for contract compatibility, but the MVP processes synchronously. Polling the returned job should show `done`.

---

## 11. Ingest job polling

### Endpoint

```text
GET /v1/ingest/{job_id}
```

### Function chain

```text
GET /v1/ingest/{job_id}
→ routes/ingest.py::get_ingest_status()
→ ingest_service.get_ingest_job_status()
→ sqlite_store.get_job()
→ returns IngestJobStatus
```

### Curl request

```powershell
curl.exe -X GET http://localhost:8080/v1/ingest/j_3f7a883ddd44 `
  -H "Authorization: Bearer test-api-key" `
  -H "X-Request-ID: 33333333-3333-4333-8333-333333333333" `
  -H "X-Tenant-ID: ph-balta-doamnei"
```

### Response when complete

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

### Response when failed

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
    "code": "INGEST_FAILED",
    "message": "Unsupported MIME type: application/json"
  }
}
```

---

## 12. Idempotency behavior

Idempotency is tenant-scoped.

### Function chain

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
           raise 409 duplicate/idempotency error
```

### Same key + same body

Returns the same job metadata.

### Same key + different body

Returns an error response.

Example:

```json
{
  "error": {
    "code": "duplicate_job",
    "message": "Idempotency-Key reused with different body.",
    "request_id": "11111111-1111-4111-8111-111111111111",
    "details": null
  }
}
```

---

## 13. URL ingest

URL ingest is used when:

```text
source_type=url
metadata.text is absent
url is present
```

### Function chain

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

### Supported MIME types

```text
text/plain
text/markdown
text/html
application/pdf
```

### Example request

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

### Curl

```powershell
curl.exe -X POST http://localhost:8080/v1/ingest `
  -H "Authorization: Bearer test-api-key" `
  -H "Content-Type: application/json" `
  -H "X-Request-ID: 66666666-6666-4666-8666-666666666666" `
  -H "X-Tenant-ID: ph-balta-doamnei" `
  -H "Idempotency-Key: 66666666-6666-4666-8666-666666666667" `
  --data-binary "@examples/ingest_url.json"
```

### Internal URL fetch response object

`fetch_url_document()` returns an object like:

```python
FetchedUrlDocument(
    url="https://example.com/legal.txt",
    status_code=200,
    extracted=ExtractedDocument(
        text="Articolul 15. ...",
        mime_type="text/plain",
        metadata={"original_size_bytes": 123}
    ),
    headers={...},
    metadata={
        "fetched_url": "https://example.com/legal.txt",
        "http_status_code": 200,
        "content_type": "text/plain; charset=utf-8",
        "effective_mime_type": "text/plain"
    }
)
```

This metadata is copied into chunk metadata.

---

## 14. Multipart file ingest

Multipart ingest is used for direct uploaded documents.

### Endpoint

```text
POST /v1/ingest
Content-Type: multipart/form-data
```

### Form parts

```text
payload: JSON string
file: binary uploaded document
```

### Function chain

```text
routes/ingest.py::post_ingest()
→ _parse_ingest_request()
→ await http_request.form()
→ read form["payload"]
→ read form["file"]
→ IngestRequest.model_validate(payload)
→ uploaded_file.read()
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

### Payload example

`examples/file_payload.json`:

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

`examples/legea_31.txt`:

```text
Articolul 15.
Aporturile în numerar sunt obligatorii la constituirea oricărei forme de societate.
```

### Curl

```powershell
curl.exe -X POST http://localhost:8080/v1/ingest `
  -H "Authorization: Bearer test-api-key" `
  -H "X-Request-ID: 77777777-7777-4777-8777-777777777777" `
  -H "X-Tenant-ID: ph-balta-doamnei" `
  -H "Idempotency-Key: 77777777-7777-4777-8777-777777777778" `
  -F "payload=<examples/file_payload.json;type=application/json" `
  -F "file=@examples/legea_31.txt;type=text/plain"
```

### Expected response

```json
{
  "job_id": "j_...",
  "status": "queued",
  "submitted_at": "...",
  "estimated_completion_at": "..."
}
```

### Uploaded file metadata stored

```json
{
  "text_source": "uploaded_file",
  "uploaded_filename": "legea_31.txt",
  "uploaded_file_sha256": "...",
  "uploaded_file_size_bytes": 97,
  "effective_mime_type": "text/plain"
}
```

---

## 15. Document extraction

Implemented in:

```text
app/services/document_extractor.py
```

### Main function

```python
extract_document_text(
    content: bytes,
    mime_type: str | None,
) -> ExtractedDocument
```

### Function chain

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

### Response object

```python
ExtractedDocument(
    text="Articolul 15. ...",
    mime_type="text/plain",
    metadata={
        "original_size_bytes": 123
    }
)
```

For PDFs:

```python
ExtractedDocument(
    text="[Page 1]\nArticolul 15. ...",
    mime_type="application/pdf",
    metadata={
        "original_size_bytes": 100000,
        "page_count": 4
    }
)
```

### HTML extraction behavior

The HTML extractor removes:

```text
script
style
noscript
template
svg
canvas
nav
footer
header
```

Then it extracts visible text with line separators.

### Unsupported MIME example

If the MIME is `application/json`, extraction raises:

```python
DocumentExtractionError("Unsupported MIME type: application/json")
```

The ingest job becomes `failed`.

---

## 16. Legal chunking

Implemented in:

```text
app/services/legal_chunker.py
```

### Main function

```python
chunk_legal_text(text: str) -> list[LegalChunk]
```

### Supported legal structures

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

### Output chunk object

A chunk contains:

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

### Why article-aware chunking is important

Legal questions often refer to article numbers:

```text
Ce spune articolul 15?
```

If chunking loses article numbers, retrieval becomes unreliable.

The chunker preserves article metadata so retrieval can boost exact matches.

---

## 17. Embedding generation

Implemented in:

```text
app/services/embedding_service.py
```

### Main functions

```python
embed_text(text: str) -> list[float]

embed_texts(texts: list[str]) -> list[list[float]]
```

### Function chain

```text
embed_texts()
→ get_embedding_model()
→ SentenceTransformer(settings.embedding_model)
→ model.encode(texts)
→ convert vectors to list[float]
```

### Default model

```text
paraphrase-multilingual-MiniLM-L12-v2
```

### Embedding dimension

```text
384
```

### Why local embeddings are used

Local embeddings avoid sending Romanian legal documents and user questions to third-party embedding APIs.

Tradeoff:

```text
better privacy and data locality
but larger Docker image due to sentence-transformers / PyTorch
```

---

## 18. Qdrant vector store

Implemented in:

```text
app/services/vector_store.py
```

### Main responsibilities

```text
create collection
upsert vectors
search vectors
delete by source
delete by namespace
```

### Collection

Default collection:

```text
rag_chunks
```

### Vector upsert chain

```text
_index_chunks_in_vector_store()
→ embed_texts([chunk.content])
→ vector_store.upsert_chunks(tenant_id, chunks, vectors)
→ ensure_collection()
→ Qdrant upsert(points)
```

### Point payload

Each vector point includes payload:

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

### Vector search chain

```text
retrieval_service.retrieve_chunks()
→ embed_text(question)
→ vector_store.search_chunks(
      tenant_id,
      namespaces,
      query_vector,
      limit
  )
→ Qdrant search with filters:
      tenant_id == request tenant
      namespace_id in request namespaces
→ convert results to chunk dicts
```

### Tenant isolation in Qdrant

Qdrant search always applies tenant filter:

```text
tenant_id == X-Tenant-ID
```

and namespace filter:

```text
namespace_id in request.namespaces
```

This prevents cross-tenant vector leakage.

---

## 19. Hybrid retrieval

Implemented in:

```text
app/services/retrieval_service.py
```

### Main function

```python
retrieve_chunks(
    tenant_id: str,
    namespaces: list[str],
    question: str,
    top_k: int,
    hint_article_number: str | None,
) -> list[dict]
```

### Retrieval chain

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

### Retrieval strategy response value

When Qdrant is active:

```text
hybrid_qdrant_article_keyword
```

When fallback lexical mode is active:

```text
article_keyword_mvp
```

### Exact article boost

If request has:

```json
"hint_article_number": "15"
```

then chunks with:

```json
"article_number": "15"
```

receive priority.

This matters because legal references must be exact.

---

## 20. Query endpoint

### Endpoint

```text
POST /v1/query
```

### Function chain

```text
routes/query.py::post_query()
→ verify_auth()
→ retrieval_service.retrieve_chunks()
→ answer_service.build_answer_response()
→ create QueryResponse
→ set X-Vendor-Retrieval-Strategy header
→ return response
```

### Request

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

### Curl

```powershell
curl.exe -X POST http://localhost:8080/v1/query `
  -H "Authorization: Bearer test-api-key" `
  -H "Content-Type: application/json" `
  -H "X-Request-ID: 11111111-1111-4111-8111-111111111111" `
  -H "X-Tenant-ID: ph-balta-doamnei" `
  --data-binary "@examples/query.json"
```

### Response

```json
{
  "request_id": "11111111-1111-4111-8111-111111111111",
  "answer": "Articolul 15 prevede următoarele: Articolul 15. Aporturile în numerar sunt obligatorii la constituirea oricărei forme de societate. [1].",
  "citations": [
    {
      "marker": "[1]",
      "chunk": {
        "chunk_id": "6ffc18dc-153e-485a-9573-9471d4c4a1e5",
        "content": "Articolul 15. Aporturile în numerar sunt obligatorii la constituirea oricărei forme de societate.",
        "article_number": "15",
        "section_title": null,
        "point_number": null,
        "page_number": null,
        "source_id": "s_47381",
        "source_url": "https://legislatie.just.ro/Public/DetaliiDocument/47381",
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

## 21. Deterministic answer generation

Implemented in:

```text
app/services/answer_service.py
```

### Main function

```python
build_answer_response(
    include_answer: bool,
    question: str,
    chunks: list[dict],
    style_hints: Any | None,
) -> tuple[str | None, list[dict], float]
```

### Function behavior

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

### Why deterministic answers

The legal domain requires grounded responses.

The deterministic answer service only uses retrieved chunk content and citation markers.

This reduces hallucination risk compared to an unconstrained LLM response.

---

## 22. No-answer behavior

If retrieval finds no relevant chunks, response is:

```json
{
  "answer": null,
  "citations": [],
  "confidence": 0.0
}
```

This is the intended anti-hallucination behavior.

Example use case:

```text
Question: Care este programul primăriei Bălta Doamnei?
Namespace: legea_31_1990
```

The legal namespace does not contain town hall schedule data, so the service should not invent an answer.

---

## 23. Namespace stats endpoint

### Endpoint

```text
GET /v1/namespaces/{namespace_id}/stats
```

### Function chain

```text
routes/namespaces.py
→ namespace_service.get_namespace_stats()
→ sqlite_store.get_namespace_stats()
→ return NamespaceStatsResponse
```

### Curl

```powershell
curl.exe -X GET http://localhost:8080/v1/namespaces/legea_31_1990/stats `
  -H "Authorization: Bearer test-api-key" `
  -H "X-Request-ID: 99999999-9999-4999-8999-999999999999" `
  -H "X-Tenant-ID: ph-balta-doamnei"
```

### Response

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

## 24. Source deletion

### Endpoint

```text
DELETE /v1/namespaces/{namespace_id}/sources/{source_id}
```

### Function chain

```text
routes/namespaces.py
→ namespace_service.delete_source()
→ sqlite_store.delete_source()
→ vector_store.delete_source()
→ return 204
```

### Qdrant deletion filter

```text
tenant_id == tenant
namespace_id == namespace_id
source_id == source_id
```

### Curl

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

After deletion, querying the same namespace/source content should return no answer.

---

## 25. Namespace deletion

### Endpoint

```text
DELETE /v1/namespaces/{namespace_id}
```

### Function chain

```text
routes/namespaces.py
→ namespace_service.delete_namespace()
→ sqlite_store.delete_namespace()
→ vector_store.delete_namespace()
→ return deletion response
```

### Qdrant deletion filter

```text
tenant_id == tenant
namespace_id == namespace_id
```

### Curl

```powershell
curl.exe -X DELETE http://localhost:8080/v1/namespaces/legea_31_1990 `
  -H "Authorization: Bearer test-api-key" `
  -H "X-Request-ID: bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb" `
  -H "X-Tenant-ID: ph-balta-doamnei"
```

### Response shape

```json
{
  "job_id": "j_...",
  "status": "done",
  "namespace_id": "legea_31_1990"
}
```

---

## 26. Error responses

### Validation error envelope

FastAPI validation errors are wrapped into:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
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

### Multipart validation error

Missing `file`:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
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

### Unsupported MIME

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

## 27. OpenAPI

Static contract file:

```text
openapi.yaml
```

Runtime schema:

```text
GET /v1/openapi.json
```

Generate snapshot:

```powershell
curl.exe http://localhost:8080/v1/openapi.json -o generated-openapi.local.json
```

This generated file is a local debug artifact and should not be committed.

---

## 28. Dockerfile behavior

The Dockerfile uses a multi-stage build.

### Builder stage

```text
FROM python:3.12-slim AS builder
→ copy requirements.txt
→ build wheels
```

### Runtime stage

```text
FROM python:3.12-slim AS runtime
→ create non-root appuser
→ install wheels
→ copy app
→ expose 8080
→ healthcheck /v1/health
→ run uvicorn
```

### CPU-only torch

The requirements pin CPU-only PyTorch so CUDA/NVIDIA packages are not pulled.

Expected check:

```powershell
docker run --rm citydock-rag-mvp:cpu python -c "import torch; print(torch.cuda.is_available())"
```

Expected:

```text
False
```

---

## 29. Docker Compose files

### docker-compose.local.yml

Used for local development.

Usually includes:

```text
rag-service
qdrant
```

The API is accessible at:

```text
http://localhost:8080
```

Qdrant is accessible from host at:

```text
http://localhost:6333
```

Inside the API container:

```text
http://qdrant:6333
```

### docker-compose.service.yml

Deployment fragment for the target stack.

It defines the RAG API service only and joins external network:

```text
lex-advisor
```

It does not bind host ports.

Validate:

```powershell
docker compose -f docker-compose.service.yml config
```

---

## 30. Testing strategy

The project contains automated tests for:

```text
auth
health
validation errors
response headers
document extraction
URL fetching
multipart file upload
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
no-hallucination behavior
```

Run all tests:

```powershell
pytest
```

Run smoke tests:

```powershell
python smoke_endpoints.py
```

Run Docker smoke tests:

```powershell
docker compose -f docker-compose.local.yml up --build
python smoke_endpoints.py http://localhost:8080 test-api-key docker-compose-test-tenant
```

---

## 31. Smoke test script behavior

`smoke_endpoints.py` validates the main API behavior:

```text
1. GET /v1/health
2. POST /v1/ingest
3. GET /v1/ingest/{job_id}
4. POST /v1/query for article 15
5. POST /v1/query for article 16
6. POST /v1/query empty/no-answer behavior
7. GET namespace stats
8. cross-tenant isolation
9. DELETE source
10. verify source deletion
11. GET /v1/openapi.json
```

Expected final output:

```text
ALL ENDPOINT SMOKE TESTS PASSED
```

---

## 32. External LLM extension point

External LLM generation is not active by default.

Current setting:

```env
LLM_PROVIDER=none
```

### Current answer flow

```text
retrieved chunks
→ citations
→ deterministic answer
```

### Future LLM flow

```text
retrieved chunks
→ build grounded prompt
→ call LLM provider
→ return generated answer
→ preserve citations
→ fallback to deterministic answer on failure
```

### Why default is no external LLM

Reasons:

```text
legal data privacy
no external API key requirement
no third-party data transfer
deterministic citation-grounded behavior
lower hallucination risk
```

---

## 33. Data privacy and isolation

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

## 34. Final local verification checklist

Before sending repository for review:

```powershell
pytest
python smoke_endpoints.py
docker compose -f docker-compose.service.yml config
git status
```

Check that these are not committed:

```text
.env
.venv/
data/app.db
.pytest_cache/
generated-openapi.local.json
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

## 35. Current known limitations

The following are not active locally:

```text
external LLM generation
Prometheus /metrics
OpenTelemetry
official Bitbucket CI
official Artifact Registry push
official deployment
official evaluation suite
```

The service is ready for local functional review with the documented limitations.
