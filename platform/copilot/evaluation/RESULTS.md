# Evaluation results

Run date: 2026-09-08

| Metric | Result |
|---|---:|
| Questions | 25 |
| Recall@5 | 100% |
| Mean Reciprocal Rank | 1.00 |
| Classification accuracy | 72% |
| Citation validity | 100% |
| Abstention accuracy | 72% |

Retrieval located the expected source in first position for all 21 questions
that named an expected source. Every returned citation belonged to the evidence
retrieved for that question.

## Failures to address

Classification mismatches:

- `spark-duration-002`, `nifi-duplicate-002`, `iceberg-metadata-002`, and
  `trino-access-002` were classified as `unknown` instead of incidents.
- `docs-permission-001` was classified as an incident instead of access control.
- `ops-minio-004` was classified as `unknown` instead of a checklist.
- `missing-delta-001` was classified as access control instead of documentation.

Abstention mismatches:

- Four incident paraphrases classified as `unknown` bypassed the incident-log
  requirement and answered from historical documents.
- The Trino permission documentation question was treated as an incident and
  unnecessarily requested a timestamped log.
- One Iceberg table-health answer set its own insufficient-evidence flag even
  though the deterministic sufficiency gate passed.
- The unsupported Arabic Kafka question incorrectly answered with unrelated
  NiFi evidence. Arabic behavior must not be presented as production-ready.

## Manual review required

The generated answers and expected facts are stored together in `report.json`.
A human reviewer must fill in each `manual_review.correct`,
`manual_review.grounded`, and `manual_review.notes` value. These fields remain
`null` intentionally; Qwen did not grade its own output.
