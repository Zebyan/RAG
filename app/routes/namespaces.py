from fastapi import APIRouter, Depends

from app.auth import AuthContext, verify_auth
from app.models import DeleteNamespaceResponse, NamespaceStats
from app.services.namespace_service import (
    delete_namespace_data,
    delete_source_data,
    get_namespace_stats_data,
)

router = APIRouter()


@router.get("/namespaces/{namespace_id}/stats", response_model=NamespaceStats)
async def get_namespace_stats(namespace_id: str, auth: AuthContext = Depends(verify_auth)) -> NamespaceStats:
    return get_namespace_stats_data(
        tenant_id=auth.tenant_id,
        request_id=auth.request_id,
        namespace_id=namespace_id,
    )


@router.delete("/namespaces/{namespace_id}/sources/{source_id}", status_code=204)
async def delete_source(
    namespace_id: str,
    source_id: str,
    auth: AuthContext = Depends(verify_auth),
) -> None:
    delete_source_data(
        tenant_id=auth.tenant_id,
        request_id=auth.request_id,
        namespace_id=namespace_id,
        source_id=source_id,
    )
    return None


@router.delete(
    "/namespaces/{namespace_id}",
    response_model=DeleteNamespaceResponse,
    status_code=202,
)
async def delete_namespace_route(
    namespace_id: str,
    auth: AuthContext = Depends(verify_auth),
) -> DeleteNamespaceResponse:
    return delete_namespace_data(
        tenant_id=auth.tenant_id,
        namespace_id=namespace_id,
        request_id=auth.request_id,
    )
