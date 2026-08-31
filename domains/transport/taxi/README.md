# NYC Taxi Data Product

This domain demonstrates high-volume ingestion and transformation:

```text
SQL Server -> NiFi -> MinIO raw Avro -> Spark -> Iceberg -> Trino -> Power BI
```

The Spark job produces:

```text
iceberg.demo.taxi_trips_clean
iceberg.demo.taxi_hourly_summary
```

The large source CSV remains local and is excluded from Git. It must not be
committed to the repository or container image.
