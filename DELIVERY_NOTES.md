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
- `/v1/openapi.json`.

### Security, headers, and isolation

- Bearer API-key validation.
- Required `X-Request-ID` validation.
- Required `X-Tenant-ID` tenant scoping.
- Tenant-scoped data isolation.
- Tenant-scoped idempotency through `Idempotency-Key`.
- Standard validation error response envelope.
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
- Source deletion.
- Namespace deletion.
- Qdrant cleanup on source deletion.
- Qdrant cleanup on namespace deletion.

### Ingest and document processing

- Synchronous local ingest processing.
- URL fetching wired into ingest for `source_type=url`.
- Multipart file upload ingest for `source_type=file`.
- Document extraction service for:
  - `text/plain`;
  - `text/markdown`;
  - `text/html`;
  - `application/pdf`.
- MIME validation.
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
- No-hallucination empty-result behavior:
  - `answer: null`;
  - `citations: []`;
  - `confidence: 0.0`.
- Multi-namespace retrieval tests.
- Cross-tenant isolation tests.

### Docker and local verification

- Dockerfile.
- `docker-compose.local.yml` with API + Qdrant.
- `docker-compose.service.yml` deployment fragment.
- `docker-compose.service.yml` validates with `docker compose config`.
- Docker image build verified locally.
- Docker Compose local stack verified locally.
- Docker endpoint smoke tests passing.
- Python endpoint smoke test.
- Automated test suite passing locally.

### Repository documentation

- Main `README.md`.
- `DELIVERY_NOTES.md`.
- Root `openapi.yaml`.
- Generated runtime OpenAPI available at `/v1/openapi.json`.
- Local fixtures.
- Example curl/API usage documented.
- Project structure documented.
- Architecture and workflow documented.

---

## Current limitations

The following are intentionally not completed locally or remain planned improvements:

- External LLM generation is not active yet.
  - Current answers are deterministic and citation-based.
  - This keeps answers grounded in retrieved citations and avoids sending legal text to an external LLM by default.
- Prometheus `/metrics` is not implemented yet.
- OpenTelemetry instrumentation is not implemented yet.
- Trivy/security scan output is not produced yet.
- Final strict OpenAPI byte-level reconciliation may still be required before official handoff.
- Official Bitbucket CI, Artifact Registry push, and deployment require CityDock infrastructure access.
- Official acceptance/evaluation suite requires CityDock infrastructure access.

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

- `openapi.yaml` is present in the repository root.
- `GET /v1/openapi.json` is served by the running FastAPI service.
- `openapi.yaml` should represent the official/static contract source.
- `/v1/openapi.json` represents the generated implementation schema.
- Final strict schema reconciliation remains planned before official handoff.

---

## Local verification checklist

Before sending the repository for review, run:

```powershell
pytest
python smoke_endpoints.py
docker compose -f docker-compose.service.yml config
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
