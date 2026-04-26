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
- in-memory tenant-scoped store
- ingest flow with job status
- synchronous MVP ingest processing
- article-aware legal chunking
- exact article-number retrieval boost
- lexical keyword retrieval
- phrase matching
- diacritic normalization for scoring
- rough Romanian word-form matching
- namespace diversity for multi-namespace queries
- citation-based deterministic answers
- no-hallucination empty-result behavior
- namespace stats
- source deletion
- namespace deletion
- cross-tenant isolation tests
- multi-namespace retrieval tests
- `/v1/openapi.json`
- Dockerfile scaffold
- `docker-compose.local.yml` scaffold
- `docker-compose.service.yml` scaffold
- local fixtures
- local smoke-test documentation
- automated tests: 23 passing

## Current limitations

- Storage is currently in-memory; indexed data does not survive process restart.
- Qdrant/ChromaDB/vector database is not active yet.
- No real embeddings are generated yet.
- Retrieval is lexical/hybrid-MVP, not full semantic vector retrieval.
- No external LLM generation is active yet.
- Answers are deterministic and citation-based.
- Ingest processing is synchronous internally.
- Real URL fetching is not implemented yet.
- PDF/HTML/text extraction from external sources is not implemented yet.
- Multipart file upload is not implemented yet.
- `openapi.yaml` still needs final alignment with the official contract.
- Docker build still needs to be verified locally.
- Docker Compose local run still needs to be verified.
- OpenTelemetry and Prometheus metrics are not implemented yet.
- Bitbucket CI, Trivy scan, Artifact Registry push, and deployment require CityDock access.

## Planned local improvements before requesting repository access

- Add persistent SQLite storage.
- Add Qdrant vector database through Docker.
- Add local embeddings with `sentence-transformers`.
- Add hybrid retrieval: exact article match + vector search + lexical matching.
- Add vector-specific tests.
- Add real URL fetching.
- Add text/HTML/PDF extraction.
- Add multipart file ingest.
- Verify Docker build.
- Verify `docker-compose.local.yml`.
- Validate `docker-compose.service.yml`.
- Replace or align `openapi.yaml`.
- Wrap FastAPI validation errors in the standard `ErrorResponse` format.
- Add response headers: `X-Request-ID`, `X-Vendor-Trace-ID`, `X-Vendor-Retrieval-Strategy`, `Server-Timing`.
- Optionally add `/metrics`.

## Requires CityDock access

- Push to their Bitbucket organization.
- Create semver release tag in their repo.
- Trigger their self-hosted Bitbucket runner.
- Produce official CI logs from their infrastructure.
- Push image to their GCP Artifact Registry.
- Deploy into their stack.
- Run their official contract/eval suite.
- Produce official handoff artifacts from their environment.