from urllib.parse import quote

import httpx

from app.collectors.common import safe_log
from app.config import (
    AIRFLOW_PASSWORD,
    AIRFLOW_URL,
    AIRFLOW_USERNAME,
    MAX_LOG_BYTES,
)


class AirflowCollector:
    def __init__(self):
        self.client = httpx.Client(
            base_url=AIRFLOW_URL,
            auth=(AIRFLOW_USERNAME, AIRFLOW_PASSWORD),
            timeout=10.0,
        )

    def recent_dag_runs(self, limit: int = 10) -> list[dict]:
        safe_limit = min(max(limit, 1), 50)

        response = self.client.get(
            "/api/v1/dags/~/dagRuns",
            params={
                "limit": safe_limit,
                "order_by": "-execution_date",
            },
        )
        response.raise_for_status()

        dag_runs = response.json().get("dag_runs", [])

        return [
            {
                "dag_id": run.get("dag_id"),
                "dag_run_id": run.get("dag_run_id"),
                "state": run.get("state"),
                "execution_date": run.get("execution_date"),
                "start_date": run.get("start_date"),
                "end_date": run.get("end_date"),
            }
            for run in dag_runs
        ]

    def task_instances(
        self,
        dag_id: str,
        run_id: str,
    ) -> list[dict]:
        safe_dag_id = quote(dag_id, safe="")
        safe_run_id = quote(run_id, safe="")

        response = self.client.get(
            f"/api/v1/dags/{safe_dag_id}"
            f"/dagRuns/{safe_run_id}/taskInstances"
        )
        response.raise_for_status()

        tasks = response.json().get("task_instances", [])

        return [
            {
                "task_id": task.get("task_id"),
                "state": task.get("state"),
                "start_date": task.get("start_date"),
                "end_date": task.get("end_date"),
                "try_number": task.get("try_number"),
                "max_tries": task.get("max_tries"),
            }
            for task in tasks
        ]

    def task_log(
        self,
        dag_id: str,
        run_id: str,
        task_id: str,
        try_number: int,
    ) -> dict:
        if try_number < 1 or try_number > 100:
            raise ValueError(
                "try_number must be between 1 and 100"
            )

        safe_dag_id = quote(dag_id, safe="")
        safe_run_id = quote(run_id, safe="")
        safe_task_id = quote(task_id, safe="")

        response = self.client.get(
            f"/api/v1/dags/{safe_dag_id}"
            f"/dagRuns/{safe_run_id}"
            f"/taskInstances/{safe_task_id}"
            f"/logs/{try_number}",
            headers={"Accept": "text/plain"},
        )
        response.raise_for_status()

        return safe_log(
            response.text,
            MAX_LOG_BYTES,
        )

    def close(self) -> None:
        self.client.close()