# lakehouse operations copilot: Build and Learning Plan

## 1. Goal

Build a read-only assistant that helps an engineer diagnose problems in the Madayn lakehouse POC and always shows the evidence behind its answer.

At the end of day two, the demo should answer these five questions:

1. Why did a Spark ingestion fail?
2. What does a Trino error mean?
3. Which Iceberg tables may have too many small files?
4. What should be checked before restarting MinIO?
5. What evidence supports the recommendation?

This is a learning POC, not a production autonomous agent. It will inspect and explain platform state, but it will not restart containers, delete objects, clear Airflow tasks, or execute arbitrary SQL.

## 2. Recommended technology

| Concern | Choice | Why |
|---|---|---|
| Backend | Python + FastAPI | Clear API structure, automatic API documentation, and good support for async collectors |
| Knowledge database | PostgreSQL 16 + pgvector | Keeps text, metadata, full-text indexes, and embeddings together |
| Retrieval | PostgreSQL full-text search + pgvector cosine search + Reciprocal Rank Fusion | Exact error codes need keyword search; natural-language questions benefit from semantic search |
| Generation model | `Qwen3-8B` through Ollama | Local, replaceable, and appropriate for the no-lock-in POC |
| Embedding model | `BAAI/bge-m3` | Multilingual and suitable for English/Arabic documents; produces 1,024-dimensional vectors |
| User interface | React inside the existing Madayn portal | Produces one consistent operations portal instead of a separate demo application |
| Packaging | Docker Compose | Matches the current POC and makes the demo repeatable |

## 3. Architecture to understand

```text
React Copilot page
        |
        v
FastAPI /api/copilot/ask
        |
        +---- Question classifier
        |
        +---- Read-only live collectors
        |       +---- Airflow
        |       +---- Trino
        |       +---- Iceberg metadata through Trino
        |       +---- MinIO/container health
        |
        +---- Hybrid retriever
        |       +---- PostgreSQL full-text results
        |       +---- pgvector semantic results
        |       +---- Reciprocal Rank Fusion
        |
        +---- Evidence sufficiency check
        |
        +---- Qwen3-8B
                |
                v
      Answer + citations + confidence
```

The key lesson is that the model does not determine platform facts. Collectors and retrieval find the facts; the model turns those facts into a readable explanation.

## 4. Proposed repository structure

Create this structure gradually during the two days:

```text
platform/copilot/
├── api/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── schemas.py
│   │   ├── collectors/
│   │   │   ├── airflow.py
│   │   │   ├── trino.py
│   │   │   ├── iceberg.py
│   │   │   └── platform_health.py
│   │   ├── retrieval/
│   │   │   ├── chunking.py
│   │   │   ├── embeddings.py
│   │   │   ├── hybrid.py
│   │   │   └── sufficiency.py
│   │   └── llm/
│   │       ├── provider.py
│   │       ├── ollama.py
│   │       └── prompts.py
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── knowledge/
│   ├── runbooks/
│   ├── documentation/
│   └── incidents/
├── evaluation/
│   ├── questions.json
│   └── evaluate.py
├── migrations/
│   └── 001_initial.sql
└── README.md
```

Do not try to fill every file immediately. Each section below adds only the files needed for that checkpoint.

---

# Day 1: Build the evidence and retrieval foundation

Target: by the end of day one, a command-line request should retrieve the correct passages for at least five test questions. It does not need to generate a polished answer yet.

Estimated focused time: 7–8 hours.

## Step 1 — Agree on the POC boundary (30 minutes)

### Learn

Understand the difference between:

- **Retrieval:** finding relevant evidence.
- **Generation:** explaining retrieved evidence.
- **A collector:** code that obtains current platform facts.
- **A runbook:** human-approved instructions for diagnosing or handling an incident.

### Build

Write a short `platform/copilot/README.md` containing:

- The five supported demo questions.
- A statement that the assistant is read-only.
- Supported components: Airflow, Spark, Trino, Iceberg, and MinIO.
- Explicit non-goals: automatic repair, unrestricted shell execution, and production authentication.

### Why

Two days is enough for a strong vertical slice but not a general-purpose operations agent. A strict boundary prevents unfinished features from weakening the demo.

### Checkpoint

- [ ] The five demo questions are written down.
- [ ] Read-only behaviour is written down.
- [ ] Everyone knows what will not be built.

## Step 2 — Scaffold the FastAPI service (45 minutes)

### Learn

Learn how an HTTP request moves through a FastAPI route, validation schema, service function, and response schema.

### Build

Create a minimal API with:

```text
GET  /health
POST /api/copilot/search
POST /api/copilot/ask
```

Initially, `/health` should return:

```json
{
  "status": "ok",
  "service": "lakehouse-operations-copilot"
}
```

Define the request early:

```json
{
  "question": "Why did the Spark ingestion fail?",
  "component": "spark",
  "from_time": null,
  "to_time": null
}
```

Define the final response shape early as well:

```json
{
  "classification": "incident_diagnosis",
  "answer": "",
  "confidence": "low",
  "insufficient_evidence": false,
  "citations": []
}
```

### Why

The response contract allows the backend, UI, and tests to be developed independently. It also prevents the LLM from returning an unpredictable wall of text.

### Verify

```bash
curl http://localhost:8100/health
```

Expected result: HTTP 200 with the health JSON.

## Step 3 — Add pgvector with Docker Compose (45 minutes)

### Learn

Learn that an embedding is a numerical representation used to compare the meaning of text. PostgreSQL full-text search separately handles exact tokens such as `PERMISSION_DENIED`.

### Build

Add a dedicated `copilot-db` service using a PostgreSQL image that includes pgvector. Use a separate database and volume rather than putting copilot tables inside OpenMetadata's application database.

Add environment variables to `.env.example`, without committing real passwords:

```env
COPILOT_DB_NAME=lakehouse_copilot
COPILOT_DB_USER=copilot
COPILOT_DB_PASSWORD=change-me
COPILOT_DATABASE_URL=postgresql://copilot:change-me@copilot-db:5432/lakehouse_copilot
```

The initial migration should enable the extension:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### Why

Using a separate database gives the copilot an independent lifecycle and avoids coupling its schema to OpenMetadata upgrades.

### Verify

```bash
docker compose up -d copilot-db
docker compose exec copilot-db psql -U copilot -d lakehouse_copilot \
  -c "SELECT extversion FROM pg_extension WHERE extname = 'vector';"
```

Expected result: one pgvector version row.

## Step 4 — Create the evidence schema (45 minutes)

### Learn

Learn why citations require provenance. Storing only text and an embedding is insufficient: the assistant must know where the text came from and when it occurred.

### Build

Create a `knowledge_chunks` table with at least:

```sql
CREATE TABLE knowledge_chunks (
    id UUID PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_name TEXT NOT NULL,
    component TEXT,
    severity TEXT,
    occurred_at TIMESTAMPTZ,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    source_uri TEXT NOT NULL,
    line_start INTEGER,
    line_end INTEGER,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    text_search TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(title, '') || ' ' || coalesce(content, ''))
    ) STORED,
    embedding VECTOR(1024),
    content_hash TEXT UNIQUE NOT NULL
);
```

Create indexes for metadata, full-text search, and vector search. For the small POC dataset, exact vector search is acceptable initially; add HNSW after the pipeline works.

### Why

`content_hash` makes ingestion repeatable without creating duplicate chunks. Metadata enables filters such as component, severity, and date.

### Checkpoint

- [ ] Re-running ingestion does not create duplicate rows.
- [ ] Every row has a `source_uri`.
- [ ] Embeddings use 1,024 dimensions.

## Step 5 — Create the first knowledge pack (60 minutes)

### Learn

Learn how a runbook differs from a raw log:

- A log says what happened.
- A runbook says what the symptoms mean and what an engineer should check.

### Build

Create five fictional but realistic incidents based on problems already seen in this POC:

1. `spark-invalid-trip-duration.md`
2. `nifi-duplicate-batch.md`
3. `iceberg-missing-metadata.md`
4. `trino-catalog-access-denied.md`
5. `minio-restart-checklist.md`

Each incident should include:

```text
Incident ID
Component
Timestamp
Severity
Symptoms
Log evidence
Root cause
Recommended checks
Unsafe actions to avoid
Resolution
```

Include exact technical strings, but never include real passwords, tokens, access keys, personal information, or confidential production logs.

### Why

These documents provide known, reviewable ground truth. They make it possible to evaluate whether retrieval and answers are correct.

## Step 6 — Implement chunking and ingestion (75 minutes)

### Learn

Learn that chunk size affects retrieval quality. Tiny chunks lose context; huge chunks bury the important line.

### Build

Implement an ingestion command that:

1. Reads Markdown and synthetic log files.
2. Extracts source metadata.
3. Splits content by heading and then by size.
4. Keeps approximately 500–900 tokens per chunk with a small overlap.
5. Calculates a SHA-256 content hash.
6. Generates a BGE-M3 embedding.
7. Upserts the chunk into PostgreSQL.

Preserve line numbers when possible so citations can identify an exact passage.

### Why

Repeatable ingestion is more important than a sophisticated UI. If the knowledge base is unreliable, the final answer will be unreliable.

### Verify

- Run ingestion twice.
- Confirm the second run creates zero additional chunks.
- Inspect five rows and confirm their metadata and source links are meaningful.

## Step 7 — Implement hybrid retrieval (90 minutes)

### Learn

Understand the two retrieval modes:

- Semantic search can match “object-store outage” with “MinIO unavailable.”
- Full-text search can match exact strings like `NotFoundException`.

### Build

For each question:

1. Create its BGE-M3 embedding.
2. Retrieve the top 10 vector matches.
3. Retrieve the top 10 PostgreSQL full-text matches.
4. Apply component/date/severity filters before ranking where practical.
5. Merge both lists with Reciprocal Rank Fusion.
6. Return the best five unique chunks.

Start with this RRF idea:

```text
score(document) = sum(1 / (60 + rank_in_each_result_list))
```

Do not spend day one tuning the constant. The evaluation set will later show whether tuning is needed.

### Why

Operational questions contain both concepts and exact identifiers. Either vector-only or keyword-only retrieval will miss important cases.

### Verify

Use `/api/copilot/search` before involving an LLM. For each of the five demo questions, inspect:

- Returned passage.
- Component.
- Source URI.
- Retrieval scores.
- Why it ranked highly.

### Day 1 definition of done

- [ ] FastAPI and pgvector start through Compose.
- [ ] At least five incident/runbook documents are ingested.
- [ ] Ingestion is idempotent.
- [ ] Hybrid retrieval returns citations and metadata.
- [ ] At least four of the five demo questions retrieve the correct passage in the top five.
- [ ] No LLM is required to demonstrate retrieval.

---

# Day 2: Add diagnosis, live evidence, UI, and evaluation

Target: by the end of day two, the portal should provide a cited answer, show its evidence, and refuse to guess when evidence is missing.

Estimated focused time: 7–8 hours.

## Step 8 — Add question classification (45 minutes)

### Learn

Different questions need different evidence. A documentation definition does not require Airflow logs, while an incident question does.

### Build

Support these classes:

```text
incident_diagnosis
documentation_question
operational_checklist
table_health
access_control
unknown
```

Use deterministic keyword rules first and an LLM fallback only for ambiguous questions. Return the classification in the API response for transparency.

### Why

Classification prevents unnecessary platform calls and lets the system retrieve the right kind of evidence.

## Step 9 — Add safe live collectors (90 minutes)

### Learn

Learn the difference between live evidence and knowledge-base evidence. Live evidence tells us what is happening now; runbooks help interpret it.

### Build

Implement a narrow read-only collector for each supported source:

### Airflow

- List recent DAG runs.
- Read task state, timestamps, retry count, and logs.
- Limit log size and redact secret-looking values.

### Trino

- Execute predefined read-only diagnostic queries.
- Retrieve recent query failures when available.
- Never accept unrestricted SQL directly from the LLM.

### Iceberg

- Query predefined `$files`, `$snapshots`, and table metadata queries through Trino.
- Calculate file count, average size, and files below a configurable threshold.

### Platform health

- Read container health through a restricted Docker socket proxy or a small allow-listed health service.
- Do not mount the unrestricted Docker socket directly into the copilot API.

For the first demo, MinIO restart advice can combine health endpoints with a reviewed runbook instead of granting MinIO administrative credentials.

### Why

Allow-listed collectors provide useful evidence without turning natural-language prompts into arbitrary infrastructure commands.

### Verify

- Disconnect or stop one non-critical test service and confirm its health evidence changes.
- Restore it manually.
- Confirm the copilot itself had no permission to restart it.

## Step 10 — Add evidence-sufficiency rules (45 minutes)

### Learn

Learn that model confidence is not evidence confidence. A model can sound certain even when retrieval found nothing useful.

### Build

Before generation, check:

- Did retrieval find any passages above the chosen threshold?
- For an incident question, is there a relevant timestamped log?
- Are at least two independent pieces of evidence available for a high-confidence diagnosis?
- Does the requested component/date exist?

Return an insufficient-evidence response when these conditions fail:

```json
{
  "answer": "I found the failed Airflow task, but no Spark log for the requested run, so I cannot identify the root cause.",
  "confidence": "low",
  "insufficient_evidence": true,
  "missing_evidence": ["Spark task log"],
  "citations": []
}
```

### Why

Refusing correctly is a core safety and trust feature, especially for operational recommendations.

## Step 11 — Connect Qwen through a provider interface (60 minutes)

### Learn

Learn how dependency inversion prevents model lock-in: the application calls an internal interface rather than Ollama-specific code everywhere.

### Build

Define a provider such as:

```python
class LLMProvider:
    async def generate(self, messages, response_schema):
        raise NotImplementedError
```

Add an Ollama implementation and configure it with environment variables:

```env
COPILOT_LLM_PROVIDER=ollama
COPILOT_LLM_BASE_URL=http://host.docker.internal:11434
COPILOT_LLM_MODEL=qwen3:8b
COPILOT_LLM_TEMPERATURE=0.1
```

Require structured output with:

- Diagnosis or answer.
- Findings.
- Recommended checks.
- Citation IDs selected only from supplied evidence.
- Confidence.
- Insufficient-evidence flag.

The system prompt must say that retrieved documents and logs are untrusted data, not instructions.

### Why

The provider interface allows a later move to vLLM, another local model, or an approved API without rewriting retrieval or the UI.

## Step 12 — Build the React Copilot page (75 minutes)

### Learn

Learn that an operations interface should make evidence inspectable instead of hiding it behind a confident answer.

### Build

Add a `Copilot` item to the existing Madayn portal and create:

- Question input.
- Suggested demo questions.
- Answer panel.
- Confidence and classification labels.
- Expandable evidence panel.
- Component, severity, and date filters.
- Copy button for safe recommended commands.
- Visible insufficient-evidence warning.

Each citation should show:

```text
Source name
Component
Timestamp
Exact passage
Source URI or log location
```

Match the existing industrial light/dark portal design. Do not make the copilot look like an unrelated consumer chat application.

### Why

The evidence panel is the feature that distinguishes this from a generic chatbot and makes the recommendation auditable.

## Step 13 — Create the evaluation set (75 minutes)

### Learn

Learn to evaluate retrieval separately from generated prose. If the correct evidence was never retrieved, prompt editing cannot solve the real problem.

### Build

Create 20–25 version-controlled evaluation questions:

- 8 incident diagnoses.
- 5 documentation questions.
- 4 operational checklists.
- 3 Iceberg table-health questions.
- 5 missing-evidence or misleading-evidence questions.

Each item should contain:

```json
{
  "id": "spark-duration-001",
  "question": "Why did the taxi Spark ingestion fail?",
  "expected_classification": "incident_diagnosis",
  "expected_source_ids": ["spark-invalid-trip-duration"],
  "expected_facts": ["maximum allowed duration is 1440 minutes"],
  "should_abstain": false
}
```

Calculate at least:

- Recall@5.
- Mean Reciprocal Rank.
- Classification accuracy.
- Citation validity.
- Abstention accuracy.

Review generated answers manually for correctness and groundedness. Do not let the same LLM be the only judge of its own output.

### Why

The evaluation demonstrates engineering discipline and gives Madayn a measurable way to compare local and hosted models.

## Step 14 — Test, rehearse, and document limitations (45 minutes)

### Build

Run the entire demo from a clean application start:

1. Start Compose services.
2. Check API and database health.
3. Ingest the knowledge pack.
4. Run the evaluation command.
5. Open the portal.
6. Ask a known incident question.
7. Expand its evidence.
8. Ask an unanswerable question and demonstrate abstention.
9. Ask which Iceberg table has small files and show the computed metrics.

Document limitations honestly:

- Synthetic incidents are not production telemetry.
- Docker Compose is the POC runtime, not the final HA architecture.
- Authentication and Madayn RBAC integration are not implemented yet.
- The copilot cannot modify infrastructure.
- Arabic retrieval and answers require evaluation before production claims.

### Day 2 definition of done

- [ ] The existing portal has a working Copilot page.
- [ ] Answers cite exact evidence passages.
- [ ] At least Airflow/Trino/Iceberg read-only evidence is available.
- [ ] Missing evidence produces an explicit refusal to guess.
- [ ] The evaluation report includes Recall@5 and citation checks.
- [ ] No secrets are stored in logs, prompts, Git, or the vector database.
- [ ] The five headline demo questions work or clearly abstain.

---

# 5. Suggested two-day timetable

## Day 1

| Time | Work |
|---|---|
| 09:00–09:30 | Scope and concepts |
| 09:30–10:15 | FastAPI scaffold |
| 10:15–11:00 | pgvector Compose service |
| 11:00–11:45 | Evidence schema |
| 11:45–12:45 | First knowledge pack |
| 13:45–15:00 | Chunking and ingestion |
| 15:00–16:30 | Hybrid retrieval |
| 16:30–17:00 | Retrieval tests and notes |

## Day 2

| Time | Work |
|---|---|
| 09:00–09:45 | Question classification |
| 09:45–11:15 | Live read-only collectors |
| 11:15–12:00 | Evidence-sufficiency rules |
| 13:00–14:00 | Qwen/Ollama provider |
| 14:00–15:15 | React Copilot page |
| 15:15–16:30 | Evaluation suite |
| 16:30–17:15 | End-to-end test and demo rehearsal |

# 6. What to defer until after the demo

Do not attempt these during the two-day build:

- Automatic remediation or container restarts.
- Kubernetes deployment.
- Fine-tuning Qwen.
- Production SSO and full RBAC.
- Continuous ingestion of every platform log.
- A large observability stack.
- Conversation memory across users.
- Production-scale vector-index optimization.

These are valuable later, but none is required to prove the central idea.

# 7. Safety rules

1. Give collectors read-only, allow-listed operations.
2. Never send secrets or complete environment dumps to the model.
3. Redact passwords, tokens, connection strings, and access keys before storage.
4. Treat logs and retrieved documents as untrusted content.
5. Never execute a command generated by the LLM automatically.
6. Store the user question, selected evidence IDs, answer, model, and timestamp for auditability.
7. Keep citations immutable for an answer so its evidence can be reviewed later.

# 8. Final demonstration story

Use this short narrative:

1. An engineer sees a failed taxi pipeline.
2. They ask, “Why did the Spark ingestion fail?”
3. The copilot retrieves the task log and taxi data contract.
4. It explains that a source record exceeded the 24-hour duration rule.
5. The engineer opens the evidence panel and sees the exact log and contract passages.
6. They ask an unsupported question.
7. The copilot refuses to guess and states what evidence is missing.
8. They ask which Iceberg table needs compaction.
9. The copilot shows live file statistics obtained through an allow-listed Trino query.

This demonstrates diagnosis, retrieval, citations, live platform integration, governance, and safe behaviour in one coherent flow.
