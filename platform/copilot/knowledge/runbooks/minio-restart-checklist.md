---
incident_id: RUNBOOK-MINIO-001
source_type: runbook
component: minio
timestamp: "2026-09-03T00:00:00Z"
severity: warning
title: Checks required before restarting MinIO
---

## Symptoms

An engineer is considering restarting MinIO because Spark, Trino, Iceberg, or NiFi cannot access object storage.

## Log evidence

Relevant symptoms may include:

```text
Connection refused
S3Exception
Unable to execute HTTP request
Location does not exist
Connection reset
```

These errors do not always mean MinIO itself must be restarted.

## Root cause

Possible causes include:
1. The MinIO container is unhealthy.
2. Docker networking cannot resolve minio.
3. Incorrect S3 credentials are configured.
4. A bucket or object path does not exist.
5. Iceberg references deleted metadata.
6. MinIO is healthy but a dependent service has stale connections.

## Recommended checks

1. Check the MinIO container status.
2. Read recent MinIO logs.
3. Check disk availability.
4. Confirm the lakehouse bucket exists.
5. Test the MinIO health endpoint.
6. Confirm no Spark or Iceberg commit is running.
7. Check dependent Airflow and NiFi tasks.
8. Record the current failure evidence before restarting.
9. Confirm the persistent MinIO volume is attached.

## Unsafe actions to avoid

Do not remove the minio-data Docker volume.
Do not run docker compose down -v.
Do not delete Iceberg metadata manually.
Do not restart MinIO during an active Iceberg commit unless the impact is understood.

## Resolution
Restart only the MinIO container after evidence has been collected and active writes have been ruled out:

```text
docker compose restart minio
```

Afterward, verify MinIO health and run read-only Trino checks before retrying failed workflows.