import os
from datetime import datetime
import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from app.retrieval.embeddings import embed_question

DATABASE_URL = os.environ["COPILOT_DATABASE_URL"]

# build_filters adds additional where clauses 
# from the users q to avoid searching the whole db
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

# takes the numerical meaning of the user’s question
# compares it with the meaning of every eligible document chunk
#  and returns the 10 closest matches.
def vector_search( connection, question_embedding, filter_sql: str, filter_parameters: list, limit: int = 10,) -> list[dict]:
    query = f"""
        SELECT id
          , source_name
          , component
          , severity
          , title
          , content
          , source_uri
          , line_start
          , line_end
          , 1 - (embedding <=> %s) AS semantic_score
        FROM knowledge_chunks
        WHERE embedding IS NOT NULL
        {filter_sql}
        ORDER BY embedding <=> %s
        LIMIT %s
    """

    parameters = [ question_embedding, *filter_parameters, question_embedding, limit,]

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query, parameters)
        return cursor.fetchall()