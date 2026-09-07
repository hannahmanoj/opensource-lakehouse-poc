from typing import Any
import httpx
from app.config import TRINO_URL, TRINO_USER


DIAGNOSTIC_QUERIES = {
    "cluster_overview": """
        SELECT
            node_id,
            coordinator,
            state,
            http_uri
        FROM system.runtime.nodes
        ORDER BY coordinator DESC, node_id
    """,
    "recent_failures": """
        SELECT
            query_id,
            state,
            user,
            source,
            error_type,
            error_code,
            created
        FROM system.runtime.queries
        WHERE state = 'FAILED'
        ORDER BY created DESC
        LIMIT 20
    """,
}


class TrinoCollector:
    def __init__(self):
        self.client = httpx.Client(
            timeout=10.0,
        )

    def run_diagnostic(
        self,
        name: str,
    ) -> dict[str, Any]:
        if name not in DIAGNOSTIC_QUERIES:
            raise ValueError(
                f"Unsupported diagnostic: {name}"
            )

        sql = DIAGNOSTIC_QUERIES[name]

        return self._execute(sql)

    def _execute(
        self,
        sql: str,
    ) -> dict[str, Any]:
        response = self.client.post(
            f"{TRINO_URL}/v1/statement",
            content=sql,
            headers={
                "X-Trino-User": TRINO_USER,
                "X-Trino-Source": "lakehouse-copilot",
            },
        )
        response.raise_for_status()

        pages = [response.json()]

        while pages[-1].get("nextUri"):
            next_uri = pages[-1]["nextUri"]

            response = self.client.get(next_uri)
            response.raise_for_status()

            pages.append(response.json())

            if len(pages) > 100:
                raise RuntimeError(
                    "Trino returned too many result pages"
                )

        columns = []

        for page in pages:
            if page.get("columns"):
                columns = [
                    column["name"]
                    for column in page["columns"]
                ]
                break

        rows = []

        for page in pages:
            for row in page.get("data", []):
                rows.append(dict(zip(columns, row)))

        error = None

        for page in pages:
            if page.get("error"):
                error = page["error"]
                break

        return {
            "query_id": pages[0].get("id"),
            "rows": rows,
            "error": error,
        }

    def close(self) -> None:
        self.client.close()