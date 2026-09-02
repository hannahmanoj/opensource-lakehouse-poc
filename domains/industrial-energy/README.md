# industrial energy data product

this domain is one of the airflow automation demonstration. It simulates hourly energy telemetry for five industrial cities and publishes analytics-ready
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
