from fastapi import FastAPI, status
from app.schemas import (
    CopilotRequest,
    CopilotResponse,
    SearchResponse,
)
from app.retrieval.hybrid import hybrid_search
from app.classification import classify_question

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

    return CopilotResponse(
        classification=classification,
        answer="",
        confidence="low",
        insufficient_evidence=False,
        citations=[],
    )
