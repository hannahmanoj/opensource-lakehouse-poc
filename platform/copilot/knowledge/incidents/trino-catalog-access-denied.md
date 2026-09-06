---
incident_id: INC-TRINO-001
source_type: incident
component: trino
timestamp: "2026-09-01T06:28:46Z"
severity: error
title: Trino user could not access the Iceberg catalog
---

## Symptoms

A client connected successfully to Trino but could not list schemas or query Iceberg tables.

## Log evidence

```text
PERMISSION_DENIED
Access Denied: Cannot access catalog iceberg
```

An example failed query was:

```text
SELECT *
FROM iceberg.demo.taxi_hourly_summary
LIMIT 5;
```

## Root cause
The Trino access-control rules did not grant the connected user or group permission to access the iceberg catalog.

This was an authorization failure, not a network or MinIO failure.

## Recommended checks

1. Confirm the Trino username sent by the client.
2. Check which group contains the user.
3. Verify that Trino successfully loaded the group file.
4. Inspect the matching catalog access rule.
5. Confirm the rule permits the iceberg catalog.
6. Test with SHOW SCHEMAS FROM iceberg.

## Unsafe actions to avoid

Do not disable all Trino access control to fix one user.

Do not give every user unrestricted catalog access.

## Resolution

The appropriate user group and catalog rules were added, and Trino was restarted with readable access-control files.