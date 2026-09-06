---
incident_id: INC-ICEBERG-001
source_type: incident
component: iceberg
timestamp: "2026-09-03T09:29:42Z"
severity: critical
title: Iceberg catalog referenced missing metadata
---

## Symptoms

Spark passed the data-quality checks but failed while publishing an Iceberg table.

## Log evidence

```text
NotFoundException: Location does not exist:
s3://lakehouse/raw/taxi_trips/metadata/00001.metadata.json
```

## Root cause
The NiFi raw landing prefix and the Iceberg-managed table initially used the same MinIO path:

```text
s3://lakehouse/raw/taxi_trips
```

When landing files were cleaned up, Iceberg metadata under the same path was also removed. The catalog still referenced metadata that no longer existed.

## Recommended checks

1. Inspect the location registered in the Iceberg REST catalog.
2. Verify that the referenced metadata JSON exists in MinIO.
3. Confirm that landing and managed-table locations are different.
4. Check whether the problem affects other table registrations.
5. Repair stale catalog registrations without purging valid source objects.

## Unsafe actions to avoid

Do not purge an Iceberg table until its registered location and remaining objects have been inspected.

Do not mix externally managed landing files with Iceberg metadata and data files under the same prefix.

## Resolution

The landing prefix remained:

```text
s3://lakehouse/raw/taxi_trips
```

The managed Iceberg table moved to:

```text
s3://lakehouse/iceberg-tables/raw/taxi_trips
```