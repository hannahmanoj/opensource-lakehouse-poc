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

# full text search using postgres built in text search capabilities
def keyword_search( connection, question: str, filter_sql: str, filter_parameters: list, limit: int = 10,) -> list[dict]:
    query = f"""
        WITH search_query AS (
            SELECT plainto_tsquery('english', %s) AS query
        )
        SELECT id
            , source_name
            , component
            , severity
            , title
            , content
            , source_uri
            , line_start
            , line_end
            , ts_rank_cd(
                text_search,
                search_query.query
            ) AS keyword_score
        FROM knowledge_chunks, search_query
        WHERE text_search @@ search_query.query
        {filter_sql}
        ORDER BY keyword_score DESC
        LIMIT %s
    """

    parameters = [
        question,
        *filter_parameters,
        limit,
    ]

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query, parameters)
        return cursor.fetchall()

## combines the results of vector search and keyword search using reciprocal rank fusion (rrf) to produce a final ranked list of results
def reciprocal_rank_fusion(
    vector_results: list[dict],
    keyword_results: list[dict],
    final_limit: int = 5,
    rrf_constant: int = 60,
) -> list[dict]:
    combined = {}

    for rank, row in enumerate(vector_results, start=1):
        source_id = str(row["id"])

        combined[source_id] = {
            **row,
            "source_id": source_id,
            "semantic_score": float(row["semantic_score"]),
            "keyword_score": None,
            "semantic_rank": rank,
            "keyword_rank": None,
            "rrf_score": 1 / (rrf_constant + rank),
            "matched_by": ["semantic"],
        }

    for rank, row in enumerate(keyword_results, start=1):
        source_id = str(row["id"])
        contribution = 1 / (rrf_constant + rank)

        if source_id in combined:
            combined[source_id]["keyword_score"] = float(
                row["keyword_score"]
            )
            combined[source_id]["keyword_rank"] = rank
            combined[source_id]["rrf_score"] += contribution
            combined[source_id]["matched_by"].append("keyword")
        else:
            combined[source_id] = {
                **row,
                "source_id": source_id,
                "semantic_score": None,
                "keyword_score": float(row["keyword_score"]),
                "semantic_rank": None,
                "keyword_rank": rank,
                "rrf_score": contribution,
                "matched_by": ["keyword"],
            }

    results = list(combined.values())

    for result in results:
        if len(result["matched_by"]) == 2:
            result["why_ranked"] = (
                "Matched both the question's meaning "
                "and its exact keywords."
            )
        elif result["matched_by"] == ["semantic"]:
            result["why_ranked"] = (
                "Matched the meaning of the question."
            )
        else:
            result["why_ranked"] = (
                "Matched exact words from the question."
            )

        result["excerpt"] = result["content"][:800]
        result.pop("content", None)
        result.pop("id", None)

    return sorted(
        results,
        key=lambda result: result["rrf_score"],
        reverse=True,
    )[:final_limit]