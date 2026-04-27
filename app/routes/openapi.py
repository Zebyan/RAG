from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter
from fastapi.responses import JSONResponse


router = APIRouter()


@lru_cache(maxsize=1)
def _load_static_openapi_contract() -> dict[str, Any]:
    contract_path = Path(__file__).resolve().parents[2] / "openapi.yaml"

    with contract_path.open("r", encoding="utf-8") as file:
        contract = yaml.safe_load(file)

    if not isinstance(contract, dict):
        raise RuntimeError("openapi.yaml did not parse to a JSON object.")

    return contract


@router.get("/openapi.json", include_in_schema=False)
async def get_openapi_contract() -> JSONResponse:
    return JSONResponse(content=_load_static_openapi_contract())