# lakehouse operations copilot

the Lakehouse Operations Copilot is a read-only assistant for investigating the
Madayn lakehouse proof of concept. It retrieves operational evidence, explains
what it found, recommends checks, and cites its sources. It does not modify data
or operate platform services.

## how it works

```text
question
  -> classify the investigation
  -> retrieve keyword + semantic matches from PostgreSQL/pgvector
  -> check whether the evidence is sufficient
  -> ask the local Ollama model to produce a grounded answer
  -> validate citations and return findings and recommended checks
```

The knowledge base contains version-controlled Markdown incidents and runbooks
under `knowledge/`. `app.ingest` splits these documents into chunks, creates
BGE-M3 embeddings, and stores them in PostgreSQL with pgvector. Retrieval uses
both semantic similarity and PostgreSQL full-text search. The model is used to
explain retrieved evidence; it is not allowed to invent platform state.

The portal presents the result as:

1. a direct answer;
2. likely causes or findings;
3. recommended checks;
4. expandable supporting evidence.

When the available evidence cannot support a reliable answer, the API returns
low confidence, identifies the missing evidence, and avoids claiming certainty.

## components

| path or service | purpose |
|---|---|
| `api/app/` | FastAPI application, retrieval, collectors and LLM integration |
| `knowledge/incidents/` | example incident evidence used by the POC |
| `knowledge/runbooks/` | operational guidance indexed by the retriever |
| `migrations/` | PostgreSQL and pgvector schema created for a new DB volume |
| `evaluation/` | version-controlled questions, evaluator and reports |
| `copilot-db` | PostgreSQL 16 with pgvector |
| `copilot-api` | API exposed on `http://localhost:8100` |
| portal | full Copilot UI at `http://localhost:3000/copilot.html` |

## setup

Copy the example environment file and replace all demo secrets:

```bash
cp .env.example .env
```

The default LLM provider is Ollama running on the host. Install Ollama and pull
the configured model before starting the Copilot:

```bash
ollama pull qwen3:8b
docker compose up -d --build copilot-db copilot-api portal
```

Index the bundled evidence after the first startup:

```bash
docker compose exec copilot-api python -m app.ingest
```

The ingest command is safe to repeat: unchanged chunks are skipped by their
content hash. Run it again after adding or editing knowledge documents. The
first run may take longer because the embedding model must be downloaded.

Verify the services:

```bash
curl http://localhost:8100/health
docker compose exec copilot-db pg_isready -U copilot -d lakehouse_copilot
curl http://localhost:11434/api/tags
```

Then open `http://localhost:3000/copilot.html`.

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
- NiFi incident and ingestion evidence

The API also provides predefined live collectors for Airflow DAG runs, Trino
diagnostics, Iceberg metadata, and platform service health. Live collectors are
read-only and are separate from the normal knowledge-base retrieval flow.

## asking through the API

Ask an evidence-grounded question:

```bash
curl --request POST http://localhost:8100/api/copilot/ask \
  --header 'Content-Type: application/json' \
  --data '{"question":"What should I check before restarting MinIO?","component":"minio"}'
```

Inspect retrieval results without generating an answer:

```bash
curl --request POST http://localhost:8100/api/copilot/search \
  --header 'Content-Type: application/json' \
  --data '{"question":"Why did the Spark ingestion fail?","component":"spark"}'
```

Optional request filters are `component`, `severity`, `from_time`, and
`to_time`. Supported components are Airflow, Spark, Trino, Iceberg, MinIO, and
NiFi. Timestamps use ISO 8601 format.

Live diagnostic routes are:

- `GET /api/copilot/live/airflow/dag-runs?limit=10`
- `GET /api/copilot/live/trino/cluster_overview`
- `GET /api/copilot/live/trino/recent_failures`
- `POST /api/copilot/live/iceberg` with a table and `files`, `snapshots`, or
  `table_health` operation
- `GET /api/copilot/live/health` with an optional `service` query parameter

## configuration

The main `.env` settings are:

| variable | default or purpose |
|---|---|
| `COPILOT_DATABASE_URL` | connection to the Copilot PostgreSQL database |
| `COPILOT_LLM_PROVIDER` | `ollama` |
| `COPILOT_LLM_BASE_URL` | `http://host.docker.internal:11434` |
| `COPILOT_LLM_MODEL` | `qwen3:8b` |
| `COPILOT_LLM_TEMPERATURE` | `0.1` for restrained answers |
| `COPILOT_LLM_TIMEOUT_SECONDS` | model request timeout, default `120` |
| `COPILOT_EMBEDDING_MODEL` | `BAAI/bge-m3` |
| `COPILOT_AIRFLOW_URL` | internal Airflow API URL |
| `COPILOT_TRINO_URL` | internal Trino URL |
| `COPILOT_TRINO_USER` | read-only POC Trino identity |
| `COPILOT_MAX_LOG_BYTES` | maximum task-log content collected |
| `COPILOT_SMALL_FILE_THRESHOLD_BYTES` | Iceberg small-file threshold |

## read-only boundary

the Copilot may search documentation, retrieve logs, inspect health information,
and execute predefined read-only diagnostic queries. Every diagnosis or
recommendation should cite the evidence used.

the Copilot must not change data, configuration, services, access policies, or
workflow state. Recommendations are instructions for a human; they do not mean
that the Copilot performed the action.

## adding evidence

Add a Markdown file below `knowledge/incidents/` or `knowledge/runbooks/`. Each
document must begin with YAML front matter containing:

- `incident_id`
- `source_type`
- `component`
- `timestamp`
- `severity`
- `title`

After changing the knowledge pack, run the ingest command again. Avoid placing
passwords, tokens, personal information, or unrestricted production logs in the
knowledge directory.

## tests and evaluation

Run the unit tests inside the API container:

```bash
docker compose exec copilot-api python -m unittest discover -s tests
```

Run retrieval-only evaluation first, then the complete model evaluation:

```bash
docker compose exec copilot-api python /evaluation/evaluate.py --retrieval-only
docker compose exec copilot-api python /evaluation/evaluate.py
```

See [the evaluation guide](evaluation/README.md) for metric definitions, manual
review, and the Day 2 rehearsal.

## troubleshooting

- If the UI opens but produces no useful evidence, run `python -m app.ingest`
  inside `copilot-api` and check its output.
- If answer generation fails or times out, confirm Ollama is running, verify
  `qwen3:8b` appears in `http://localhost:11434/api/tags`, and check
  `docker compose logs copilot-api`.
- If live evidence fails, confirm the target service is running and that its
  internal URL and credentials are configured in Docker Compose.
- If database startup fails after changing credentials, remember that PostgreSQL
  initialization variables only apply to a new database volume. Inspect the
  existing configuration before removing any volume.

## non-goals for the POC right now

- automatic repair or remediation
- starting, stopping, or restarting services
- unrestricted shell-command execution
- arbitrary SQL generated or executed by the model
- production authentication, SSO, or complete role-based access control
- production-scale availability, monitoring, or log ingestion
- a general-purpose assistant for every data-platform operation

these capabilities can be evaluated after the read-only, evidence-grounded
workflow has been demonstrated and tested.

## scope checkpoint

- [x] the five supported demo questions are documented
- [x] read-only behaviour is documented
- [x] supported platform components are documented
- [x] features that will not be built during the POC are documented
