---
incident_id: INC-NIFI-001
source_type: incident
component: nifi
timestamp: "2026-09-03T08:57:00Z"
severity: error
title: NiFi loaded the taxi batch twice
---

## Symptoms

The taxi raw-data quality check failed after NiFi uploaded 44 Avro objects instead of the expected 22 objects.

## Log evidence

```text
Raw landing row count: 21813716
Raw approximate-duplicate ratio: 49.8996%
DATA_CONTRACT_VIOLATION: duplicate ratio exceeds 2.00%
```

## Root cause

QueryDatabaseTable ran more than once against the same source range. Each execution extracted approximately 10.9 million rows and created another 22-file batch.

The processor did not have a reliable incremental watermark or batch identifier preventing the same source records from being uploaded again.

## Recommended checks

1. Stop QueryDatabaseTable before retrying the DAG.
2. Inspect the NiFi success queue.
3. Count objects under raw/taxi_trips.
4. Compare object creation timestamps.
5. Confirm the processor's maximum-value columns or source watermark.
6. Quarantine the duplicate batch before rerunning the transformation.

## Unsafe actions to avoid

Do not increase the duplicate threshold to approximately 50 percent. This would allow doubled totals into Iceberg and Power BI.

Do not delete all objects from the raw prefix without identifying the duplicate batch.

## Resolution

The duplicate batch was removed from the active raw prefix, leaving one 22-file batch with approximately 10.9 million rows.