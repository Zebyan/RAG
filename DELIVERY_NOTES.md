# Delivery Notes

## Completed locally

- FastAPI service
- `/v1` endpoint surface
- Pydantic request/response models
- auth/header validation
- `Authorization: Bearer <api_key>` validation
- `X-Request-ID` validation
- `X-Tenant-ID` tenant scoping
- tenant-scoped `Idempotency-Key` handling for ingest
- tenant + namespace isolation
- persistent SQLite storage
- ingest flow with job status
- synchronous MVP ingest processing
- article-aware legal chunking
- section/chapter metadata extraction
- paragraph and point metadata extraction
- long article splitting
- document extraction service:
  - `text/plain`
  - `text/markdown`
  - `text/html`
  - `application/pdf`
- Qdrant vector database through Docker
- local embeddings with `sentence-transformers`
- vector indexing during ingest
- vector search during query
- hybrid retrieval:
  - exact article-number boost
  - Qdrant vector search
  - lexical keyword retrieval
  - phrase matching
  - diacritic normalization
  - rough Romanian word-form matching
  - namespace diversity
- citation-based deterministic answers
- no-hallucination empty-result behavior
- namespace stats
- source deletion
- namespace deletion
- Qdrant cleanup on source deletion
- Qdrant cleanup on namespace deletion
- standard validation error response envelope
- response headers:
  - `X-Request-ID`
  - `X-Vendor-Trace-ID`
  - `X-Vendor-Retrieval-Strategy`
  - `Server-Timing`
- cross-tenant isolation tests
- multi-namespace retrieval tests
- vector-store integration tests
- hybrid retrieval tests
- document extraction tests
- `/v1/openapi.json`
- root `openapi.yaml`
- Dockerfile
- `docker-compose.local.yml` with Qdrant
- `docker-compose.service.yml` deployment fragment
- local fixtures
- Python endpoint smoke test
- automated tests passing locally
- Docker image build verified locally
- Docker Compose full local stack verified locally
- Docker endpoint smoke tests passing
- `docker-compose.service.yml` validated with `docker compose config`

## Current limitations

- External LLM generation is not active yet.
- Answers are deterministic and citation-based.
- URL fetching is not wired into ingest yet.
- Multipart file upload is not implemented yet.
- Realistic PDF fixture validation is still pending.
- OpenTelemetry and Prometheus metrics are not implemented yet.
- Trivy/security scan output is not produced yet.
- Final strict OpenAPI reconciliation is still pending.
- Bitbucket CI, Artifact Registry push, and deployment require CityDock access.

## Docker image size note

The Docker image includes a local multilingual embedding runtime using `sentence-transformers`/PyTorch. This keeps Romanian legal documents and user questions inside the deployed stack and avoids third-party embedding APIs, but increases image size beyond the nominal 500 MB target. A production optimization path is to move embeddings to an internal embedding service or replace the embedding runtime with ONNX/FastEmbed after quality validation.

## Service compose note

`docker-compose.service.yml` defines only the RAG API service and joins the external `lex-advisor` network. It does not expose host ports. It expects Qdrant to be reachable through `QDRANT_URL`. For local development, `docker-compose.local.yml` includes both the API service and Qdrant.

## OpenAPI status

- `openapi.yaml` is present in the repository root.
- `GET /v1/openapi.json` is served by the running FastAPI service.
- `openapi.yaml` should represent the official/static contract source.
- `/v1/openapi.json` currently represents the generated implementation schema.
- Final strict schema reconciliation remains planned before official handoff.

## Planned local improvements before requesting repository access

- Wire real URL fetching into ingest.
- Add multipart file ingest.
- Add realistic PDF fixture tests.
- Optionally add `/metrics`.
- Optionally add OpenTelemetry instrumentation.
- Run local dependency/security scan if tooling is available.
- Optionally add LLM generation behind `LLM_PROVIDER`.
- Final OpenAPI reconciliation against the official contract.
- Final README/DELIVERY_NOTES cleanup.
- Create local release tag.

## Requires CityDock access

- Push to Bitbucket organization.
- Create semver release tag in the repo.
- Trigger the self-hosted Bitbucket runner.
- Produce official CI logs from the infrastructure.
- Push image to the GCP Artifact Registry.
- Deploy into the stack.
- Run the official contract/eval suite.
- Confirm target network/service names in the environment.
- Produce official handoff artifacts from the environment.


