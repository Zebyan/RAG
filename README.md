# CityDock / Lex-Advisor RAG Service

FastAPI-based implementation of a Romanian legal-domain RAG service aligned with the main CityDock `/v1` API contract surface.

The project currently provides a local implementation with:

- authenticated `/v1` endpoints;
- tenant isolation;
- idempotent ingest;
- persistent SQLite storage;
- article-aware legal chunking;
- Qdrant vector database support;
- local embeddings with `sentence-transformers`;
- hybrid retrieval;
- citation-grounded deterministic answers;
- no-hallucination fallback behavior;
- namespace lifecycle operations;
- endpoint smoke tests;
- automated test coverage.

Current test status:

```text
39 passed
```

---

## 1. Current Implementation Status

Implemented and tested locally:

- FastAPI service.
- `/v1` API surface.
- Pydantic request/response models.
- Bearer API-key validation.
- `X-Request-ID` validation.
- `X-Tenant-ID` tenant scoping.
- Tenant-scoped `Idempotency-Key` handling for `POST /v1/ingest`.
- Tenant + namespace isolation.
- Persistent SQLite storage.
- Ingest flow with job status.
- Synchronous MVP ingest processing.
- Article-aware legal chunking.
- Section/chapter metadata extraction.
- Paragraph and point metadata extraction.
- Long article splitting.
- Qdrant vector database through Docker.
- Local embeddings with `sentence-transformers`.
- Vector indexing during ingest.
- Vector search during query.
- Hybrid retrieval:
  - exact article-number boost;
  - Qdrant vector search;
  - lexical keyword scoring;
  - phrase matching;
  - diacritic-normalized scoring;
  - rough Romanian word-form matching;
  - namespace diversity.
- Citation-based deterministic answers.
- Empty-result anti-hallucination contract.
- Namespace stats.
- Source deletion.
- Namespace deletion.
- Qdrant vector cleanup on source/namespace deletion.
- Cross-tenant isolation tests.
- Multi-namespace retrieval tests.
- Vector-store integration tests.
- Hybrid query tests.
- `/v1/openapi.json`.
- Local fixtures.
- Python endpoint smoke test.
- Automated test suite passing.

---

## 2. Current Limitations

Not implemented yet:

- External LLM answer generation.
- Real URL fetching.
- HTML extraction.
- PDF extraction.
- Multipart file upload.
- Prometheus `/metrics`.
- OpenTelemetry.
- Standardized wrapping for FastAPI `422` validation errors.
- Full response header contract:
  - `X-Request-ID`;
  - `X-Vendor-Trace-ID`;
  - `X-Vendor-Retrieval-Strategy`;
  - `Server-Timing`.
- Fully aligned `openapi.yaml`.
- Verified production Docker image build.
- Verified full local Docker Compose stack.
- Bitbucket CI.
- Trivy scan.
- Production deployment.

Current answer generation is deterministic and citation-based. No external LLM is called by default.

Current retrieval strategy:

```text
tenant + namespace filter
→ exact article-number matching
→ Qdrant vector search
→ lexical keyword matching
→ phrase matching
→ diacritic-normalized scoring
→ rough Romanian word-form matching
→ namespace diversity
→ citation-based deterministic answer
```

Planned optional LLM generation:

```text
tenant + namespace filter
→ exact article candidates
→ vector candidates
→ lexical candidates
→ merge + rerank
→ prompt LLM with retrieved chunks only
→ validate/attach citations
→ return grounded answer
```

---

## 3. Architecture

```text
Client
  |
  | HTTP /v1 request
  v
FastAPI routes
  |
  +--> auth.py
  |      - Authorization validation
  |      - X-Request-ID validation
  |      - X-Tenant-ID scoping
  |
  +--> models.py
  |      - Pydantic request/response models
  |
  +--> services/
         |
         +--> ingest_service.py
         |      - validates ingest request
         |      - enforces idempotency
         |      - chunks legal text
         |      - stores jobs/sources/chunks in SQLite
         |      - generates embeddings
         |      - indexes vectors into Qdrant
         |
         +--> legal_chunker.py
         |      - article-aware chunking
         |      - section/chapter metadata
         |      - paragraph and point metadata
         |      - long article splitting
         |
         +--> embedding_service.py
         |      - loads sentence-transformers model
         |      - converts text into 384-dimensional vectors
         |
         +--> vector_store.py
         |      - creates Qdrant collection
         |      - upserts chunk vectors
         |      - searches vectors with tenant + namespace filters
         |      - deletes vectors by source/namespace
         |
         +--> retrieval_service.py
         |      - combines SQLite lexical candidates
         |      - combines Qdrant vector candidates
         |      - boosts exact article matches
         |      - reranks hybrid results
         |
         +--> answer_service.py
         |      - builds deterministic Romanian answer
         |      - attaches [1], [2] citations
         |      - returns null answer on empty result
         |
         +--> namespace_service.py
         |      - namespace stats
         |      - source deletion
         |      - namespace deletion
         |
         +--> sqlite_store.py
                - persistent jobs
                - idempotency records
                - source registry
                - chunk metadata
                - namespace stats

External local services:
  |
  +--> SQLite
  |      - ./data/app.db
  |
  +--> Qdrant Docker container
         - http://localhost:6333
         - collection: rag_chunks
```

---

## 4. Project Structure

```text
citydock-rag-mvp/
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
│       ├── embedding_service.py
│       ├── ingest_service.py
│       ├── legal_chunker.py
│       ├── namespace_service.py
│       ├── retrieval_service.py
│       ├── sqlite_store.py
│       ├── store.py
│       └── vector_store.py
├── fixtures/
├── tests/
├── docs/
├── scripts/
├── data/
├── requirements.txt
├── Dockerfile
├── docker-compose.local.yml
├── docker-compose.service.yml
├── openapi.yaml
├── .env.example
├── DELIVERY_NOTES.md
├── pytest.ini
├── smoke_endpoints.py
└── README.md
```

---

## 5. Core Workflows

### 5.1 Health

```text
GET /v1/health
→ returns service status, version, uptime, dependencies
```

No authentication required.

---

### 5.2 Ingest

```text
POST /v1/ingest
→ validate headers
→ validate Idempotency-Key
→ check idempotency body hash
→ create ingest job
→ read source text
→ chunk legal text by article/section/paragraph
→ store chunks in SQLite
→ generate embeddings with sentence-transformers
→ upsert vectors and payloads into Qdrant
→ update namespace stats
→ mark job as done
→ return 202 accepted response
```

Current ingest is synchronous internally, but exposed through a job-status API.

---

### 5.3 Query

```text
POST /v1/query
→ validate headers
→ embed user question
→ retrieve vector candidates from Qdrant
→ retrieve lexical/article candidates from SQLite
→ merge candidates
→ rerank hybrid results
→ apply no-answer threshold
→ build citations
→ build deterministic answer
→ return QueryResponse
```

If no relevant chunks are found:

```json
{
  "answer": null,
  "citations": [],
  "confidence": 0.0
}
```

---

### 5.4 Namespace Stats

```text
GET /v1/namespaces/{namespace_id}/stats
→ verify namespace exists for tenant
→ return chunk/source/token stats
```

---

### 5.5 Delete Source

```text
DELETE /v1/namespaces/{namespace_id}/sources/{source_id}
→ delete source chunks from SQLite
→ delete source vectors from Qdrant
→ return 204
```

---

### 5.6 Delete Namespace

```text
DELETE /v1/namespaces/{namespace_id}
→ delete all namespace data from SQLite
→ delete all namespace vectors from Qdrant
→ return deletion job response
```

---

## 6. Requirements

Recommended Python version:

```text
Python 3.12.x
```

Required local tools:

```text
Python 3.12
Docker Desktop
PowerShell or terminal
```

Install Python dependencies:

```powershell
pip install -r requirements.txt
```

Qdrant runs through Docker and is required for vector tests and hybrid retrieval.

---

## 7. Environment Variables

Example `.env`:

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

LLM_PROVIDER=none
```

| Variable | Description | Default |
|---|---|---|
| `APP_NAME` | Service name | `citydock-rag-mvp` |
| `APP_VERSION` | Service version | `0.1.0` |
| `RAG_API_KEY` | Bearer token used by local auth | `test-api-key` |
| `DATABASE_PATH` | SQLite database path | `./data/app.db` |
| `VECTOR_STORE` | Vector backend selector | `qdrant` |
| `QDRANT_URL` | Qdrant HTTP URL | `http://localhost:6333` |
| `QDRANT_COLLECTION` | Qdrant collection name | `rag_chunks` |
| `EMBEDDING_MODEL` | Sentence-transformers model | `paraphrase-multilingual-MiniLM-L12-v2` |
| `EMBEDDING_DIM` | Embedding dimension | `384` |
| `LLM_PROVIDER` | LLM provider selector | `none` |

---

## 8. Run Locally

### 8.1 Create virtual environment

```powershell
python -m venv .venv
```

Activate:

```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Create `.env`:

```powershell
copy .env.example .env
```

---

### 8.2 Start Qdrant

```powershell
docker compose -f docker-compose.local.yml up qdrant
```

Verify Qdrant:

```powershell
curl.exe http://localhost:6333/collections
```

Expected:

```json
{
  "result": {
    "collections": []
  },
  "status": "ok",
  "time": 0.000014307
}
```

If the `rag_chunks` collection already exists, it may appear in the collections list.

---

### 8.3 Start API server

In another terminal:

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

Health check:

```powershell
curl.exe http://localhost:8080/v1/health
```

Expected:

```json
{
  "status": "ok",
  "version": "0.1.0",
  "uptime_seconds": 123,
  "dependencies": {
    "vector_store": "ok",
    "llm": "ok",
    "object_store": "ok"
  }
}
```

---

## 9. Run Tests

Make sure Qdrant is running:

```powershell
curl.exe http://localhost:6333/collections
```

Then run:

```powershell
pytest
```

Expected:

```text
39 passed
```

The test suite currently covers:

- health endpoint;
- auth validation;
- missing auth errors;
- ingest;
- idempotency same body;
- idempotency conflict;
- ingest polling;
- unsupported MIME;
- article-aware chunking;
- legal metadata chunking;
- long article splitting;
- exact article retrieval;
- retrieval without article hint;
- diacritic normalization;
- diacritics preserved in citation content;
- no-hallucination wrong namespace;
- namespace stats;
- source deletion;
- namespace deletion;
- SQLite persistence behavior;
- embedding service;
- Qdrant collection creation;
- Qdrant vector upsert/search;
- Qdrant tenant isolation;
- Qdrant source deletion;
- Qdrant namespace deletion;
- ingest vector indexing;
- Qdrant cleanup on delete;
- hybrid query retrieval;
- exact article priority under hybrid retrieval;
- cross-tenant isolation under hybrid retrieval;
- validation errors.

---

## 10. Endpoint Smoke Tests

Run the Python smoke test while both Qdrant and the API server are running:

```powershell
python smoke_endpoints.py
```

Optional explicit parameters:

```powershell
python smoke_endpoints.py http://localhost:8080 test-api-key endpoint-test-tenant
```

Expected final output:

```text
ALL ENDPOINT SMOKE TESTS PASSED
```

The smoke test checks:

```text
/v1/health
/v1/ingest
/v1/ingest/{job_id}
/v1/query article 15
/v1/query article 16
empty result / no hallucination
namespace stats
cross-tenant isolation
delete source
/v1/openapi.json
```

After hybrid retrieval is enabled, query responses should show:

```json
"retrieval_strategy": "hybrid_qdrant_article_keyword"
```

---

## 11. Manual API Examples

### 11.1 Ingest

Create `ingest.json`:

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
  --data-binary "@ingest.json"
```

Expected:

```json
{
  "job_id": "j_...",
  "status": "queued",
  "submitted_at": "...",
  "estimated_completion_at": "..."
}
```

---

### 11.2 Query Article 15

Create `query.json`:

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
  --data-binary "@query.json"
```

Expected:

```json
{
  "answer": "Articolul 15 prevede ... [1].",
  "citations": [
    {
      "marker": "[1]",
      "chunk": {
        "article_number": "15",
        "namespace_id": "legea_31_1990"
      }
    }
  ],
  "retrieval_strategy": "hybrid_qdrant_article_keyword",
  "confidence": 0.7
}
```

---

### 11.3 Empty Result

Create `query_empty.json`:

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
  --data-binary "@query_empty.json"
```

Expected:

```json
{
  "answer": null,
  "citations": [],
  "confidence": 0.0
}
```

---

## 12. Docker

Docker files are present, but the final production-style Docker build still needs verification.

Build:

```powershell
docker build -t citydock-rag-mvp:0.1.0 .
```

Run:

```powershell
docker run --rm -p 8080:8080 --env-file .env citydock-rag-mvp:0.1.0
```

Health:

```powershell
curl.exe http://localhost:8080/v1/health
```

Notes:

- The local API container must be able to reach Qdrant.
- In Docker Compose, the app should use `QDRANT_URL=http://qdrant:6333`.
- When running the app directly on the host, use `QDRANT_URL=http://localhost:6333`.

---

## 13. Docker Compose

### 13.1 Local Compose

```powershell
docker compose -f docker-compose.local.yml up --build
```

Then test:

```powershell
curl.exe http://localhost:8080/v1/health
```

Expected:

```json
{
  "status": "ok"
}
```

---

### 13.2 Service Compose

Validate the service compose file:

```powershell
docker compose -f docker-compose.service.yml config
```

The service compose file is intended for CityDock's external stack and should:

- expose port `8080` only to the Docker network;
- avoid host port binding;
- use env vars for configuration;
- join the external `lex-advisor` network;
- use mounted volumes for persistence if required.

---

## 14. OpenAPI

The running service exposes:

```text
GET /v1/openapi.json
```

The repo also contains:

```text
openapi.yaml
```

Current status:

- `/v1/openapi.json` exposes the generated FastAPI schema.
- `openapi.yaml` still needs final alignment with the official provided contract.
- Strict byte-level contract reconciliation remains a handoff task before final delivery.

---

## 15. Retrieval Design

The current retrieval is hybrid.

### 15.1 Exact Article Retrieval

If `hint_article_number` is provided, chunks with the same `article_number` receive the strongest boost.

This protects legal accuracy for questions like:

```text
Ce spune articolul 15 din Legea 31/1990?
```

### 15.2 Vector Retrieval

The user question is embedded with the same `sentence-transformers` model used for chunk embeddings.

The query vector is searched in Qdrant with filters:

```text
tenant_id == X-Tenant-ID
namespace_id in request.namespaces
```

This prevents cross-tenant leakage.

### 15.3 Lexical Retrieval

SQLite chunks are also scored with:

- keyword overlap;
- phrase matching;
- diacritic normalization;
- rough Romanian word-form matching.

### 15.4 Reranking

Candidates from Qdrant and SQLite are merged by `chunk_id`, deduplicated, and reranked.

Legal article matches remain stronger than pure vector similarity.

---

## 16. Chunking Design

The legal chunker supports:

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

For each chunk, the service stores:

```text
content
article_number
section_title
point_number
page_number
metadata
```

Additional metadata may include:

```json
{
  "chunk_type": "legal_article",
  "headings": ["CAPITOLUL II", "SECȚIUNEA 1"],
  "paragraph_number": "1",
  "chunk_part": 1,
  "chunk_total": 1,
  "document_preamble": "..."
}
```

Long articles are split into overlapping subchunks while preserving the same legal metadata.

---

## 17. Data Storage

### SQLite

SQLite stores:

```text
jobs
idempotency_keys
sources
chunks
namespace_stats
```

Default path:

```text
./data/app.db
```

### Qdrant

Qdrant stores vector points in collection:

```text
rag_chunks
```

Each point includes:

```json
{
  "tenant_id": "...",
  "namespace_id": "...",
  "source_id": "...",
  "article_number": "15",
  "content": "...",
  "source_title": "...",
  "source_url": "...",
  "metadata": {}
}
```

---

## 18. Security and Isolation

Implemented:

- Bearer API-key validation.
- Required `X-Request-ID`.
- Required `X-Tenant-ID`.
- Tenant-scoped idempotency.
- Tenant-scoped SQLite queries.
- Tenant-scoped Qdrant vector filters.
- Cross-tenant isolation tests.

Important invariant:

```text
A tenant must never retrieve chunks or vectors belonging to another tenant.
```

---

## 19. Troubleshooting

### Qdrant connection refused

Check that Qdrant is running:

```powershell
docker compose -f docker-compose.local.yml up qdrant
```

Verify:

```powershell
curl.exe http://localhost:6333/collections
```

---

### Sentence-transformers model download is slow

The first embedding test or first ingest may take longer because the model is downloaded and cached locally.

Model:

```text
paraphrase-multilingual-MiniLM-L12-v2
```

---

### PowerShell corrupts diacritics

For Unicode-safe endpoint tests, use:

```powershell
python smoke_endpoints.py
```

instead of complex PowerShell JSON bodies.

---

### Tests fail because Qdrant contains stale data

The test suite resets the Qdrant collection when `VECTOR_STORE=qdrant`.

If needed, manually recreate the collection by restarting Qdrant or using the test reset helper.

---

### FastAPI `on_event` deprecation warning

The application may show:

```text
on_event is deprecated, use lifespan event handlers instead
```

This is currently non-blocking and can be cleaned up later by switching to FastAPI lifespan handlers.

---

## 20. Planned Improvements

Before requesting Bitbucket access:

1. Verify Docker build.
2. Verify full `docker-compose.local.yml` stack.
3. Validate `docker-compose.service.yml`.
4. Replace or align `openapi.yaml`.
5. Wrap FastAPI validation errors in the standard `ErrorResponse` format.
6. Add response headers:
   - `X-Request-ID`;
   - `X-Vendor-Trace-ID`;
   - `X-Vendor-Retrieval-Strategy`;
   - `Server-Timing`.
7. Add real URL fetching.
8. Add text/HTML/PDF extraction.
9. Add multipart file ingest.
10. Optionally add `/metrics`.
11. Optionally add LLM generation behind `LLM_PROVIDER`.

---

## 21. Requires CityDock Access

The following cannot be completed locally:

- Push to their Bitbucket organization.
- Create official semver release tag in their repo.
- Trigger their self-hosted Bitbucket runner.
- Produce official CI logs.
- Push image to their GCP Artifact Registry.
- Deploy into their stack.
- Run their official acceptance/eval suite.
- Produce official handoff artifacts from their environment.

---

## 22. Suggested Local Release Tag

After local verification:

```powershell
git tag v0.1.0-local
```

Do not push to CityDock until repository access is granted.

---

## 23. Current Summary

This project currently implements a local FastAPI RAG service with:

```text
authenticated /v1 endpoints
tenant isolation
idempotent ingest
persistent SQLite storage
Qdrant vector indexing
sentence-transformers embeddings
legal article chunking
hybrid retrieval
citation-grounded deterministic answers
no-hallucination fallback
namespace lifecycle operations
endpoint smoke tests
automated test coverage
```

It does not yet implement external LLM generation, real URL/PDF/HTML ingestion, multipart upload, production observability, or official Bitbucket/GCP deployment.
