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
- cross-tenant isolation tests
- multi-namespace retrieval tests
- vector-store integration tests
- hybrid retrieval tests
- `/v1/openapi.json`
- Dockerfile scaffold
- `docker-compose.local.yml` with Qdrant
- `docker-compose.service.yml` scaffold
- local fixtures
- Python endpoint smoke test
- automated tests passing

## Current limitations

- External LLM generation is not active yet.
- Answers are deterministic and citation-based.
- Real URL fetching is not implemented yet.
- PDF/HTML/text extraction from external sources is not implemented yet.
- Multipart file upload is not implemented yet.
- `openapi.yaml` still needs final alignment with the official contract.
- Docker build still needs to be verified locally.
- Docker Compose full local run still needs to be verified.
- OpenTelemetry and Prometheus metrics are not implemented yet.
- FastAPI validation errors still need to be wrapped in the standard `ErrorResponse` format.
- Response headers such as `X-Vendor-Trace-ID` and `Server-Timing` are not fully implemented yet.
- Bitbucket CI, Trivy scan, Artifact Registry push, and deployment require CityDock access.

## Planned local improvements before requesting repository access

- Verify Docker build.
- Verify `docker-compose.local.yml`.
- Validate `docker-compose.service.yml`.
- Replace or align `openapi.yaml`.
- Wrap FastAPI validation errors in the standard `ErrorResponse` format.
- Add response headers:
  - `X-Request-ID`
  - `X-Vendor-Trace-ID`
  - `X-Vendor-Retrieval-Strategy`
  - `Server-Timing`
- Add real URL fetching.
- Add text/HTML/PDF extraction.
- Add multipart file ingest.
- Optionally add `/metrics`.
- Optionally add LLM generation behind `LLM_PROVIDER`.

## Requires CityDock access

- Push to their Bitbucket organization.
- Create semver release tag in their repo.
- Trigger their self-hosted Bitbucket runner.
- Produce official CI logs from their infrastructure.
- Push image to their GCP Artifact Registry.
- Deploy into their stack.
- Run their official contract/eval suite.
- Produce official handoff artifacts from their environment.