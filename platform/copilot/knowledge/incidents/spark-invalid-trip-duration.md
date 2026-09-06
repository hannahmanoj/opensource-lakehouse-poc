---
incident_id: INC-SPARK-001
source_type: incident
component: spark
timestamp: "2026-09-03T09:25:45Z"
severity: error
title: Invalid taxi trip duration
---

## Symptoms

The Airflow task `transform_and_publish_iceberg` failed while processing the taxi dataset.

## Log evidence

```text
DATA_CONTRACT_VIOLATION [clean.trip_duration]:
observed range 0.02 to 119912.7 minutes
The taxi data contract allows a maximum trip duration of 1440 minutes.
```

## Root cause

At least one source record claimed that a taxi trip lasted approximately 83 days. The transformation initially checked that drop-off occurred after pickup, but it did not reject durations longer than 24 hours.

## Recommended checks

1. Check the maximum observed trip duration.
2. Compare it with maximumTripDurationMinutes.
3. Count how many records exceed 1440 minutes.
4. Confirm the rejected-row ratio remains within the contract limit.
5. Verify that invalid rows are removed before Iceberg publication.

## Unsafe actions to avoid

Do not increase the allowed duration to 119912.7 minutes only to make the pipeline pass. This would publish invalid data.

## Resolution
The cleaning filter was changed to reject trips longer than 1440 minutes. The resulting clean table had a maximum duration of 1439.97 minutes.