# nyc taxi data product

this domain demonstrates high-volume ingestion and transformation:

```text
sql server -> nifi -> minIO raw avro -> spark -> iceberg -> trino -> power bi
```

spark job produces:

```text
iceberg.raw.taxi_trips
iceberg.demo.taxi_trips_clean
iceberg.demo.taxi_hourly_summary
```

nifi's avro objects is the immutable landing copy. 
spark also publishes their source-shaped contents as `iceberg.raw.taxi_trips`, which trino can query while the iceberg catalog manages schema, snapshots, and table metadata.

## orchestration

`taxi_lakehouse_pipeline` coordinates the complete POC path:

```text
nifi QueryDatabaseTable (run once)
  -> drain PutS3Object queue to minIO
  -> verify raw avro exists
  -> publish the raw iceberg table and run the spark transformation
  -> validate the raw, clean, and summary iceberg tables through trino
```

the dag is intentionally manual initially because the source contains 10.9
million rows. Configure an incremental NiFi maximum-value column or another
watermark before adding a recurring Airflow schedule, otherwise each scheduled run can extract the full source again.
