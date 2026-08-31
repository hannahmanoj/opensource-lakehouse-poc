
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    avg,
    col,
    date_format,
    lit,
    max as spark_max,
    round as spark_round,
    sum as spark_sum,
    to_date,
    to_timestamp,
    when,
)


spark = (
    SparkSession.builder
    .appName("industrial-energy-transform")
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
    .config("spark.hadoop.fs.s3a.access.key", "admin")
    .config("spark.hadoop.fs.s3a.secret.key", "admin12345")
    .config("spark.hadoop.fs.s3a.path.style.access", "true")
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
    .getOrCreate()
)

source = "iceberg.raw.industrial_energy_readings"
print(f"Reading scheduled source data from bronze table {source}")
raw = spark.table(source)

clean = raw.filter(
    col("reading_timestamp").isNotNull()
    & col("estate_name").isNotNull()
    & (col("energy_kwh") >= 0)
    & (col("peak_demand_kw") >= 0)
    & col("power_factor").between(0, 1)
    & (col("renewable_kwh") >= 0)
    & (col("renewable_kwh") <= col("energy_kwh"))
    & (col("outage_minutes") >= 0)
)

enriched = (
    clean.withColumn("reading_date", to_date("reading_timestamp"))
    .withColumn("reading_hour", date_format("reading_timestamp", "H").cast("integer"))
    .withColumn(
        "renewable_share_pct",
        spark_round(col("renewable_kwh") / col("energy_kwh") * 100, 2),
    )
    .withColumn(
        "estimated_co2_kg",
        spark_round((col("energy_kwh") - col("renewable_kwh")) * lit(0.404), 2),
    )
    .withColumn(
        "efficiency_status",
        when(col("power_factor") >= 0.95, "Efficient")
        .when(col("power_factor") >= 0.90, "Monitor")
        .otherwise("Action required"),
    )
)

raw_count = raw.count()
clean_count = enriched.count()
if clean_count == 0:
    raise ValueError("Data-quality check failed: no valid industrial energy readings")

print(f"Data-quality result: {clean_count}/{raw_count} rows valid")
enriched.writeTo("iceberg.demo.industrial_energy_clean").createOrReplace()

summary = enriched.groupBy("estate_name", "reading_date").agg(
    spark_round(spark_sum("energy_kwh"), 2).alias("total_energy_kwh"),
    spark_round(spark_max("peak_demand_kw"), 2).alias("peak_demand_kw"),
    spark_round(avg("power_factor"), 3).alias("avg_power_factor"),
    spark_round(spark_sum("renewable_kwh"), 2).alias("renewable_energy_kwh"),
    spark_round(avg("renewable_share_pct"), 2).alias("avg_renewable_share_pct"),
    spark_round(spark_sum("estimated_co2_kg"), 2).alias("estimated_co2_kg"),
    spark_sum("outage_minutes").cast("integer").alias("outage_minutes"),
)

summary.writeTo("iceberg.demo.industrial_energy_daily_summary").createOrReplace()
print("Published industrial_energy_clean and industrial_energy_daily_summary")

spark.stop()
