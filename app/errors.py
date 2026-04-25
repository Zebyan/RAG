from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError


def error_payload(code: str, message: str, request_id: str | None = None, details: dict | None = None) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
            "details": details or {},
        }
    }


class RagHTTPException(HTTPException):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        request_id: str | None = None,
        details: dict | None = None,
    ):
        super().__init__(
            status_code=status_code,
            detail=error_payload(code, message, request_id, details),
        )


async def rag_http_exception_handler(request: Request, exc: RagHTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.detail)


async def generic_http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    request_id = request.headers.get("X-Request-ID")
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)

    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(
            code="invalid_request",
            message=str(exc.detail),
            request_id=request_id,
        ),
    )


def raise_error(status_code: int, code: str, message: str, request_id: str | None = None, details: dict | None = None):
    raise RagHTTPException(status_code, code, message, request_id, details)
