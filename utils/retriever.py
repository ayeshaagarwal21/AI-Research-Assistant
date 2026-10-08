from typing import List

from utils.embeddings import create_embeddings


def retrieve_chunks(
    question: str,
    model,
    index,
    chunks: List[dict],
    top_k: int = 4,
) -> List[dict]:
    """Return the most relevant chunks, best first."""

    if index is None or not chunks:
        return []

    # Queries should use RETRIEVAL_QUERY.
    query_vector = create_embeddings(
        model,
        [question],
        task_type="RETRIEVAL_QUERY",
    )

    scores, ids = index.search(
        query_vector,
        min(top_k, len(chunks)),
    )

    results = []

    for score, idx in zip(scores[0], ids[0]):
        if idx < 0:
            continue

        results.append({
            **chunks[int(idx)],
            "score": float(score),
        })

    return results