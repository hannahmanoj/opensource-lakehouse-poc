from pyspark.sql import SparkSession

spark = (
    SparkSession.builder
    .appName("genre-summary")
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
    .getOrCreate()
)

df = spark.table("iceberg.demo.artists")

summary = (
    df.groupBy("primary_genre")
    .agg({"total_streams_millions": "avg", "artist_name": "count"})
    .withColumnRenamed("avg(total_streams_millions)", "avg_total_streams")
    .withColumnRenamed("count(artist_name)", "artist_count")
)

summary.writeTo("iceberg.demo.genre_summary").createOrReplace()

print("Done: iceberg.demo.genre_summary created")