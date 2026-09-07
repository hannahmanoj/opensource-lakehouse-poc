from dataclasses import dataclass
from typing import Any

from app.schemas import Classification, Confidence


MIN_SEMANTIC_SCORE = 0.40
LOG_SOURCE_TYPES = {
    "airflow_log",
    "spark_log",
    "trino_log",
    "platform_log",
}


@dataclass(frozen=True)
class SufficiencyDecision:
    sufficient: bool
    confidence: Confidence
    missing_evidence: list[str]
    qualified_evidence: list[dict[str, Any]]


def is_relevant(result: dict[str, Any]) -> bool:
    semantic_score = result.get("semantic_score")
    keyword_score = result.get("keyword_score")

    return bool(
        (
            semantic_score is not None
            and semantic_score >= MIN_SEMANTIC_SCORE
        )
        or (
            keyword_score is not None
            and keyword_score > 0
        )
    )


def evaluate_sufficiency(
    classification: Classification,
    results: list[dict[str, Any]],
    requested_component: str | None = None,
    date_requested: bool = False,
) -> SufficiencyDecision:
    qualified = [result for result in results if is_relevant(result)]
    missing: list[str] = []

    if not qualified:
        missing.append("Relevant knowledge-base evidence")

        if requested_component:
            missing.append(
                f"Evidence for component: {requested_component}"
            )

        if date_requested:
            missing.append("Evidence in the requested date range")

    if classification == "incident_diagnosis":
        has_timestamped_log = any(
            result.get("source_type") in LOG_SOURCE_TYPES
            and result.get("occurred_at") is not None
            for result in qualified
        )

        if not has_timestamped_log:
            component = requested_component or "Relevant"
            missing.append(f"{component.title()} timestamped log")

    independent_sources = {
        result.get("source_uri")
        for result in qualified
        if result.get("source_uri")
    }

    sufficient = not missing

    if not sufficient:
        confidence: Confidence = "low"
    elif len(independent_sources) >= 2:
        confidence = "high"
    else:
        confidence = "medium"

    return SufficiencyDecision(
        sufficient=sufficient,
        confidence=confidence,
        missing_evidence=missing,
        qualified_evidence=qualified,
    )
