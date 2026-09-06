import os
from functools import lru_cache

from sentence_transformers import SentenceTransformer


EMBEDDING_MODEL = os.environ.get( "COPILOT_EMBEDDING_MODEL", "BAAI/bge-m3", )

#keeps the first loaded model in memory
@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    print(f"Loading embedding model: {EMBEDDING_MODEL}")
    return SentenceTransformer(EMBEDDING_MODEL)


def embed_question(question: str):
    model = get_embedding_model()

    return model.encode(
        question,
        normalize_embeddings=True,
    )