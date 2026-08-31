# Industrial Energy Data Product

This domain is the primary Airflow automation demonstration. It simulates hourly
energy telemetry for five industrial cities and publishes analytics-ready
Iceberg tables.

## Contents

```text
industrial-energy/
├── dags/
│   └── industrial_energy_pipeline.py
└── spark/
    ├── upload_energy_raw.py
    └── transform_energy.py
```

## Data flow

| Step | Airflow task | Output |
|---|---|---|
| 1 | `generate_source_readings` | Scheduled daily CSV |
| 2 | `land_raw_csv_in_minio` | `iceberg.raw.industrial_energy_readings` |
| 3 | `transform_and_publish_iceberg` | Clean and daily-summary tables |
| 4 | `validate_clean_table` | Trino readability and non-empty check |
| 5 | `validate_daily_summary` | Trino readability and non-empty check |

Curated tables:

```text
iceberg.demo.industrial_energy_clean
iceberg.demo.industrial_energy_daily_summary
```

The landing job dynamically overwrites the scheduled date partition, making a
retry safe and preventing duplicate records.

## Demo

1. Open Airflow at http://localhost:8090.
2. Select `industrial_energy_lakehouse_pipeline`.
3. Show the Graph view and explain the task dependencies.
4. Trigger the DAG or show the latest successful scheduled run.
5. Open task logs to demonstrate auditability and retries.
6. Query `industrial_energy_daily_summary` through Trino or Power BI.

The generated readings are synthetic and intended only for demonstrating the
platform workflow.
