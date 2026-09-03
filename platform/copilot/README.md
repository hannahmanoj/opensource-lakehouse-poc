# lakehouse operations copilot

this copilot is a read-only assistant that helps engineers investigate problems in the Madayn lakehouse proof of concept. 
it retrieves operational evidence and explains what it found, but it does not modify the platform (may happen if i have time)

## supported demo questions

1. why did yesterday's spark ingestion fail?
2. which iceberg tables have too many small files?
3. what does this trino error mean?
4. what should i check before restarting minio?
5. show the evidence supporting your recommendations

## supported components

- airflow DAG runs, task states, retries, and logs
- spark ingestion and transformation logs
- trino query failures and diagnostic metadata
- iceberg table, snapshot, and data-file metadata
- minIO health information and operational runbooks

## read-only boundary

the Copilot may search documentation, retrieve logs, inspect health information, and execute predefined read-only diagnostic queries. 
every diagnosis or recommendation should cite the evidence used

the copilot must not change data, configuration, services, access policies, or workflow state

## non-goals for the POC right now

- automatic repair or remediation
- starting, stopping, or restarting services
- unrestricted shell-command execution
- arbitrary SQL generated or executed by the model
- production authentication, SSO, or complete role-based access control
- production-scale availability, monitoring, or log ingestion
- a general-purpose assistant for every data-platform operation

these capabilities can be evaluated after the read-only, evidence-grounded workflow has been demonstrated and tested.

## scope checkpoint

- [x] the five supported demo questions are documented
- [x] read-only behaviour is documented
- [x] supported platform components are documented
- [x] features that will not be built during the POC are documented
