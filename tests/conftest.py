import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.sqlite_store import reset_db
from app.config import settings
from app.services.vector_store import reset_collection

@pytest.fixture(autouse=True)
def reset_test_stores():
    reset_db()

    if settings.vector_store.lower() == "qdrant":
        reset_collection()

    yield

@pytest.fixture()
def client():
    return TestClient(app)

@pytest.fixture()
def auth_headers():
    return {
        "Authorization": "Bearer test-api-key",
        "X-Request-ID": "11111111-1111-4111-8111-111111111111",
        "X-Tenant-ID": "test-tenant",
    }


@pytest.fixture()
def ingest_headers(auth_headers):
    return {
        **auth_headers,
        "Idempotency-Key": "33333333-3333-4333-8333-333333333333",
    }
