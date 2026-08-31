import argparse
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, to_date, to_timestamp


parser = argparse.ArgumentParser()
parser.add_argument("--date", required=True)
args = parser.parse_args()

source = Path(f"/opt/data/generated/industrial_energy_{args.date}.csv")
if not source.exists():
    raise FileNotFoundError(f"Generated source file does not exist: {source}")

spark = (
    SparkSession.builder
    .appName("industrial-energy-raw-landing")
    .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
    .config("spark.sql.catalog.iceberg", "org.apache.iceberg.spark.SparkCatalog")
    .config("spark.sql.catalog.iceberg.catalog-impl", "org.apache.iceberg.rest.RESTCatalog")
    .config("spark.sql.catalog.iceberg.uri", "http://iceberg-rest:8181")
    .config("spark.sql.catalog.iceberg.io-impl", "org.apache.iceberg.aws.s3.S3FileIO")
    .config("spark.sql.catalog.iceberg.warehouse", "s3://lakehouse/")
    .config("spark.sql.catalog.iceberg.s3.endpoint", "http://minio:9000")
    .config("spark.sql.catalog.iceberg.s3.path-style-access", "true")
    .config("spark.sql.defaultCatalog", "iceberg")
    .getOrCreate()
)

table = "iceberg.raw.industrial_energy_readings"
source_data = (
    spark.read.option("header", True).option("inferSchema", True).csv(str(source))
    .withColumn("reading_timestamp", to_timestamp("reading_timestamp"))
    .withColumn("reading_date", to_date("reading_timestamp"))
)

spark.sql("CREATE NAMESPACE IF NOT EXISTS iceberg.raw")
if spark.catalog.tableExists(table):
    source_data.writeTo(table).overwritePartitions()
else:
    source_data.writeTo(table).partitionedBy(col("reading_date")).create()

print(f"Landed {source_data.count()} rows in bronze table {table}")
spark.stop()
