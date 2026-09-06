---
incident_id: RUNBOOK-ICEBERG-002
source_type: runbook
component: iceberg
timestamp: "2026-09-03T00:00:00Z"
severity: warning
title: Detecting excessive small files in Iceberg tables
---

## Symptoms

An Iceberg table contains many data files that are small relative to the expected target file size. Trino queries may spend excessive time opening files and reading metadata.

## Log evidence

Small-file analysis should inspect the Iceberg metadata table:

```sql
SELECT
    count(*) AS file_count,
    avg(file_size_in_bytes) AS average_file_size,
    count_if(file_size_in_bytes < 16777216) AS files_below_16_mb
FROM iceberg.demo."taxi_trips_clean$files";
```

A high number or percentage of files below 16 MB indicates that compaction may be useful. The threshold is a POC policy and should be adjusted for production workloads.

## Root cause

Small files can be created by frequent micro-batches, excessive Spark partitions, small ingestion batches, or repeated writes.

## Recommended checks

1. Query the table's $files metadata table.
2. Count all active data files.
3. Calculate average and median file sizes.
4. Count files below the configured small-file threshold.
5. Check whether recent jobs created many small commits.
6. Compare file count with table size and query behaviour.
7. Review Spark partitioning before performing compaction.

## Unsafe actions to avoid

Do not delete Parquet files directly from MinIO.
Do not assume that every small file requires immediate compaction.
Do not execute a rewrite while another job is modifying the same table.

## Resolution

Use an approved Iceberg data-file rewrite procedure after confirming that small files are affecting the table. Recheck file statistics after compaction.