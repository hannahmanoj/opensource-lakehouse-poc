import hashlib
import os
import uuid
from pathlib import Path
import psycopg
import yaml
from pgvector.psycopg import register_vector
from psycopg.types.json import Jsonb
from sentence_transformers import SentenceTransformer

DATABASE_URL = os.environ["COPILOT_DATABASE_URL"]
# finds every md doc under /knowledge
KNOWLEDGE_PATH = Path(os.environ.get("COPILOT_KNOWLEDGE_PATH", "/knowledge"))
EMBEDDING_MODEL = os.environ.get("COPILOT_EMBEDDING_MODEL","BAAI/bge-m3",)

REQUIRED_METADATA = {
    "incident_id",
    "source_type",
    "component",
    "timestamp",
    "severity",
    "title",
}

def read_document(path: Path) -> tuple[dict, list[tuple[int, str]]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"Document {path} is missing YAML front matter")

    try:
        closing_marker = lines[1:].index("---") + 1
    except ValueError as error:
        raise ValueError(f"Document {path} is missing closing YAML front matter marker") from error

    yaml_text = "\n".join(lines[1:closing_marker])
    metadata = yaml.safe_load(yaml_text)

    missing = REQUIRED_METADATA - set(metadata)
    if missing:
        raise ValueError(f"Document {path} is missing required metadata fields: {', '.join(missing)}")

    body = [
        (line_number, line)
        for line_number, line in enumerate(
            lines[closing_marker + 1 :],
            start=closing_marker + 2,
        )
    ]

    return metadata, body

def token_count(tokenizer, lines: list[tuple[int, str]]) -> int:
    text = "\n".join(line for _, line in lines)
    return len(tokenizer.encode(text, add_special_tokens=False))


def split_into_sections(numbered_lines: list[tuple[int, str]],) -> list[list[tuple[int, str]]]:
    sections = []
    current_section = []

    for line_number, line in numbered_lines:
        if line.startswith("## ") and current_section:
            sections.append(current_section)
            current_section = []

        current_section.append((line_number, line))

    if current_section:
        sections.append(current_section)

    return sections

def chunk_document(numbered_lines: list[tuple[int, str]], tokenizer, maximum_tokens: int = 700, overlap_tokens: int = 80,) -> list[list[tuple[int, str]]]:
    sections = split_into_sections(numbered_lines)
    chunks = []
    current_chunk = []

    for section in sections:
        combined = current_chunk + section

        if (current_chunk and token_count(tokenizer, combined) > maximum_tokens):
            chunks.append(current_chunk)

            overlap = []
            for numbered_line in reversed(current_chunk):
                overlap.insert(0, numbered_line)

                if token_count(tokenizer, overlap) >= overlap_tokens:
                    break

            current_chunk = overlap + section
        else:
            current_chunk = combined

    if current_chunk:
        chunks.append(current_chunk)

    return chunks

def make_content_hash(source_uri: str, content: str,) -> str:
    value = f"{source_uri}\n{content}".encode("utf-8")
    return hashlib.sha256(value).hexdigest()

def collect_documents(model: SentenceTransformer) -> list[dict]:
    documents = []

    paths = sorted(KNOWLEDGE_PATH.rglob("*.md"))

    for path in paths:
        metadata, numbered_lines = read_document(path)

        relative_path = path.relative_to(KNOWLEDGE_PATH)
        source_uri = f"knowledge://{relative_path.as_posix()}"

        chunks = chunk_document(
            numbered_lines,
            model.tokenizer,
        )

        for chunk_number, chunk in enumerate(chunks, start=1):
            content = "\n".join(line for _, line in chunk).strip()

            if not content:
                continue

            documents.append(
                {
                    "id": uuid.uuid4(),
                    "source_type": metadata["source_type"],
                    "source_name": path.name,
                    "component": metadata["component"],
                    "severity": metadata["severity"],
                    "occurred_at": metadata["timestamp"],
                    "title": metadata["title"],
                    "content": content,
                    "source_uri": source_uri,
                    "line_start": chunk[0][0],
                    "line_end": chunk[-1][0],
                    "metadata": {
                        **metadata,
                        "chunk_number": chunk_number,
                    },
                    "content_hash": make_content_hash(
                        source_uri,
                        content,
                    ),
                }
            )

    return documents

def ingest() -> None:
    print(f"Loading embedding model: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL)

    documents = collect_documents(model)

    if not documents:
        print(f"No Markdown documents found in {KNOWLEDGE_PATH}")
        return

    print(f"Creating embeddings for {len(documents)} chunks")

    embeddings = model.encode(
        [document["content"] for document in documents],
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    inserted = 0
    skipped = 0

    with psycopg.connect(DATABASE_URL) as connection:
        register_vector(connection)

        with connection.cursor() as cursor:
            for document, embedding in zip(
                documents,
                embeddings,
                strict=True,
            ):
                cursor.execute(
                    """
                    INSERT INTO knowledge_chunks (
                        id,
                        source_type,
                        source_name,
                        component,
                        severity,
                        occurred_at,
                        title,
                        content,
                        source_uri,
                        line_start,
                        line_end,
                        metadata,
                        embedding,
                        content_hash
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (content_hash) DO NOTHING
                    RETURNING id
                    """,
                    (
                        document["id"],
                        document["source_type"],
                        document["source_name"],
                        document["component"],
                        document["severity"],
                        document["occurred_at"],
                        document["title"],
                        document["content"],
                        document["source_uri"],
                        document["line_start"],
                        document["line_end"],
                        Jsonb(document["metadata"]),
                        embedding,
                        document["content_hash"],
                    ),
                )

                if cursor.fetchone():
                    inserted += 1
                else:
                    skipped += 1

    print(f"Inserted chunks: {inserted}")
    print(f"Skipped existing chunks: {skipped}")


if __name__ == "__main__":
    ingest()

