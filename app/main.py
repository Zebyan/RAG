from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from requests import Request
import time
import uuid

from app.config import settings
from app.errors import RagHTTPException, rag_http_exception_handler, generic_http_exception_handler
from app.routes import health, ingest, namespaces, openapi, query
from app.services.sqlite_store import init_db

def create_app() -> FastAPI:
    app = FastAPI(
        title="CityDock RAG MVP",
        version=settings.app_version,
        docs_url="/docs",
        openapi_url=None,
    )

    app.add_exception_handler(RagHTTPException, rag_http_exception_handler)
    app.add_exception_handler(HTTPException, generic_http_exception_handler)

    @app.middleware("http")
    async def response_headers_middleware(request: Request, call_next):
        started = time.perf_counter()

        request_id = request.headers.get("X-Request-ID")
        vendor_trace_id = request.headers.get("X-Vendor-Trace-ID") or f"tr_{uuid.uuid4().hex}"

        request.state.vendor_trace_id = vendor_trace_id

        response = await call_next(request)

        duration_ms = (time.perf_counter() - started) * 1000

        if request_id:
            response.headers["X-Request-ID"] = request_id

        response.headers["X-Vendor-Trace-ID"] = vendor_trace_id
        response.headers["Server-Timing"] = f"app;dur={duration_ms:.2f}"

        return response
    
    app.include_router(health.router, prefix="/v1", tags=["health"])
    app.include_router(openapi.router, prefix="/v1", tags=["openapi"])
    app.include_router(query.router, prefix="/v1", tags=["query"])
    app.include_router(ingest.router, prefix="/v1", tags=["ingest"])
    app.include_router(namespaces.router, prefix="/v1", tags=["namespaces"])

    @app.on_event("startup")
    async def startup_event() -> None:
        init_db()


    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        request_id = request.headers.get("X-Request-ID")

        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed.",
                    "request_id": request_id,
                    "details": {
                        "errors": exc.errors(),
                    },
                }
            },
        )

    return app


app = create_app()
