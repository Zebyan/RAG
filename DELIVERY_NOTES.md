# Delivery Notes

## Completed locally

The local implementation includes the core CityDock / Lex-Advisor RAG service features that can be verified outside the CityDock infrastructure.

### API and service foundation

- FastAPI service.
- `/v1` endpoint surface.
- Pydantic request/response models.
- `/v1/health`.
- `/v1/query`.
- `/v1/ingest`.
- `/v1/ingest/{job_id}`.
- `/v1/namespaces/{namespace_id}/stats`.
- `DELETE /v1/namespaces/{namespace_id}/sources/{source_id}`.
- `DELETE /v1/namespaces/{namespace_id}`.
- `/v1/openapi.json`, serving the static `openapi.yaml` contract as JSON.

### Security, headers, and isolation

- Bearer API-key validation.
- Required `X-Request-ID` validation.
- Required `X-Tenant-ID` tenant scoping.
- Tenant-scoped data isolation.
- Tenant-scoped idempotency through `Idempotency-Key`.
- Standard validation/error response envelope.
- Lowercase contract-aligned error codes:
  - `invalid_request`;
  - `unauthorized`;
  - `not_found`;
  - `namespace_not_found`;
  - `duplicate_job`;
  - `payload_too_large`;
  - `unsupported_media_type`;
  - `validation_error`.
- Standard response headers:
  - `X-Request-ID`;
  - `X-Vendor-Trace-ID`;
  - `X-Vendor-Retrieval-Strategy`;
  - `Server-Timing`.

### Persistence and lifecycle

- Persistent SQLite storage.
- Ingest job persistence.
- Idempotency record persistence.
- Source registry.
- Chunk metadata persistence.
- Namespace statistics.
- Source deletion with `204 No Content`.
- Namespace deletion with contract-aligned `202 Accepted` response:
  - `job_id: del_...`;
  - `status: queued`;
  - `sla: 24h`.
- Qdrant cleanup on source deletion.
- Qdrant cleanup on namespace deletion.
- Post-delete query behavior verified:
  - `answer: null`;
  - `citations: []`;
  - `confidence: 0.0`.

### Ingest and document processing

- Synchronous local ingest processing.
- URL fetching wired into ingest for `source_type=url`.
- URL fetch failure represented as failed ingest job.
- Multipart file upload ingest for `source_type=file`.
- Multipart validation:
  - missing `payload`;
  - missing `file`;
  - invalid multipart payload.
- Oversized multipart file upload rejected before job creation with:
  - HTTP `413`;
  - `payload_too_large`;
  - `max_size_bytes`;
  - `actual_size_bytes`.
- Document extraction service for:
  - `text/plain`;
  - `text/markdown`;
  - `text/html`;
  - `application/pdf`.
- MIME validation.
- Unsupported MIME rejected with `415 unsupported_media_type`.
- Maximum document size validation through extraction layer.
- Article-aware Romanian legal chunking.
- Section/chapter metadata extraction.
- Paragraph and point metadata extraction.
- Long article splitting.
- Metadata preservation across chunks.

### Embeddings and vector search

- Local embeddings with `sentence-transformers`.
- CPU-only PyTorch Docker runtime.
- Qdrant vector database through Docker.
- Qdrant collection creation.
- Vector indexing during ingest.
- Vector search during query.
- Tenant + namespace filters in vector search.

### Retrieval and answer behavior

- Hybrid retrieval:
  - exact article-number boost;
  - Qdrant vector search;
  - lexical keyword retrieval;
  - phrase matching;
  - diacritic normalization;
  - rough Romanian word-form matching;
  - namespace diversity.
- Citation-based deterministic answers.
- Retrieval-only mode with `include_answer=false`.
- No-hallucination empty-result behavior:
  - `answer: null`;
  - `citations: []`;
  - `confidence: 0.0`.
- Exact article query tests.
- Semantic retrieval test.
- Uploaded-file retrieval test.
- Multi-namespace retrieval tests.
- Cross-tenant isolation tests.

### OpenAPI contract status

- Root `openapi.yaml` is present.
- `/v1/openapi.json` serves the static `openapi.yaml` contract as JSON.
- Runtime schema endpoint is aligned with the static contract.
- Local comparison results:
  - no paths only in generated schema;
  - no paths only in `openapi.yaml`;
  - no response-code differences.
- `generated-openapi.local.json` remains a local debug artifact and should not be committed.

### Docker and local verification

- Dockerfile.
- Python base image pinned by SHA digest.
- Non-root `appuser`.
- Service listens on port `8080`.
- Healthcheck uses `/v1/health`.
- `docker-compose.local.yml` with API + Qdrant.
- `docker-compose.service.yml` deployment fragment.
- `docker-compose.service.yml` validates with `docker compose config`.
- Docker image build verified locally.
- Docker Compose local stack verified locally.
- Expanded Python endpoint smoke test.
- Optional smoke coverage for oversized multipart upload and optional endpoints.
- Automated test suite passing locally.

### Repository documentation

- Main `README.md`.
- `DELIVERY_NOTES.md`.
- `docs/TECHNICAL_README.md`.
- Root `openapi.yaml`.
- Static OpenAPI contract served at `/v1/openapi.json`.
- Local fixtures.
- Example curl/API usage documented.
- Project structure documented.
- Architecture and workflow documented.
- Expanded verification commands documented.

---

## Latest local verification evidence

The expanded smoke suite verifies:

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
```

The latest full smoke run ended with:

```text
ALL ENDPOINT SMOKE TESTS PASSED
```

The OpenAPI comparison now shows:

```text
Only in generated:

Only in openapi.yaml:

compare_openapi_responses.py produces no output
```

---

## Current limitations

The following are intentionally not completed locally or remain planned improvements:

- External LLM generation is not active yet.
  - Current answers are deterministic and citation-based.
  - This keeps answers grounded in retrieved citations and avoids sending legal text to an external LLM by default.
- Prometheus `/metrics` is not implemented yet.
- OpenTelemetry instrumentation is not implemented yet.
- Trivy/security scan output is not produced yet.
- Official Bitbucket CI, Artifact Registry push, and deployment require CityDock infrastructure access.
- Official acceptance/evaluation suite requires CityDock infrastructure access.
- Official Schemathesis/property-based contract suite requires CityDock or reviewer-side execution.
- Official performance/load testing requires target infrastructure.

---

## Docker image size note

The Docker image includes a local multilingual embedding runtime using `sentence-transformers` and CPU-only PyTorch.

This keeps Romanian legal documents and user questions inside the deployed stack and avoids third-party embedding APIs, but increases image size beyond a minimal FastAPI-only image.

A production optimization path is to move embeddings to an internal embedding service or replace the embedding runtime with ONNX/FastEmbed after quality validation.

---

## Service compose note

`docker-compose.service.yml` defines only the RAG API service and joins the external `lex-advisor` network.

It does not expose host ports.

It expects Qdrant to be reachable through `QDRANT_URL`.

For local development, `docker-compose.local.yml` includes both the API service and Qdrant.

---

## OpenAPI status

- `openapi.yaml` represents the official/static contract source.
- `GET /v1/openapi.json` serves the same static contract as JSON.
- Local path and response-code comparison between `/v1/openapi.json` and `openapi.yaml` has been verified.
- `generated-openapi.local.json` remains a local debug artifact and should not be committed.

---

## Local verification checklist

Before sending the repository for review, run:

```powershell
pytest
python smoke_endpoints.py --include-large-upload
python compare_openapi_paths.py
python compare_openapi_responses.py
docker compose -f docker-compose.service.yml config
git status
```

For Docker Compose verification:

```powershell
docker compose -f docker-compose.local.yml up --build
```

Then in another terminal:

```powershell
python smoke_endpoints.py http://localhost:8080 test-api-key docker-compose-test-tenant
```

Expected smoke test result:

```text
ALL ENDPOINT SMOKE TESTS PASSED
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

---

## Requires CityDock access

The following steps require CityDock repository or infrastructure access:

- Push to Bitbucket organization, if required by CityDock.
- Create official semver release tag in the target repository.
- Trigger the self-hosted Bitbucket runner.
- Produce official CI logs from CityDock infrastructure.
- Push image to the GCP Artifact Registry.
- Deploy into the CityDock stack.
- Run the official contract/eval suite.
- Confirm target network/service names in the environment.
- Produce official handoff artifacts from the target environment.
