from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Component = Literal["airflow", "spark", "trino", "iceberg", "minio",]

Classification = Literal["incident_diagnosis", "documentation_question", "operational_checklist", "table_health", "access_control", "unknown"]

Confidence = Literal["low", "medium", "high"]

class CopilotRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    component: Component | None = None
    from_time: datetime | None = None
    to_time: datetime | None = None

class Citation(BaseModel):
    source_id: str
    title: str
    source_uri: str
    excerpt: str

class SearchResult(BaseModel):
    source_id: str
    title: str
    component: Component
    excerpt: str
    source_uri: str
    score: float

class SearchResponse(BaseModel):
    question: str
    results: list[SearchResult]

class CopilotResponse(BaseModel):
    classification: Classification
    answer: str
    confidence: Confidence
    insufficient_evidence: bool
    citations: list[Citation]