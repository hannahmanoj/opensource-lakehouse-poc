from fastapi import FastAPI, status
from app.schemas import (
    CopilotRequest,
    CopilotResponse,
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
async def search(request: CopilotRequest) -> SearchResponse:
    return SearchResponse(
        question=request.question,
        results=[]
    )

@app.post(
    "/api/copilot/ask",
    response_model=CopilotResponse,
)
async def ask(request: CopilotRequest) -> CopilotResponse:
    return CopilotResponse(
        classification="incident_diagnosis",
        answer="",
        confidence="low",
        insufficient_evidence=False,
        citations=[]
    )
