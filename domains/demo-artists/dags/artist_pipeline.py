from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime

with DAG(
    dag_id="artist_summary_pipeline",
    description="Manual demo transformation for the artists dataset",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    tags=["demo", "spark", "iceberg"],
) as dag:
    run_spark_transform = BashOperator(
        task_id="build_genre_summary",
        bash_command=(
            "docker exec spark-iceberg spark-submit "
            "/opt/project/domains/demo-artists/spark/transform_genres.py"
        ),
    )
