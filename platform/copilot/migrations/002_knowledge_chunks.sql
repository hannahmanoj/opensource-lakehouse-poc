CREATE TABLE IF NOT EXISTS knowledge_chunks (
     id UUID PRIMARY KEY -- eg. 07a898cc-757f-4791-a6bc-9146d4219e31
    , source_type TEXT NOT NULL -- eg. "spark_log", "spark_log", "trino_log", etc.
    , source_name TEXT NOT NULL -- eg. "spark_runbook_for_errors"
    , component TEXT -- eg. "spark", "trino", etc.
    , severity TEXT -- eg, "ERROR", "WARNING", "INFO", etc.
    , occurred_at TIMESTAMPTZ -- eg 2026-09-03 09:25:45+04
    , title TEXT NOT NULL -- eg. "Spark Job Failed"
    , content TEXT NOT NULL
    , source_uri TEXT NOT NULL
    , line_start INT
    , line_end INT
    , metadata JSONB NOT NULL DEFAULT '{}'::JSONB
    , text_search TSVECTOR GENERATED ALWAYS AS (
        to_tsvector(
            'english'
            , coalesce(title, '') || ' ' || coalesce(content, '')
        )
    ) STORED
    , embedding VECTOR(1024)
    , content_hash TEXT UNIQUE NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_component 
    ON knowledge_chunks (component);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_source_type
    ON knowledge_chunks (source_type);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_occurred_at
    ON knowledge_chunks (occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_component_time
    ON knowledge_chunks (component, occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_text_search
    ON knowledge_chunks
    USING GIN (text_search);