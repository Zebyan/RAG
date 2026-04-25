import time
from fastapi import APIRouter, Response

from app.config import settings
from app.models import HealthStatus

router = APIRouter()
START_TIME = time.monotonic()


@router.get("/health", response_model=HealthStatus)
async def get_health(response: Response) -> HealthStatus:
    uptime = int(time.monotonic() - START_TIME)

    dependencies = {
        "vector_store": "ok",
        "llm": "ok" if settings.llm_provider == "none" or settings.anthropic_api_key else "degraded",
        "object_store": "ok",
    }

    status = "ok"
    if "down" in dependencies.values():
        status = "down"
        response.status_code = 503
    elif "degraded" in dependencies.values():
        status = "degraded"

    return HealthStatus(
        status=status,
        version=settings.app_version,
        uptime_seconds=uptime,
        dependencies=dependencies,
    )
