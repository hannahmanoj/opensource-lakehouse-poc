import json
import os

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    approx_count_distinct,
    col,
    dayofweek,
    hour,
    max as spark_max,
    min as spark_min,
    round as spark_round,
    sum as spark_sum,
    to_timestamp,
    unix_timestamp,
    when,
    xxhash64,
)


CONTRACT_PATH = os.environ.get(
    "TAXI_DATA_CONTRACT",
    "/opt/project/domains/transport/taxi/contracts/taxi.contract.json",
)
RAW_ICEBERG_LOCATION = os.environ.get(
    "TAXI_RAW_ICEBERG_LOCATION",
    "s3://lakehouse/iceberg-tables/raw/taxi_trips",
)
CLEAN_ICEBERG_LOCATION = os.environ.get(
    "TAXI_CLEAN_ICEBERG_LOCATION",
    "s3://lakehouse/iceberg-tables/demo/taxi_trips_clean",
)
SUMMARY_ICEBERG_LOCATION = os.environ.get(
    "TAXI_SUMMARY_ICEBERG_LOCATION",
    "s3://lakehouse/iceberg-tables/demo/taxi_hourly_summary",
)
with open(CONTRACT_PATH, encoding="utf-8") as contract_file:
    CONTRACT = json.load(contract_file)


def fail_quality(check: str, detail: str) -> None:
    raise ValueError(f"DATA_CONTRACT_VIOLATION [{check}]: {detail}")


def validate_schema(dataframe, table_contract: dict, table_label: str) -> None:
    actual = {field.name: field.dataType.simpleString() for field in dataframe.schema}
    missing = sorted(set(table_contract["requiredColumns"]) - set(actual))
    if missing:
        fail_quality(
            f"{table_label}.schema",
            f"missing required columns: {missing}; actual columns: {sorted(actual)}",
        )

    incompatible = {
        name: {"expected": expected, "actual": actual[name]}
        for name, expected in table_contract["requiredColumns"].items()
        if actual[name] != expected
    }
    if incompatible:
        fail_quality(
            f"{table_label}.schema", f"incompatible column types: {incompatible}"
        )
    print(f"PASS data contract: {table_label} schema")


def publish_table(dataframe, table_name: str, location: str) -> None:
    if spark.catalog.tableExists(table_name):
        dataframe.writeTo(table_name).createOrReplace()
    else:
        dataframe.writeTo(table_name).tableProperty("location", location).create()
    print(f"Done: {table_name} published")


spark = (
    SparkSession.builder
    .appName("taxi-transform")
    .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
    .config("spark.sql.catalog.iceberg", "org.apache.iceberg.spark.SparkCatalog")
    .config("spark.sql.catalog.iceberg.catalog-impl", "org.apache.iceberg.rest.RESTCatalog")
    .config("spark.sql.catalog.iceberg.uri", "http://iceberg-rest:8181")
    .config("spark.sql.catalog.iceberg.io-impl", "org.apache.iceberg.aws.s3.S3FileIO")
    .config("spark.sql.catalog.iceberg.warehouse", "s3://lakehouse/")
    .config("spark.sql.catalog.iceberg.s3.endpoint", "http://minio:9000")
    .config("spark.sql.catalog.iceberg.s3.path-style-access", "true")
    .config("spark.sql.defaultCatalog", "iceberg")
    .config("spark.sql.iceberg.vectorization.enabled", "false")
    .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000")
    .config("spark.hadoop.fs.s3a.access.key", os.environ["AWS_ACCESS_KEY_ID"])
    .config("spark.hadoop.fs.s3a.secret.key", os.environ["AWS_SECRET_ACCESS_KEY"])
    .config("spark.hadoop.fs.s3a.path.style.access", "true")
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
    .config("spark.sql.legacy.timeParserPolicy", "LEGACY")
    .getOrCreate()
)

print(f"Using taxi data contract version {CONTRACT['contractVersion']}")
print("Step 1: Reading and validating raw Avro landing files from MinIO...")
raw_landing = spark.read.format("avro").load("s3a://lakehouse/raw/taxi_trips/")
validate_schema(raw_landing, CONTRACT["tables"]["raw"], "raw")

raw_count = raw_landing.count()
print(f"Raw landing row count: {raw_count}")
if raw_count < CONTRACT["quality"]["minimumRawRows"]:
    fail_quality("raw.minimum_rows", f"received {raw_count} rows")

raw_fingerprint = xxhash64(*[col(name) for name in raw_landing.columns])
distinct_raw_count = raw_landing.select(
    approx_count_distinct(raw_fingerprint, rsd=0.01).alias("distinct_rows")
).first()["distinct_rows"]
duplicate_ratio = max(0.0, (raw_count - distinct_raw_count) / raw_count)
print(
    f"Raw approximate-duplicate ratio: {duplicate_ratio:.4%} "
    f"(approximately {raw_count - distinct_raw_count} duplicate rows)"
)
if duplicate_ratio > CONTRACT["quality"]["maximumApproximateDuplicateRatio"]:
    fail_quality(
        "raw.exact_duplicates",
        f"ratio {duplicate_ratio:.4%} exceeds "
        f"{CONTRACT['quality']['maximumApproximateDuplicateRatio']:.2%}",
    )

raw = raw_landing.withColumn(
    "tpep_pickup_datetime", to_timestamp("tpep_pickup_datetime")
).withColumn("tpep_dropoff_datetime", to_timestamp("tpep_dropoff_datetime"))

print("Step 2: Cleaning and validating source rows...")
clean = raw.filter(
    (col("fare_amount") > 0)
    & (col("trip_distance") > 0)
    & (col("passenger_count") > 0)
    & (col("tpep_dropoff_datetime") > col("tpep_pickup_datetime"))
    & (
        (
            unix_timestamp("tpep_dropoff_datetime")
            - unix_timestamp("tpep_pickup_datetime")
        )
        / 60
        <= CONTRACT["quality"]["maximumTripDurationMinutes"]
    )
)
clean_count = clean.count()
rejected_ratio = (raw_count - clean_count) / raw_count
print(f"Rows after cleaning: {clean_count} (rejected {rejected_ratio:.4%})")
if rejected_ratio > CONTRACT["quality"]["maximumRejectedRowRatio"]:
    fail_quality(
        "clean.rejected_rows",
        f"ratio {rejected_ratio:.4%} exceeds "
        f"{CONTRACT['quality']['maximumRejectedRowRatio']:.2%}",
    )

print("Step 3: Computing and validating derived columns...")
enriched = (
    clean
    .withColumn(
        "trip_duration_minutes",
        spark_round(
            (unix_timestamp("tpep_dropoff_datetime") - unix_timestamp("tpep_pickup_datetime")) / 60,
            2,
        ),
    )
    .withColumn("fare_per_mile", spark_round(col("fare_amount") / col("trip_distance"), 2))
    .withColumn("pickup_hour", hour("tpep_pickup_datetime"))
    .withColumn("pickup_day_of_week", dayofweek("tpep_pickup_datetime"))
    .withColumn(
        "is_peak_hour",
        when(
            col("pickup_hour").between(7, 9) | col("pickup_hour").between(16, 19),
            True,
        ).otherwise(False),
    )
)
validate_schema(enriched, CONTRACT["tables"]["clean"], "clean")

quality = enriched.agg(
    spark_sum(
        when(
            col("tpep_pickup_datetime").isNull()
            | col("tpep_dropoff_datetime").isNull()
            | col("trip_duration_minutes").isNull()
            | col("fare_per_mile").isNull(),
            1,
        ).otherwise(0)
    ).alias("critical_nulls"),
    spark_min("trip_duration_minutes").alias("minimum_duration"),
    spark_max("trip_duration_minutes").alias("maximum_duration"),
    spark_min("fare_per_mile").alias("minimum_fare_per_mile"),
    spark_min("pickup_hour").alias("minimum_pickup_hour"),
    spark_max("pickup_hour").alias("maximum_pickup_hour"),
    spark_min("pickup_day_of_week").alias("minimum_pickup_day"),
    spark_max("pickup_day_of_week").alias("maximum_pickup_day"),
).first()

if quality["critical_nulls"]:
    fail_quality("clean.critical_nulls", f"found {quality['critical_nulls']} rows")
if not (
    CONTRACT["quality"]["minimumTripDurationMinutes"] <= quality["minimum_duration"]
    and quality["maximum_duration"] <= CONTRACT["quality"]["maximumTripDurationMinutes"]
):
    fail_quality(
        "clean.trip_duration",
        f"observed range {quality['minimum_duration']} to {quality['maximum_duration']} minutes",
    )
if quality["minimum_fare_per_mile"] < CONTRACT["quality"]["minimumFarePerMile"]:
    fail_quality("clean.fare_per_mile", f"minimum was {quality['minimum_fare_per_mile']}")
if not (
    0 <= quality["minimum_pickup_hour"] <= quality["maximum_pickup_hour"] <= 23
    and 1 <= quality["minimum_pickup_day"] <= quality["maximum_pickup_day"] <= 7
):
    fail_quality("clean.calendar_ranges", f"observed {quality.asDict()}")
print("PASS data contract: clean null, duration, fare, and calendar checks")

print("Step 4: Building and validating hourly summary...")
summary = (
    enriched.groupBy("pickup_hour", "pickup_day_of_week", "is_peak_hour")
    .agg(
        {
            "total_amount": "avg",
            "trip_distance": "avg",
            "trip_duration_minutes": "avg",
            "fare_amount": "count",
        }
    )
    .withColumnRenamed("avg(total_amount)", "avg_total_amount")
    .withColumnRenamed("avg(trip_distance)", "avg_trip_distance")
    .withColumnRenamed("avg(trip_duration_minutes)", "avg_duration_minutes")
    .withColumnRenamed("count(fare_amount)", "trip_count")
)
validate_schema(summary, CONTRACT["tables"]["summary"], "summary")

summary_count = summary.count()
grain_count = summary.select(*CONTRACT["tables"]["summary"]["grain"]).distinct().count()
if not CONTRACT["quality"]["minimumSummaryRows"] <= summary_count <= CONTRACT["quality"]["maximumSummaryRows"]:
    fail_quality("summary.row_count", f"received {summary_count} rows")
if grain_count != summary_count:
    fail_quality("summary.unique_grain", f"{summary_count - grain_count} duplicate grain rows")
summary_trip_count = summary.agg(spark_sum("trip_count").alias("trips")).first()["trips"]
if summary_trip_count != clean_count:
    fail_quality(
        "summary.reconciliation",
        f"summary has {summary_trip_count} trips but clean data has {clean_count}",
    )
print("PASS data contract: summary size, unique grain, and reconciliation checks")

print("Step 5: Publishing validated Iceberg tables...")
spark.sql("CREATE NAMESPACE IF NOT EXISTS iceberg.raw")
raw_table_name = CONTRACT["tables"]["raw"]["name"]
publish_table(raw_landing, raw_table_name, RAW_ICEBERG_LOCATION)
publish_table(
    enriched,
    CONTRACT["tables"]["clean"]["name"],
    CLEAN_ICEBERG_LOCATION,
)
publish_table(
    summary,
    CONTRACT["tables"]["summary"]["name"],
    SUMMARY_ICEBERG_LOCATION,
)
print(f"PASS data contract version {CONTRACT['contractVersion']}")
