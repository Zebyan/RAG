from fastapi import APIRouter, Depends, Header

from app.auth import AuthContext, verify_auth
from app.errors import raise_error
from app.models import IngestAcceptedResponse, IngestJobStatus, IngestRequest
from app.services.ingest_service import create_ingest_job, get_ingest_job

router = APIRouter()


@router.post("/ingest", response_model=IngestAcceptedResponse, status_code=202)
async def post_ingest(
    request: IngestRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    auth: AuthContext = Depends(verify_auth),
) -> IngestAcceptedResponse:
    if not idempotency_key:
        raise_error(400, "invalid_request", "Missing Idempotency-Key header.", request_id=auth.request_id)

    return create_ingest_job(
        tenant_id=auth.tenant_id,
        request_id=auth.request_id,
        request=request,
        idempotency_key=idempotency_key,
    )


@router.get("/ingest/{job_id}", response_model=IngestJobStatus)
async def get_ingest_status(job_id: str, auth: AuthContext = Depends(verify_auth)) -> IngestJobStatus:
    return get_ingest_job(tenant_id=auth.tenant_id, request_id=auth.request_id, job_id=job_id)
