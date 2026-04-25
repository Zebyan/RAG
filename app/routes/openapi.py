from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/openapi.json")
async def get_openapi_json(request: Request) -> dict:
    # TODO: for strict delivery, serve the committed openapi.yaml converted to JSON
    # or ensure generated schema is equivalent to the committed contract.
    return request.app.openapi()
