"""Per-user vector storage.

On disk (one folder per user):
    vector_store/user_<id>/embeddings.npy   - the vectors (source of truth for search)
    vector_store/user_<id>/chunks.json      - text + source + page for each vector
    vector_store/user_<id>/pages.json       - full text of every page (used to solve
                                              the questions that appear inside a PDF)

The FAISS index is rebuilt from the saved vectors when needed and cached in
memory, so deleting a single document is just "filter and save".
"""
import json
import os
import shutil
import threading
from collections import Counter
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

VECTOR_DIR = Path(
    os.getenv("VECTOR_STORE_DIR", Path(__file__).resolve().parents[1] / "vector_store")
)

_lock = threading.RLock()
_index_cache = {}  # user_id -> (mtime_ns, index, chunks)


def _user_dir(user_id: int) -> Path:
    return VECTOR_DIR / f"user_{int(user_id)}"


def _pages_file(user_id: int) -> Path:
    return _user_dir(user_id) / "pages.json"


def _read_pages_file(user_id: int) -> List[dict]:
    path = _pages_file(user_id)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _write_pages_file(user_id: int, pages: List[dict]) -> None:
    _user_dir(user_id).mkdir(parents=True, exist_ok=True)
    _pages_file(user_id).write_text(json.dumps(pages, ensure_ascii=False), encoding="utf-8")


def load_store(user_id: int) -> Tuple[Optional[np.ndarray], List[dict]]:
    folder = _user_dir(user_id)
    emb_file, chunk_file = folder / "embeddings.npy", folder / "chunks.json"
    if not emb_file.exists() or not chunk_file.exists():
        return None, []
    embeddings = np.load(emb_file)
    chunks = json.loads(chunk_file.read_text(encoding="utf-8"))
    return embeddings, chunks


def save_store(user_id: int, embeddings: np.ndarray, chunks: List[dict]) -> None:
    folder = _user_dir(user_id)
    folder.mkdir(parents=True, exist_ok=True)
    np.save(folder / "embeddings.npy", np.asarray(embeddings, dtype="float32"))
    (folder / "chunks.json").write_text(
        json.dumps(chunks, ensure_ascii=False), encoding="utf-8"
    )
    _index_cache.pop(user_id, None)


def add_documents(
    user_id: int,
    new_embeddings: np.ndarray,
    new_chunks: List[dict],
    new_pages: Optional[List[dict]] = None,
) -> int:
    """Add chunks (and optionally full page texts) to the user's store.

    Re-uploading a file replaces its old data. Returns the total vector count.
    """
    with _lock:
        replaced = {c["source"] for c in new_chunks}
        old_pages = [p for p in _read_pages_file(user_id) if p["source"] not in replaced]

        old_embeddings, old_chunks = load_store(user_id)
        if old_embeddings is not None:
            keep = np.array(
                [i for i, c in enumerate(old_chunks) if c["source"] not in replaced],
                dtype=int,
            )
            embeddings = np.vstack([old_embeddings[keep], new_embeddings])
            chunks = [old_chunks[i] for i in keep] + list(new_chunks)
        else:
            embeddings, chunks = new_embeddings, list(new_chunks)

        save_store(user_id, embeddings, chunks)

        pages_to_write = old_pages + list(new_pages or [])
        if pages_to_write or _pages_file(user_id).exists():
            _write_pages_file(user_id, pages_to_write)
        return len(chunks)


def remove_document(user_id: int, filename: str) -> int:
    """Remove every chunk that came from `filename`. Returns how many were removed."""
    with _lock:
        embeddings, chunks = load_store(user_id)
        if embeddings is None:
            return 0

        keep = [i for i, c in enumerate(chunks) if c["source"] != filename]
        removed = len(chunks) - len(keep)
        if removed == 0:
            return 0
        if not keep:
            clear_store(user_id)
            return removed

        save_store(user_id, embeddings[np.array(keep, dtype=int)], [chunks[i] for i in keep])
        if _pages_file(user_id).exists():
            _write_pages_file(
                user_id, [p for p in _read_pages_file(user_id) if p["source"] != filename]
            )
        return removed


def clear_store(user_id: int) -> None:
    with _lock:
        shutil.rmtree(_user_dir(user_id), ignore_errors=True)
        _index_cache.pop(user_id, None)


def list_documents(user_id: int) -> List[dict]:
    _, chunks = load_store(user_id)
    counts = Counter(c["source"] for c in chunks)
    return [{"filename": name, "chunks": n} for name, n in counts.items()]


def load_pages(user_id: int) -> List[dict]:
    """Full text of each page: [{'source', 'page', 'text'}, ...].

    Documents uploaded before pages were stored are rebuilt from their chunks
    (slightly repeated text at chunk edges, but good enough to read questions from).
    """
    pages = _read_pages_file(user_id)
    have = {p["source"] for p in pages}

    _, chunks = load_store(user_id)
    grouped = {}
    for chunk in chunks:
        if chunk["source"] not in have:
            grouped.setdefault((chunk["source"], chunk["page"]), []).append(chunk["text"])

    rebuilt = [
        {"source": source, "page": page, "text": "\n".join(texts)}
        for (source, page), texts in grouped.items()
    ]
    return pages + rebuilt


def build_index(embeddings: np.ndarray):
    """Exact inner-product FAISS index (cosine similarity for normalised vectors)."""
    import faiss  # imported lazily so the rest of this module works without FAISS

    vectors = np.ascontiguousarray(embeddings, dtype="float32")
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    return index


def get_index(user_id: int):
    """Return (faiss_index, chunks) for the user, or (None, []) if nothing is uploaded."""
    chunk_file = _user_dir(user_id) / "chunks.json"
    with _lock:
        if not chunk_file.exists():
            _index_cache.pop(user_id, None)
            return None, []

        mtime = chunk_file.stat().st_mtime_ns
        cached = _index_cache.get(user_id)
        if cached and cached[0] == mtime:
            return cached[1], cached[2]

        embeddings, chunks = load_store(user_id)
        if embeddings is None:
            return None, []
        index = build_index(embeddings)
        _index_cache[user_id] = (mtime, index, chunks)
        return index, chunks
