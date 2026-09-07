from typing import Any

import httpx


HEALTH_ENDPOINTS = {
    "airflow": "http://airflow:8080/health",
    "trino": "http://trino:8080/v1/info",
    "iceberg-rest": "http://iceberg-rest:8181/v1/config",
    "minio": "http://minio:9000/minio/health/live",
}


class PlatformHealthCollector:
    def __init__(self):
        self.client = httpx.Client(timeout=5.0)

    def collect(
        self,
        service: str | None = None,
    ) -> list[dict[str, Any]]:
        if service is not None:
            if service not in HEALTH_ENDPOINTS:
                raise ValueError(
                    f"Service is not allow-listed: {service}"
                )

            targets = {
                service: HEALTH_ENDPOINTS[service],
            }
        else:
            targets = HEALTH_ENDPOINTS

        return [
            self._probe(name, url)
            for name, url in targets.items()
        ]

    def _probe(
        self,
        service: str,
        url: str,
    ) -> dict[str, Any]:
        try:
            response = self.client.get(url)

            return {
                "service": service,
                "healthy": response.is_success,
                "status_code": response.status_code,
            }
        except httpx.RequestError as error:
            return {
                "service": service,
                "healthy": False,
                "status_code": None,
                "error": type(error).__name__,
            }

    def close(self) -> None:
        self.client.close()
