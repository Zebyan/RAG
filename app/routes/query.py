import time
from fastapi import APIRouter, Depends, Response, Request

from app.auth import AuthContext, verify_auth
from app.config import settings
from app.models import QueryRequest, QueryResponse, Usage
from app.services.answer_service import build_answer_response
from app.services.retrieval_service import retrieve_chunks

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def post_query(
    query_request: QueryRequest,
    response: Response,
    http_request: Request,
    auth: AuthContext = Depends(verify_auth),
) -> QueryResponse:
    started = time.monotonic()

    chunks = retrieve_chunks(
        tenant_id=auth.tenant_id,
        namespaces=query_request.namespaces,
        question=query_request.question,
        top_k=query_request.top_k,
        hint_article_number=query_request.hint_article_number,
    )

    answer, citations, confidence = build_answer_response(
        include_answer=query_request.include_answer,
        question=query_request.question,
        chunks=chunks,
        style_hints=query_request.style_hints,
    )

    latency_ms = int((time.monotonic() - started) * 1000)

    retrieval_strategy = (
        "hybrid_qdrant_article_keyword"
        if settings.vector_store.lower() == "qdrant"
        else "article_keyword_mvp"
    )

    response.headers["X-Vendor-Retrieval-Strategy"] = retrieval_strategy

    return QueryResponse(
        request_id=auth.request_id,
        answer=answer,
        citations=citations,
        usage=Usage(model_id="mvp-local"),
        latency_ms=latency_ms,
        model_version=settings.app_version,
        retrieval_strategy=retrieval_strategy,
        confidence=confidence,
        trace_id=getattr(http_request.state, "vendor_trace_id", None),
    )
