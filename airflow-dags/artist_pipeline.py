from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime

with DAG(
    dag_id = "artist_pipeline",
    start_date = datetime(2026, 1, 1),
    schedule_interval = None,
    catchup = False,
) as dag:

    load_csv = BashOperator(
        task_id = "load_csv_to_iceberg",
        bash_command="docker exec spark-iceberg spark-submit /opt/spark-apps/transform_genres.py",
    )
    run_spark_transform = BashOperator(
        task_id = "spark_genre_summary",
        bash_command="docker exec spark-iceberg spark-submit /opt/spark-apps/transform_genres.py",
    )

    load_csv >> run_spark_transform