import os
from functools import lru_cache

import numpy as np

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")


@lru_cache(maxsize=1)
def load_embedding_model():
    """Load the sentence-transformer once and reuse it (loading is slow)."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBEDDING_MODEL)


def create_embeddings(model, texts, batch_size: int = 32) -> np.ndarray:
    """Return L2-normalised float32 embeddings.

    Normalised vectors let us use inner product as cosine similarity, so scores
    fall between -1 and 1 and are easy to interpret.
    """
    embeddings = model.encode(
        list(texts),
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return np.ascontiguousarray(embeddings, dtype="float32")
