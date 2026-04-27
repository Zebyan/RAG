from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field, HttpUrl, field_validator
from pydantic import BaseModel, Field, ConfigDict, field_validator

class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorDetail


class Usage(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    model_id: str = "mvp-local"


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class StyleHints(BaseModel):
    answer_max_chars: int = Field(default=2000, ge=100, le=10000)
    cite_inline: bool = True
    tone: Literal["formal", "casual"] = "formal"


class QueryRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    question: str = Field(..., min_length=1, max_length=2000)
    language: Literal["ro"]
    namespaces: list[str] = Field(..., min_length=1, max_length=10)
    top_k: int = Field(default=10, ge=1, le=50)
    hint_article_number: str | None = None
    rerank: bool = True
    include_answer: bool = True
    conversation_history: list[ConversationTurn] = Field(default_factory=list, max_length=15)
    style_hints: StyleHints | None = None


class Chunk(BaseModel):
    chunk_id: str
    content: str = Field(..., max_length=4000)
    article_number: str | None = None
    section_title: str | None = None
    point_number: str | None = None
    page_number: int | None = None
    source_id: str
    source_url: str | None = None
    source_title: str | None = None
    namespace_id: str
    score: float = Field(..., ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Citation(BaseModel):
    marker: str
    chunk: Chunk


class QueryResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    request_id: str
    answer: str | None
    citations: list[Citation]
    usage: Usage
    latency_ms: int
    model_version: str
    retrieval_strategy: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    trace_id: str | None = None


class IngestRequest(BaseModel):
    namespace_id: str
    source_id: str
    source_type: Literal["url", "file"]
    url: str | None = None
    mime_type_hint: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    callback_url: str | None = None

    @field_validator("url")
    @classmethod
    def validate_url_when_source_type_url(cls, value: str | None, info):
        # Full validation also happens in route/service layer because source_type
        # is not always available at this validator stage.
        return value


class IngestAcceptedResponse(BaseModel):
    job_id: str
    status: str
    submitted_at: str
    estimated_completion_at: str | None = None


class IngestProgress(BaseModel):
    stage: str
    percent: int = Field(..., ge=0, le=100)
    chunks_created: int = Field(default=0, ge=0)


class IngestJobStatus(BaseModel):
    job_id: str
    namespace_id: str
    source_id: str
    status: str
    progress: IngestProgress
    submitted_at: str
    completed_at: str | None = None
    error: dict[str, Any] | None = None


class DeleteNamespaceResponse(BaseModel):
    job_id: str
    status: str 
    sla: str


class NamespaceStats(BaseModel):
    namespace_id: str
    chunk_count: int
    source_count: int
    total_tokens_indexed: int
    last_ingested_at: str | None = None
    embedding_model: str
    embedding_dim: int


class HealthStatus(BaseModel):
    status: Literal["ok", "degraded", "down"]
    version: str
    uptime_seconds: int
    dependencies: dict[str, str]
