# industrial energy data product

this domain is one of the primary Airflow automation demonstration. It simulates hourly energy telemetry for five industrial cities and publishes analytics-ready
iceberg tables

## contents

```text
industrial-energy/
├── dags/
│   └── industrial_energy_pipeline.py
└── spark/
    ├── upload_energy_raw.py
    └── transform_energy.py
```

## data flow

| step | airflow task | output |
|---|---|---|
| 1 | `generate_source_readings` | scheduled daily csv |
| 2 | `land_raw_csv_in_minio` | `iceberg.raw.industrial_energy_readings` |
| 3 | `transform_and_publish_iceberg` | clean and daily-summary tables |
| 4 | `validate_clean_table` | trino readability and non-empty check |
| 5 | `validate_daily_summary` | trino readability and non-empty check |

curated tables created:

```text
iceberg.demo.industrial_energy_clean
iceberg.demo.industrial_energy_daily_summary
```

the landing job dynamically overwrites the scheduled date partition, making a
retry safe and preventing duplicate records

## demo

1. open Airflow at http://localhost:8090.
2. select `industrial_energy_lakehouse_pipeline`
3. show the Graph view and explain the task dependencies
4. trigger the DAG or show the latest successful scheduled run
5. open task logs to demonstrate auditability and retries
6. query `industrial_energy_daily_summary` through trino or power bi

the generated readings are synthetic and intended only for demonstrating the
platform workflow
