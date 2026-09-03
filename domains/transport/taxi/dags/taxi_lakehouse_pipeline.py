""" SQL Server -> NiFi -> MinIO -> Spark -> Iceberg -> Trino pipeline."""

import os
import time
from datetime import timedelta

import boto3
import pendulum
import requests
import urllib3
from airflow import DAG
from airflow.exceptions import AirflowException
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

NIFI_API_URL = os.environ.get("NIFI_API_URL", "https://nifi:8443/nifi-api").rstrip("/")
NIFI_USERNAME = os.environ.get("NIFI_SINGLE_USER_USERNAME")
NIFI_PASSWORD = os.environ.get("NIFI_SINGLE_USER_PASSWORD")
NIFI_PROCESS_GROUP_ID = os.environ.get("NIFI_TAXI_PROCESS_GROUP_ID")
NIFI_QUERY_PROCESSOR_ID = os.environ.get("NIFI_TAXI_QUERY_PROCESSOR_ID")
NIFI_S3_PROCESSOR_ID = os.environ.get("NIFI_TAXI_S3_PROCESSOR_ID")


def _require_settings() -> None:
    settings = {
        "NIFI_SINGLE_USER_USERNAME": NIFI_USERNAME,
        "NIFI_SINGLE_USER_PASSWORD": NIFI_PASSWORD,
        "NIFI_TAXI_PROCESS_GROUP_ID": NIFI_PROCESS_GROUP_ID,
        "NIFI_TAXI_QUERY_PROCESSOR_ID": NIFI_QUERY_PROCESSOR_ID,
        "NIFI_TAXI_S3_PROCESSOR_ID": NIFI_S3_PROCESSOR_ID,
    }
    missing = [name for name, value in settings.items() if not value]
    if missing:
        raise AirflowException(f"Missing required settings: {', '.join(missing)}")


def _nifi_session() -> requests.Session:
    _require_settings()
    session = requests.Session()
    session.headers.update({"Host": "localhost:8443"})
    session.verify = False  # Local POC: NiFi uses a generated self-signed certificate.
    response = session.post(
        f"{NIFI_API_URL}/access/token",
        data={"username": NIFI_USERNAME, "password": NIFI_PASSWORD},
        timeout=30,
    )
    response.raise_for_status()
    session.headers.update({"Authorization": f"Bearer {response.text}"})
    return session


def _processor(session: requests.Session, processor_id: str) -> dict:
    response = session.get(f"{NIFI_API_URL}/processors/{processor_id}", timeout=30)
    response.raise_for_status()
    return response.json()


def _set_processor_state(
    session: requests.Session, processor_id: str, state: str
) -> None:
    processor = _processor(session, processor_id)
    response = session.put(
        f"{NIFI_API_URL}/processors/{processor_id}/run-status",
        json={
            "revision": processor["revision"],
            "state": state,
            "disconnectedNodeAcknowledged": False,
        },
        timeout=30,
    )
    response.raise_for_status()


def run_nifi_query_once() -> None:
    """Run QueryDatabaseTable once instead of leaving it on a repeating timer."""
    session = _nifi_session()
    status_response = session.get(
        f"{NIFI_API_URL}/flow/process-groups/{NIFI_PROCESS_GROUP_ID}/status",
        params={"recursive": "true"},
        timeout=30,
    )
    status_response.raise_for_status()
    queued_count = int(
        status_response.json()["processGroupStatus"]["aggregateSnapshot"][
            "queuedCount"
        ]
    )
    if queued_count:
        print(
            f"NiFi already has {queued_count} queued FlowFiles; "
            "using that existing batch instead of querying SQL Server again."
        )
        return

    _set_processor_state(session, NIFI_QUERY_PROCESSOR_ID, "RUN_ONCE")

    deadline = time.monotonic() + 45 * 60
    observed_activity = False
    while time.monotonic() < deadline:
        processor = _processor(session, NIFI_QUERY_PROCESSOR_ID)
        snapshot = processor["status"]["aggregateSnapshot"]
        state = processor["component"]["state"]
        active_threads = snapshot["activeThreadCount"]
        observed_activity = observed_activity or active_threads > 0 or state != "STOPPED"
        if observed_activity and state == "STOPPED" and active_threads == 0:
            return
        time.sleep(10)

    raise AirflowException("NiFi QueryDatabaseTable did not finish within 45 minutes")


def drain_nifi_queue_to_minio() -> None:
    """Run PutS3Object until every queued Avro FlowFile has been uploaded."""
    session = _nifi_session()
    _set_processor_state(session, NIFI_S3_PROCESSOR_ID, "RUNNING")
    deadline = time.monotonic() + 45 * 60
    empty_checks = 0

    try:
        while time.monotonic() < deadline:
            response = session.get(
                f"{NIFI_API_URL}/flow/process-groups/{NIFI_PROCESS_GROUP_ID}/status",
                params={"recursive": "true"},
                timeout=30,
            )
            response.raise_for_status()
            snapshot = response.json()["processGroupStatus"]["aggregateSnapshot"]
            queue_empty = int(snapshot["queuedCount"]) == 0
            inactive = snapshot["activeThreadCount"] == 0
            empty_checks = empty_checks + 1 if queue_empty and inactive else 0
            if empty_checks >= 2:
                return
            time.sleep(10)
        raise AirflowException("NiFi queue did not drain within 45 minutes")
    finally:
        _set_processor_state(session, NIFI_S3_PROCESSOR_ID, "STOPPED")


def verify_raw_avro() -> None:
    """Fail before Spark if NiFi did not publish any raw taxi objects."""
    client = boto3.client(
        "s3",
        endpoint_url="http://minio:9000",
        aws_access_key_id=os.environ["LAKEHOUSE_AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["LAKEHOUSE_AWS_SECRET_ACCESS_KEY"],
        region_name="us-east-1",
    )
    response = client.list_objects_v2(
        Bucket="lakehouse", Prefix="raw/taxi_trips/", MaxKeys=1
    )
    if response.get("KeyCount", 0) < 1:
        raise AirflowException("No Avro objects found under lakehouse/raw/taxi_trips/")


with DAG(
    dag_id="taxi_lakehouse_pipeline",
    description="Orchestrates taxi ingestion from SQL Server through curated Iceberg tables",
    start_date=pendulum.datetime(2026, 9, 1, tz="Asia/Muscat"),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "transport-data-team",
        "retries": 1,
        "retry_delay": timedelta(minutes=2),
    },
    tags=["madayn", "transport", "nifi", "minio", "spark", "iceberg", "trino"],
) as dag:
    extract_from_sql_server = PythonOperator(
        task_id="extract_sql_server_with_nifi",
        python_callable=run_nifi_query_once,
        execution_timeout=timedelta(minutes=50),
    )

    land_raw_avro = PythonOperator(
        task_id="land_raw_avro_in_minio",
        python_callable=drain_nifi_queue_to_minio,
        execution_timeout=timedelta(minutes=50),
    )

    check_raw_avro = PythonOperator(
        task_id="verify_raw_avro_in_minio",
        python_callable=verify_raw_avro,
    )

    transform_with_spark = BashOperator(
        task_id="transform_and_publish_iceberg",
        bash_command=(
            "docker exec spark-iceberg spark-submit "
            "--packages org.apache.spark:spark-avro_2.12:3.5.5,"
            "org.apache.hadoop:hadoop-aws:3.3.4 "
            "/opt/project/domains/transport/taxi/spark/transform_taxi.py"
     ),
        execution_timeout=timedelta(hours=2),
    )

    validate_clean_table = BashOperator(
        task_id="validate_taxi_trips_clean",
        bash_command=(
            "docker exec trino trino --user platform.admin --catalog iceberg "
            "--schema demo --execute \""
            "SELECT IF(count(*) > 0, true, fail('taxi_trips_clean is empty')) "
            "FROM taxi_trips_clean\""
        ),
    )

    validate_raw_table = BashOperator(
        task_id="validate_taxi_raw_iceberg",
        bash_command=(
            "docker exec trino trino --user platform.admin --catalog iceberg "
            "--schema raw --execute \""
            "SELECT IF(count(*) > 0, true, fail('raw taxi table is empty')) "
            "FROM taxi_trips\""
        ),
    )

    validate_summary_table = BashOperator(
        task_id="validate_taxi_hourly_summary",
        bash_command=(
            "docker exec trino trino --user platform.admin --catalog iceberg "
            "--schema demo --execute \""
            "SELECT IF(count(*) > 0, true, fail('taxi_hourly_summary is empty')) "
            "FROM taxi_hourly_summary\""
        ),
    )

    extract_from_sql_server >> land_raw_avro >> check_raw_avro >> transform_with_spark
    transform_with_spark >> [
        validate_raw_table,
        validate_clean_table,
        validate_summary_table,
    ]
