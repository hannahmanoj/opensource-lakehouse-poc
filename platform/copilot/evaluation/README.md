# Copilot evaluation and Day 2 rehearsal

The evaluation separates retrieval quality from generated prose. It uses 25
version-controlled questions and never asks Qwen to grade its own answers.

## Clean-start rehearsal

From the repository root:

```bash
docker compose up -d
curl http://localhost:8100/health
docker compose exec copilot-db pg_isready -U copilot -d lakehouse_copilot
docker compose exec copilot-api python -m app.ingest
```

Run the fast retrieval/classification evaluation first:

```bash
docker compose exec copilot-api python /evaluation/evaluate.py --retrieval-only
```

Run the complete evaluation, including Qwen answers, citations, and
abstention. This is slower because it calls the local model:

```bash
docker compose exec copilot-api python /evaluation/evaluate.py
```

Open `http://localhost:3000/copilot.html` and rehearse:

1. Ask `What should I check before restarting MinIO?` and expand its citation.
2. Ask `Why did the Spark ingestion fail?` and show the missing-log refusal.
3. Ask `Which Iceberg tables may have too many small files?` and compare the
   answer with `POST /api/copilot/live/iceberg` using `table_health`.
4. Open `evaluation/report.json`. Manually fill each generated answer's
   `manual_review.correct`, `manual_review.grounded`, and `notes` values.

## Metric meanings

- **Recall@5:** fraction of expected sources found in the first five results.
- **Mean Reciprocal Rank:** rewards placing the first correct source near rank 1.
- **Classification accuracy:** fraction assigned the expected question class.
- **Citation validity:** citations are retrieved IDs; non-refusals cite evidence.
- **Abstention accuracy:** fraction that refuse exactly when expected.

## Honest limitations

- Incident documents are synthetic ground truth, not production telemetry.
- Live collectors exist, but `/ask` does not yet orchestrate Airflow task logs or
  Iceberg metrics into generated answers. Incident questions therefore refuse
  when a current timestamped log is required.
- Docker Compose is the POC runtime, not a highly available architecture.
- Production authentication, SSO, and Madayn RBAC integration are not present.
- The copilot is read-only and cannot restart or modify infrastructure.
- `X-Trino-User` identifies the POC caller but is not production authentication.
- The small knowledge pack cannot establish production retrieval quality.
- Arabic retrieval and answer quality require a dedicated evaluation set before
  making production claims.
- Manual review is required for answer correctness and groundedness.
