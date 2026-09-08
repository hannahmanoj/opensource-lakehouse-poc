from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Component = Literal["airflow", "spark", "trino", "iceberg", "minio",]

Classification = Literal["incident_diagnosis", "documentation_question", "operational_checklist", "table_health", "access_control", "unknown"]

Confidence = Literal["low", "medium", "high"]

Severity = Literal["info", "warning", "error", "critical"]

class CopilotRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    component: Component | None = None
    severity: Severity | None = None
    from_time: datetime | None = None
    to_time: datetime | None = None

class Citation(BaseModel):
    source_id: str
    title: str
    source_uri: str
    excerpt: str

class SearchResult(BaseModel):
    source_id: str
    source_type: str
    title: str
    component: Component
    severity: Severity | None
    occurred_at: datetime | None
    excerpt: str
    source_uri: str
    line_start: int | None
    line_end: int | None

    semantic_score: float | None
    keyword_score: float | None
    semantic_rank: int | None
    keyword_rank: int | None
    rrf_score: float

    matched_by: list[Literal["semantic", "keyword"]]
    why_ranked: str

class SearchResponse(BaseModel):
    question: str
    classification: Classification
    results: list[SearchResult]

class CopilotResponse(BaseModel):
    classification: Classification
    answer: str
    confidence: Confidence
    insufficient_evidence: bool
    missing_evidence: list[str] = Field(default_factory=list)
    citations: list[Citation]
    findings: list[str] = Field(default_factory=list)
    recommended_checks: list[str] = Field(
    default_factory=list
)


class IcebergEvidenceRequest(BaseModel):
    table: str = Field(min_length=1, max_length=300)
    operation: Literal["files", "snapshots", "table_health"]


class LiveEvidenceResponse(BaseModel):
    source: Literal[
        "airflow",
        "trino",
        "iceberg",
        "platform_health",
    ]
    evidence: Any

class GeneratedAnswer(BaseModel):
    answer: str
    findings: list[str]
    recommended_checks: list[str]
    citation_ids: list[str]
    confidence: Confidence
    insufficient_evidence: bool