from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException, Query, status

from app.classification import classify_question
from app.collectors.airflow import AirflowCollector
from app.collectors.iceberg import IcebergCollector
from app.collectors.platform_health import PlatformHealthCollector
from app.collectors.trino import TrinoCollector
from app.retrieval.hybrid import hybrid_search
from app.retrieval.sufficiency import evaluate_sufficiency
from app.schemas import (
    CopilotRequest,
    CopilotResponse,
    IcebergEvidenceRequest,
    LiveEvidenceResponse,
    SearchResponse,
)

# creates the api application
app = FastAPI(
    title="Lakehouse Copilot API",
    description=(
        "Read-only, evidence-based for madayn lakehouse poc"
    ),
    version="1.0.0",
)

# connects an http address to a python function, which is called when the address is requested
@app.get("/health", status_code=status.HTTP_200_OK)
async def health() -> dict[str, str]:
    return { "status": "ok", "service": "lakehouse-ops-copilot" }

@app.post(
    "/api/copilot/search",
    response_model=SearchResponse,
)
def search(request: CopilotRequest) -> SearchResponse:
    classification = classify_question(request.question)
    
    results = hybrid_search(
        question=request.question,
        component=request.component,
        severity=request.severity,
        from_time=request.from_time,
        to_time=request.to_time,
    )

    return SearchResponse(
        question=request.question,
        classification=classification,
        results=results,
    )

@app.post(
    "/api/copilot/ask",
    response_model=CopilotResponse,
)
def ask(request: CopilotRequest) -> CopilotResponse:
    classification = classify_question(request.question)

    results = hybrid_search(
        question=request.question,
        component=request.component,
        severity=request.severity,
        from_time=request.from_time,
        to_time=request.to_time,
    )

    decision = evaluate_sufficiency(
        classification=classification,
        results=results,
        requested_component=request.component,
        date_requested=(
            request.from_time is not None
            or request.to_time is not None
        ),
    )

    if not decision.sufficient:
        missing = ", ".join(decision.missing_evidence)

        return CopilotResponse(
            classification=classification,
            answer=(
                "I cannot answer safely because I am missing: "
                f"{missing}."
            ),
            confidence="low",
            insufficient_evidence=True,
            missing_evidence=decision.missing_evidence,
            citations=[],
        )

    return CopilotResponse(
        classification=classification,
        answer=(
            "The evidence is sufficient for answer generation. "
            "LLM generation is not connected yet."
        ),
        confidence=decision.confidence,
        insufficient_evidence=False,
        missing_evidence=[],
        citations=[
            {
                "source_id": result["source_id"],
                "title": result["title"],
                "source_uri": result["source_uri"],
                "excerpt": result["excerpt"],
            }
            for result in decision.qualified_evidence
        ],
    )


def collector_error(error: Exception) -> HTTPException:
    if isinstance(error, ValueError):
        return HTTPException(
            status_code=400,
            detail=str(error),
        )

    if isinstance(error, httpx.HTTPError):
        return HTTPException(
            status_code=502,
            detail="The evidence source is unavailable",
        )

    return HTTPException(
        status_code=500,
        detail="The collector failed safely",
    )


@app.get(
    "/api/copilot/live/airflow/dag-runs",
    response_model=LiveEvidenceResponse,
)
def live_airflow_dag_runs(
    limit: int = Query(default=10, ge=1, le=50),
) -> LiveEvidenceResponse:
    collector = AirflowCollector()

    try:
        evidence = collector.recent_dag_runs(limit)
        return LiveEvidenceResponse(
            source="airflow",
            evidence=evidence,
        )
    except Exception as error:
        raise collector_error(error) from error
    finally:
        collector.close()


@app.get(
    "/api/copilot/live/trino/{diagnostic}",
    response_model=LiveEvidenceResponse,
)
def live_trino_diagnostic(
    diagnostic: Literal[
        "cluster_overview",
        "recent_failures",
    ],
) -> LiveEvidenceResponse:
    collector = TrinoCollector()

    try:
        evidence = collector.run_diagnostic(diagnostic)
        return LiveEvidenceResponse(
            source="trino",
            evidence=evidence,
        )
    except Exception as error:
        raise collector_error(error) from error
    finally:
        collector.close()


@app.post(
    "/api/copilot/live/iceberg",
    response_model=LiveEvidenceResponse,
)
def live_iceberg(
    request: IcebergEvidenceRequest,
) -> LiveEvidenceResponse:
    collector = IcebergCollector()

    try:
        evidence = collector.collect(
            request.table,
            request.operation,
        )
        return LiveEvidenceResponse(
            source="iceberg",
            evidence=evidence,
        )
    except Exception as error:
        raise collector_error(error) from error
    finally:
        collector.close()


@app.get(
    "/api/copilot/live/health",
    response_model=LiveEvidenceResponse,
)
def live_platform_health(
    service: str | None = None,
) -> LiveEvidenceResponse:
    collector = PlatformHealthCollector()

    try:
        evidence = collector.collect(service)
        return LiveEvidenceResponse(
            source="platform_health",
            evidence=evidence,
        )
    except Exception as error:
        raise collector_error(error) from error
    finally:
        collector.close()
