import time
from fastapi import APIRouter, Depends

from app.auth import AuthContext, verify_auth
from app.config import settings
from app.models import QueryRequest, QueryResponse, Usage
from app.services.answer_service import build_answer_response
from app.services.retrieval_service import retrieve_chunks

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def post_query(request: QueryRequest, auth: AuthContext = Depends(verify_auth)) -> QueryResponse:
    started = time.monotonic()

    chunks = retrieve_chunks(
        tenant_id=auth.tenant_id,
        namespaces=request.namespaces,
        question=request.question,
        top_k=request.top_k,
        hint_article_number=request.hint_article_number,
    )

    answer, citations, confidence = build_answer_response(
        include_answer=request.include_answer,
        question=request.question,
        chunks=chunks,
        style_hints=request.style_hints,
    )

    latency_ms = int((time.monotonic() - started) * 1000)

    return QueryResponse(
        request_id=auth.request_id,
        answer=answer,
        citations=citations,
        usage=Usage(model_id="mvp-local"),
        latency_ms=latency_ms,
        model_version=settings.app_version,
        retrieval_strategy="article_keyword_mvp",
        confidence=confidence,
        trace_id=None,
    )
