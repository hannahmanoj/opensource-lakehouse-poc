import re

from app.schemas import Classification

ACCESS_CONTROL_KEYWORDS = {
    "access denied",
    "permission denied",
    "unauthorized",
    "forbidden",
    "permission",
    "permissions",
    "role",
    "roles",
    "group",
    "policy",
    "masking",
    "row filter",
}

TABLE_HEALTH_KEYWORDS = {
    "small file",
    "small files",
    "compaction",
    "compact",
    "file size",
    "file count",
    "snapshots",
    "snapshot count",
    "table health",
    "optimize table",
}

OPERATIONAL_CHECKLIST_KEYWORDS = {
    "before restarting",
    "before restart",
    "should i restart",
    "safe to restart",
    "restart checklist",
    "what should i check",
    "how do i safely",
    "pre-check",
}

INCIDENT_KEYWORDS = {
    "fail",
    "failed",
    "failure",
    "error",
    "exception",
    "retry",
    "retries",
    "timed out",
    "timeout",
    "unavailable",
    "connection refused",
    "not found",
    "yesterday",
    "last run",
}

DOCUMENTATION_KEYWORDS = {
    "what is",
    "what are",
    "explain",
    "definition",
    "how does",
    "documentation",
    "difference between",
}

def normalize_question(question:str) -> str:
    normalized = question.casefold()
    normalized = re.sub(r"[_-]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)

    return normalized.strip()

def contains_any(
    question: str,
    keywords: set[str],
) -> bool:
    return any(keyword in question for keyword in keywords)


def classify_question(question: str) -> Classification:
    normalized = normalize_question(question)

    if contains_any(normalized, ACCESS_CONTROL_KEYWORDS):
        return "access_control"

    if contains_any(normalized, TABLE_HEALTH_KEYWORDS):
        return "table_health"

    if contains_any(normalized, OPERATIONAL_CHECKLIST_KEYWORDS):
        return "operational_checklist"

    if contains_any(normalized, INCIDENT_KEYWORDS):
        return "incident_diagnosis"

    if contains_any(normalized, DOCUMENTATION_KEYWORDS):
        return "documentation_question"

    return "unknown"
