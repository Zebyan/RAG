# CityDock / Lex-Advisor RAG MVP

This is the implementation scaffold for a FastAPI-based RAG service MVP.

## Current status

Project structure is created. Endpoint implementations will be added step by step.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

## First smoke test

```bash
curl http://localhost:8080/v1/health
```

## Implementation order

1. Models
2. Auth and error responses
3. Health endpoint
4. Store layer
5. Ingest endpoint
6. Article-based chunking
7. Query retrieval
8. Citations and deterministic answers
9. Namespace stats/delete
10. Docker and smoke tests
