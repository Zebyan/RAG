# Delivery Notes

## Can be completed locally

- FastAPI service
- `/v1` endpoints
- Pydantic models
- auth/header validation
- tenant-scoped idempotency
- tenant + namespace isolation
- local persistence / ChromaDB
- ingest worker
- retrieval + exact article boost
- citations
- no-hallucination behavior
- namespace stats/delete
- tests
- Dockerfile
- docker-compose files
- openapi.yaml
- /v1/openapi.json
- README
- local smoke tests

## Requires CityDock access

- push to their Bitbucket organization
- semver release tag in their repo
- self-hosted Bitbucket runner
- official CI logs
- GCP Artifact Registry push
- deployment into their stack
