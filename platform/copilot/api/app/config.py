import os


AIRFLOW_URL = os.getenv(
    "COPILOT_AIRFLOW_URL",
    "http://airflow:8080",
)

AIRFLOW_USERNAME = os.getenv(
    "COPILOT_AIRFLOW_USERNAME",
    "",
)

AIRFLOW_PASSWORD = os.getenv(
    "COPILOT_AIRFLOW_PASSWORD",
    "",
)

TRINO_URL = os.getenv(
    "COPILOT_TRINO_URL",
    "http://trino:8080",
)

TRINO_USER = os.getenv(
    "COPILOT_TRINO_USER",
    "copilot",
)

MAX_LOG_BYTES = int(
    os.getenv("COPILOT_MAX_LOG_BYTES", "32768")
)

SMALL_FILE_THRESHOLD_BYTES = int(
    os.getenv(
        "COPILOT_SMALL_FILE_THRESHOLD_BYTES",
        str(128 * 1024 * 1024),
    )
)