from typing import Any

from app.collectors.trino import TrinoCollector
from app.config import SMALL_FILE_THRESHOLD_BYTES


ALLOWED_TABLES = {
    "iceberg.demo.industrial_energy_daily_summary",
    "iceberg.demo.taxi_hourly_summary",
}

ALLOWED_OPERATIONS = {
    "files",
    "snapshots",
    "table_health",
}


class IcebergCollector:
    def __init__(self):
        self.trino = TrinoCollector()

    def collect(
        self,
        table: str,
        operation: str,
    ) -> dict[str, Any]:
        if table not in ALLOWED_TABLES:
            raise ValueError(
                f"Table is not allow-listed: {table}"
            )

        if operation not in ALLOWED_OPERATIONS:
            raise ValueError(
                f"Unsupported Iceberg operation: {operation}"
            )

        catalog, schema, table_name = table.split(".")

        files_table = self._metadata_table(
            catalog,
            schema,
            table_name,
            "files",
        )
        snapshots_table = self._metadata_table(
            catalog,
            schema,
            table_name,
            "snapshots",
        )

        queries = {
            "files": f"""
                SELECT
                    file_path,
                    file_size_in_bytes,
                    record_count
                FROM {files_table}
                ORDER BY file_size_in_bytes ASC
                LIMIT 100
            """,
            "snapshots": f"""
                SELECT
                    snapshot_id,
                    parent_id,
                    committed_at,
                    operation,
                    summary
                FROM {snapshots_table}
                ORDER BY committed_at DESC
                LIMIT 20
            """,
            "table_health": f"""
                SELECT
                    count(*) AS file_count,
                    coalesce(avg(file_size_in_bytes), 0)
                        AS average_file_size_bytes,
                    count_if(
                        file_size_in_bytes
                        < {SMALL_FILE_THRESHOLD_BYTES}
                    ) AS small_file_count
                FROM {files_table}
            """,
        }

        result = self.trino._execute(queries[operation])

        return {
            "table": table,
            "operation": operation,
            "small_file_threshold_bytes": (
                SMALL_FILE_THRESHOLD_BYTES
            ),
            **result,
        }

    @staticmethod
    def _metadata_table(
        catalog: str,
        schema: str,
        table_name: str,
        suffix: str,
    ) -> str:
        identifiers = (
            catalog,
            schema,
            f"{table_name}${suffix}",
        )

        return ".".join(
            '"' + identifier.replace('"', '""') + '"'
            for identifier in identifiers
        )

    def close(self) -> None:
        self.trino.close()
