from dataclasses import dataclass
from uuid import UUID

from fastapi import Header

from app.config import settings
from app.errors import raise_error


@dataclass(frozen=True)
class AuthContext:
    request_id: str
    tenant_id: str


def _validate_uuid(value: str, field_name: str) -> None:
    try:
        UUID(value)
    except ValueError:
        raise_error(
            status_code=400,
            code="invalid_request",
            message=f"{field_name} must be a valid UUID.",
            request_id=value if field_name == "X-Request-ID" else None,
            details={"field": field_name},
        )


async def verify_auth(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
) -> AuthContext:
    if not x_request_id:
        raise_error(400, "invalid_request", "Missing X-Request-ID header.")
    _validate_uuid(x_request_id, "X-Request-ID")

    if not x_tenant_id:
        raise_error(400, "invalid_request", "Missing X-Tenant-ID header.", request_id=x_request_id)

    if not authorization:
        raise_error(401, "unauthorized", "Missing Authorization header.", request_id=x_request_id)

    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise_error(401, "unauthorized", "Authorization must use Bearer scheme.", request_id=x_request_id)

    token = parts[1].strip()
    if token != settings.rag_api_key:
        raise_error(401, "unauthorized", "Invalid API key.", request_id=x_request_id)

    return AuthContext(request_id=x_request_id, tenant_id=x_tenant_id)
