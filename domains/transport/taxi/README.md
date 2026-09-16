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

## data contract and quality gates

[`contracts/taxi.contract.json`](contracts/taxi.contract.json) is the
machine readable agreement for this data product. It records ownership,
required columns and Spark types, table grain, and accepted quality thresholds
changes to a column or threshold should be reviewed with the contract in git.

the spark job validates the complete candidate data before replacing any
Iceberg table.
it fails with `DATA_CONTRACT_VIOLATION` when it finds:

- missing or incompatible required columns;
- an empty raw delivery or more than 2% approximate duplicate rows;
- more than 10% rejected source rows;
- critical nulls or invalid duration, fare, hour, and weekday ranges;
- duplicate hourly-summary grain or a summary that does not reconcile to the
  cleaned row count.

after publication, airflow independently queries all three tables through
trino. these checks verify the consumer-facing tables, not just spark's
in-memory data. a failed check blocks the DAG and leaves a searchable failure
message in the airflow task log.

the duplicate gate uses bounded-memory row fingerprints so it scales to large
deliveries. tt is expected to reject the current doubled raw landing
set until duplicate batches are removed or ingestion uses unique incremental
batch paths.

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
