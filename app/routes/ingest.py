from __future__ import annotations

import hashlib
import json

from fastapi import APIRouter, Depends, Header, Request
from pydantic import ValidationError

from app.auth import AuthContext, verify_auth
from app.errors import raise_error
from app.models import IngestAcceptedResponse, IngestJobStatus, IngestRequest
from app.services.ingest_service import create_ingest_job, get_ingest_job_status

router = APIRouter()

async def _parse_ingest_request(
    http_request: Request,
) -> tuple[IngestRequest, bytes | None, str | None, str | None]:
    content_type = http_request.headers.get("content-type", "")
    request_id = http_request.headers.get("X-Request-ID")

    is_form_request = (
        content_type.startswith("multipart/form-data")
        or content_type.startswith("application/x-www-form-urlencoded")
    )

    if is_form_request:
        form = await http_request.form()

        payload_raw = form.get("payload")
        uploaded_file = form.get("file")

        if payload_raw is None:
            raise_error(
                status_code=422,
                code="VALIDATION_ERROR",
                message="Multipart field 'payload' is required.",
                request_id=request_id,
                details={"errors": [{"loc": ["body", "payload"], "msg": "Field required"}]},
            )

        if uploaded_file is None:
            raise_error(
                status_code=422,
                code="VALIDATION_ERROR",
                message="Multipart field 'file' is required.",
                request_id=request_id,
                details={"errors": [{"loc": ["body", "file"], "msg": "Field required"}]},
            )

        try:
            payload = json.loads(str(payload_raw))
        except json.JSONDecodeError as exc:
            raise_error(
                status_code=422,
                code="VALIDATION_ERROR",
                message="Invalid multipart payload.",
                request_id=request_id,
                details={"errors": [{"loc": ["body", "payload"], "msg": str(exc)}]},
            )

        try:
            ingest_request = IngestRequest.model_validate(payload)
        except ValidationError as exc:
            raise_error(
                status_code=422,
                code="VALIDATION_ERROR",
                message="Invalid multipart payload.",
                request_id=request_id,
                details={"errors": exc.errors()},
            )

        file_content = await uploaded_file.read()
        file_mime_type = uploaded_file.content_type
        filename = uploaded_file.filename

        file_sha256 = hashlib.sha256(file_content).hexdigest()
        metadata = dict(ingest_request.metadata or {})
        metadata["uploaded_filename"] = filename
        metadata["uploaded_file_sha256"] = file_sha256
        metadata["uploaded_file_size_bytes"] = len(file_content)

        ingest_request = ingest_request.model_copy(
            update={
                "source_type": "file",
                "metadata": metadata,
            }
        )

        return ingest_request, file_content, file_mime_type, filename

    try:
        payload = await http_request.json()
    except json.JSONDecodeError as exc:
        raise_error(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Invalid JSON payload.",
            request_id=request_id,
            details={"errors": [{"loc": ["body"], "msg": str(exc)}]},
        )

    try:
        ingest_request = IngestRequest.model_validate(payload)
    except ValidationError as exc:
        raise_error(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Invalid JSON payload.",
            request_id=request_id,
            details={"errors": exc.errors()},
        )

    return ingest_request, None, None, None

@router.post("/ingest", response_model=IngestAcceptedResponse, status_code=202)
async def post_ingest(
    http_request: Request,
    auth: AuthContext = Depends(verify_auth),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
) -> IngestAcceptedResponse:
    ingest_request, file_content, file_mime_type, filename = await _parse_ingest_request(
        http_request
    )

    return create_ingest_job(
        tenant_id=auth.tenant_id,
        request=ingest_request,
        idempotency_key=idempotency_key,
        file_content=file_content,
        file_mime_type=file_mime_type,
        filename=filename,
        request_id=auth.request_id,
    )

@router.get("/ingest/{job_id}", response_model=IngestJobStatus)
async def get_ingest_status(
    job_id: str,
    auth: AuthContext = Depends(verify_auth),
) -> IngestJobStatus:
    return get_ingest_job_status(
        tenant_id=auth.tenant_id,
        job_id=job_id,
        request_id=auth.request_id,
    )