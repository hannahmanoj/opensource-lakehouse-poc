import csv
import math
import random
from datetime import datetime, timedelta
from pathlib import Path

import pendulum
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator


ESTATES = {
    "Rusayl Industrial City": 920,
    "Sohar Industrial City": 1160,
    "Sur Industrial City": 760,
    "Nizwa Industrial City": 640,
    "Al Buraimi Industrial City": 570,
}


def generate_energy_readings(ds: str) -> None:
    """Generate deterministic hourly meter readings for the scheduled date."""
    output_dir = Path("/opt/airflow/project/data/generated")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"industrial_energy_{ds}.csv"
    random_generator = random.Random(ds)
    reading_date = datetime.strptime(ds, "%Y-%m-%d")

    with output_file.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "estate_name",
                "reading_timestamp",
                "energy_kwh",
                "peak_demand_kw",
                "power_factor",
                "renewable_kwh",
                "outage_minutes",
            ]
        )

        for estate_name, base_load in ESTATES.items():
            for hour in range(24):
                business_load = 1.30 if 7 <= hour <= 18 else 0.68
                daily_curve = 1 + 0.12 * math.sin((hour - 7) * math.pi / 12)
                energy_kwh = base_load * business_load * daily_curve * random_generator.uniform(0.94, 1.06)
                renewable_share = max(0, math.sin((hour - 6) * math.pi / 12)) * random_generator.uniform(0.12, 0.24)
                renewable_kwh = energy_kwh * renewable_share
                peak_demand_kw = energy_kwh * random_generator.uniform(1.08, 1.24)
                power_factor = random_generator.uniform(0.89, 0.99)
                outage_minutes = random_generator.choice([0] * 22 + [5, 10])

                writer.writerow(
                    [
                        estate_name,
                        (reading_date + timedelta(hours=hour)).isoformat(sep=" "),
                        round(energy_kwh, 2),
                        round(peak_demand_kw, 2),
                        round(power_factor, 3),
                        round(renewable_kwh, 2),
                        outage_minutes,
                    ]
                )

    print(f"Generated {len(ESTATES) * 24} readings in {output_file}")


with DAG(
    dag_id="industrial_energy_lakehouse_pipeline",
    description="Scheduled raw-to-Iceberg industrial energy pipeline",
    start_date=pendulum.datetime(2026, 8, 1, tz="Asia/Muscat"),
    schedule="0 6 * * *",
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "madayn-data-platform",
        "retries": 2,
        "retry_delay": timedelta(minutes=2),
    },
    tags=["madayn", "minio", "spark", "iceberg", "trino"],
) as dag:
    generate_source = PythonOperator(
        task_id="generate_source_readings",
        python_callable=generate_energy_readings,
        op_kwargs={"ds": "{{ ds }}"},
    )

    land_in_minio = BashOperator(
        task_id="land_raw_csv_in_minio",
        bash_command=(
            "docker exec spark-iceberg spark-submit "
            "/opt/project/domains/industrial-energy/spark/upload_energy_raw.py "
            "--date {{ ds }}"
        ),
    )

    transform_with_spark = BashOperator(
        task_id="transform_and_publish_iceberg",
        bash_command=(
            "docker exec spark-iceberg spark-submit "
            "/opt/project/domains/industrial-energy/spark/transform_energy.py"
        ),
        execution_timeout=timedelta(minutes=20),
    )

    validate_detail_table = BashOperator(
        task_id="validate_clean_table",
        bash_command=(
            "docker exec trino trino --execute \""
            "SELECT IF(count(*) > 0, true, fail('clean table is empty')) "
            "FROM iceberg.demo.industrial_energy_clean\""
        ),
    )

    validate_summary_table = BashOperator(
        task_id="validate_daily_summary",
        bash_command=(
            "docker exec trino trino --execute \""
            "SELECT IF(count(*) > 0, true, fail('summary table is empty')) "
            "FROM iceberg.demo.industrial_energy_daily_summary\""
        ),
    )

    generate_source >> land_in_minio >> transform_with_spark
    transform_with_spark >> [validate_detail_table, validate_summary_table]
