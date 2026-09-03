import os

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, unix_timestamp, hour, dayofweek, when, round as spark_round
)

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

print("Step 1: Reading raw Avro landing files from MinIO...")

raw_landing = (
    spark.read
    .format("avro")
    .load("s3a://lakehouse/raw/taxi_trips/")
)

from pyspark.sql.functions import to_timestamp

raw_count = raw_landing.count()
print(f"Raw landing row count: {raw_count}")

print("Step 2: Publishing the source-shaped raw Iceberg table...")
spark.sql("CREATE NAMESPACE IF NOT EXISTS iceberg.raw")
raw_landing.writeTo("iceberg.raw.taxi_trips").createOrReplace()
print("Done: iceberg.raw.taxi_trips created")

raw = spark.table("iceberg.raw.taxi_trips").withColumn(
    "tpep_pickup_datetime", to_timestamp("tpep_pickup_datetime")
).withColumn(
    "tpep_dropoff_datetime", to_timestamp("tpep_dropoff_datetime")
)

print("Step 3: Cleaning invalid rows...")

clean = raw.filter(
    (col("fare_amount") > 0) &
    (col("trip_distance") > 0) &
    (col("passenger_count") > 0) &
    (col("tpep_dropoff_datetime") > col("tpep_pickup_datetime"))
)

clean_count = clean.count()
print(f"Rows after cleaning: {clean_count} (dropped {raw_count - clean_count})")

print("Step 4: Computing trip duration, fare-per-mile, peak-hour flag...")

enriched = (
    clean
    .withColumn(
        "trip_duration_minutes",
        spark_round(
            (unix_timestamp("tpep_dropoff_datetime") - unix_timestamp("tpep_pickup_datetime")) / 60, 2
        )
    )
    .withColumn(
        "fare_per_mile",
        spark_round(col("fare_amount") / col("trip_distance"), 2)
    )
    .withColumn("pickup_hour", hour("tpep_pickup_datetime"))
    .withColumn("pickup_day_of_week", dayofweek("tpep_pickup_datetime"))
    .withColumn(
        "is_peak_hour",
        when(
            (col("pickup_hour").between(7, 9)) | (col("pickup_hour").between(16, 19)),
            True
        ).otherwise(False)
    )
)

print("Step 5: Writing enriched table to Iceberg...")

enriched.writeTo("iceberg.demo.taxi_trips_clean").createOrReplace()

print("Done: iceberg.demo.taxi_trips_clean created")

print("Step 6: Building hourly summary aggregation...")

summary = (
    enriched.groupBy("pickup_hour", "pickup_day_of_week", "is_peak_hour")
    .agg(
        {"total_amount": "avg", "trip_distance": "avg", "trip_duration_minutes": "avg", "fare_amount": "count"}
    )
    .withColumnRenamed("avg(total_amount)", "avg_total_amount")
    .withColumnRenamed("avg(trip_distance)", "avg_trip_distance")
    .withColumnRenamed("avg(trip_duration_minutes)", "avg_duration_minutes")
    .withColumnRenamed("count(fare_amount)", "trip_count")
)

summary.writeTo("iceberg.demo.taxi_hourly_summary").createOrReplace()

print("Done: iceberg.demo.taxi_hourly_summary created")
