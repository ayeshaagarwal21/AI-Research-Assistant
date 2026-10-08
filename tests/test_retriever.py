import unittest

import numpy as np

from utils.retriever import retrieve_chunks


class FakeModel:
    def encode(self, texts, **kwargs):
        return np.ones((len(texts), 3), dtype="float32")


class FakeIndex:
    """Mimics faiss: returns (scores, ids) and pads with -1 when k > stored vectors."""

    def __init__(self, scores, ids):
        self._scores, self._ids = scores, ids
        self.last_k = None

    def search(self, query, k):
        self.last_k = k
        return np.array([self._scores]), np.array([self._ids])


CHUNKS = [
    {"text": "alpha", "source": "a.pdf", "page": 1},
    {"text": "beta", "source": "a.pdf", "page": 2},
]


class RetrieverTests(unittest.TestCase):
    def test_returns_chunks_with_scores_in_order(self):
        index = FakeIndex([0.9, 0.4], [1, 0])
        results = retrieve_chunks("q", FakeModel(), index, CHUNKS, top_k=2)
        self.assertEqual([r["text"] for r in results], ["beta", "alpha"])
        self.assertAlmostEqual(results[0]["score"], 0.9, places=5)
        self.assertEqual(results[0]["page"], 2)

    def test_top_k_larger_than_store_does_not_crash_on_minus_one(self):
        # Old code did chunks[-1] here and silently returned the wrong chunk.
        index = FakeIndex([0.9, 0.4, -1.0], [0, 1, -1])
        results = retrieve_chunks("q", FakeModel(), index, CHUNKS, top_k=5)
        self.assertEqual(len(results), 2)
        self.assertEqual(index.last_k, 2)  # k is capped at the number of chunks

    def test_empty_store_returns_nothing(self):
        self.assertEqual(retrieve_chunks("q", FakeModel(), None, []), [])


if __name__ == "__main__":
    unittest.main()
