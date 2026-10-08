import os
from functools import lru_cache

import numpy as np
from google import genai
from google.genai import types

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "gemini-embedding-001"
)

EMBEDDING_DIMENSION = 768


@lru_cache(maxsize=1)
def load_embedding_model():
    """
    Create and cache the Gemini API client.

    Unlike SentenceTransformer, this does not download a local ML model.
    """
    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is not configured")

    return genai.Client(api_key=api_key)


def create_embeddings(
    model,
    texts,
    batch_size: int = 32,
    task_type: str = "RETRIEVAL_DOCUMENT",
) -> np.ndarray:
    """
    Generate L2-normalised Gemini embeddings.

    RETRIEVAL_DOCUMENT is used when embedding stored document chunks.
    RETRIEVAL_QUERY is used when embedding a user's question.
    """

    texts = list(texts)

    if not texts:
        return np.empty((0, EMBEDDING_DIMENSION), dtype="float32")

    all_embeddings = []

    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]

        result = model.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=batch,
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=EMBEDDING_DIMENSION,
            ),
        )

        batch_embeddings = [
            embedding.values
            for embedding in result.embeddings
        ]

        all_embeddings.extend(batch_embeddings)

    embeddings = np.asarray(all_embeddings, dtype="float32")

    # L2 normalisation so FAISS inner product behaves like cosine similarity.
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    embeddings = embeddings / np.maximum(norms, 1e-12)

    return np.ascontiguousarray(embeddings, dtype="float32")