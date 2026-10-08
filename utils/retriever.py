from typing import List

from utils.embeddings import create_embeddings


def retrieve_chunks(question: str, model, index, chunks: List[dict], top_k: int = 4) -> List[dict]:
    """Return the `top_k` most relevant chunks, best first.

    Each result is the stored chunk plus a cosine-similarity `score`.
    Handles stores that hold fewer than `top_k` chunks (FAISS pads with -1).
    """
    if index is None or not chunks:
        return []

    query_vector = create_embeddings(model, [question])
    scores, ids = index.search(query_vector, min(top_k, len(chunks)))

    results = []
    for score, idx in zip(scores[0], ids[0]):
        if idx < 0:
            continue
        results.append({**chunks[int(idx)], "score": float(score)})
    return results
