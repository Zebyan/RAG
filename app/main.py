from fastapi import FastAPI, HTTPException

from app.config import settings
from app.errors import RagHTTPException, rag_http_exception_handler, generic_http_exception_handler
from app.routes import health, ingest, namespaces, openapi, query


def create_app() -> FastAPI:
    app = FastAPI(
        title="CityDock RAG MVP",
        version=settings.app_version,
        docs_url="/docs",
        openapi_url=None,
    )

    app.add_exception_handler(RagHTTPException, rag_http_exception_handler)
    app.add_exception_handler(HTTPException, generic_http_exception_handler)

    app.include_router(health.router, prefix="/v1", tags=["health"])
    app.include_router(openapi.router, prefix="/v1", tags=["openapi"])
    app.include_router(query.router, prefix="/v1", tags=["query"])
    app.include_router(ingest.router, prefix="/v1", tags=["ingest"])
    app.include_router(namespaces.router, prefix="/v1", tags=["namespaces"])

    return app


app = create_app()
