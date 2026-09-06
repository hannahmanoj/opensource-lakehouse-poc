import os
from datetime import datetime
import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from app.retrieval.embeddings import embed_question

DATABASE_URL = os.environ["COPILOT_DATABASE_URL"]

def build_filters( component: str | None, severity: str | None, from_time: datetime | None, to_time: datetime | None, ) -> tuple[str, list]:
    clauses = []
    parameters = []

    if component is not None:
        clauses.append("component = %s")
        parameters.append(component)

    if severity is not None:
        clauses.append("severity = %s")
        parameters.append(severity)

    if from_time is not None:
        clauses.append("occurred_at >= %s")
        parameters.append(from_time)

    if to_time is not None:
        clauses.append("occurred_at <= %s")
        parameters.append(to_time)

    if not clauses:
        return "", []

    return " AND " + " AND ".join(clauses), parameters