import tempfile
import unittest
from pathlib import Path

import numpy as np

from utils import vector_store as vs


def make_chunks(source, n):
    return [{"text": f"{source} chunk {i}", "source": source, "page": i + 1} for i in range(n)]


def make_vectors(n, dim=4, fill=1.0):
    return np.full((n, dim), fill, dtype="float32")


class VectorStoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._original = vs.VECTOR_DIR
        vs.VECTOR_DIR = Path(self._tmp.name)
        vs._index_cache.clear()

    def tearDown(self):
        vs.VECTOR_DIR = self._original
        self._tmp.cleanup()

    def test_empty_store(self):
        self.assertEqual(vs.load_store(1), (None, []))
        self.assertEqual(vs.list_documents(1), [])
        self.assertEqual(vs.get_index(1), (None, []))

    def test_add_accumulates_documents(self):
        vs.add_documents(1, make_vectors(3), make_chunks("a.pdf", 3))
        total = vs.add_documents(1, make_vectors(2), make_chunks("b.pdf", 2))
        self.assertEqual(total, 5)
        self.assertEqual(
            vs.list_documents(1),
            [{"filename": "a.pdf", "chunks": 3}, {"filename": "b.pdf", "chunks": 2}],
        )
        embeddings, chunks = vs.load_store(1)
        self.assertEqual(embeddings.shape, (5, 4))
        self.assertEqual(len(chunks), 5)

    def test_reupload_replaces_instead_of_duplicating(self):
        vs.add_documents(1, make_vectors(3), make_chunks("a.pdf", 3))
        total = vs.add_documents(1, make_vectors(2, fill=9.0), make_chunks("a.pdf", 2))
        self.assertEqual(total, 2)
        embeddings, _ = vs.load_store(1)
        self.assertTrue(np.all(embeddings == 9.0))

    def test_remove_one_document_keeps_vectors_aligned_with_chunks(self):
        vs.add_documents(1, make_vectors(2, fill=1.0), make_chunks("a.pdf", 2))
        vs.add_documents(1, make_vectors(2, fill=2.0), make_chunks("b.pdf", 2))

        self.assertEqual(vs.remove_document(1, "a.pdf"), 2)
        embeddings, chunks = vs.load_store(1)
        self.assertEqual({c["source"] for c in chunks}, {"b.pdf"})
        self.assertTrue(np.all(embeddings == 2.0))

    def test_removing_last_document_clears_store(self):
        vs.add_documents(1, make_vectors(2), make_chunks("a.pdf", 2))
        vs.remove_document(1, "a.pdf")
        self.assertEqual(vs.load_store(1), (None, []))

    def test_remove_unknown_document(self):
        vs.add_documents(1, make_vectors(2), make_chunks("a.pdf", 2))
        self.assertEqual(vs.remove_document(1, "nope.pdf"), 0)
        self.assertEqual(vs.remove_document(2, "a.pdf"), 0)

    def test_users_are_isolated(self):
        vs.add_documents(1, make_vectors(2), make_chunks("mine.pdf", 2))
        vs.add_documents(2, make_vectors(1), make_chunks("theirs.pdf", 1))
        self.assertEqual([d["filename"] for d in vs.list_documents(1)], ["mine.pdf"])
        vs.clear_store(1)
        self.assertEqual(vs.list_documents(1), [])
        self.assertEqual([d["filename"] for d in vs.list_documents(2)], ["theirs.pdf"])


if __name__ == "__main__":
    unittest.main()


class PagesTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._original = vs.VECTOR_DIR
        vs.VECTOR_DIR = Path(self._tmp.name)
        vs._index_cache.clear()

    def tearDown(self):
        vs.VECTOR_DIR = self._original
        self._tmp.cleanup()

    @staticmethod
    def pages(source, texts):
        return [{"source": source, "page": i + 1, "text": t} for i, t in enumerate(texts)]

    def test_pages_are_saved_and_loaded(self):
        pg = self.pages("exam.pdf", ["Q1. What is 2+2?", "Q2. Define AI."])
        vs.add_documents(1, make_vectors(2), make_chunks("exam.pdf", 2), new_pages=pg)
        self.assertEqual(vs.load_pages(1), pg)

    def test_reupload_replaces_pages(self):
        vs.add_documents(1, make_vectors(1), make_chunks("a.pdf", 1),
                         new_pages=self.pages("a.pdf", ["old"]))
        vs.add_documents(1, make_vectors(1), make_chunks("a.pdf", 1),
                         new_pages=self.pages("a.pdf", ["new"]))
        self.assertEqual([p["text"] for p in vs.load_pages(1)], ["new"])

    def test_removing_a_document_removes_its_pages(self):
        vs.add_documents(1, make_vectors(1), make_chunks("a.pdf", 1),
                         new_pages=self.pages("a.pdf", ["A"]))
        vs.add_documents(1, make_vectors(1), make_chunks("b.pdf", 1),
                         new_pages=self.pages("b.pdf", ["B"]))
        vs.remove_document(1, "a.pdf")
        self.assertEqual([p["source"] for p in vs.load_pages(1)], ["b.pdf"])

    def test_old_documents_without_pages_are_rebuilt_from_chunks(self):
        vs.add_documents(1, make_vectors(2), make_chunks("old.pdf", 2))  # no pages saved
        pages = vs.load_pages(1)
        self.assertEqual([(p["source"], p["page"]) for p in pages],
                         [("old.pdf", 1), ("old.pdf", 2)])
        self.assertEqual(pages[0]["text"], "old.pdf chunk 0")

    def test_mix_of_old_and_new_documents(self):
        vs.add_documents(1, make_vectors(1), make_chunks("old.pdf", 1))
        vs.add_documents(1, make_vectors(1), make_chunks("new.pdf", 1),
                         new_pages=self.pages("new.pdf", ["full new text"]))
        by_source = {p["source"]: p["text"] for p in vs.load_pages(1)}
        self.assertEqual(by_source, {"new.pdf": "full new text", "old.pdf": "old.pdf chunk 0"})

    def test_clear_removes_pages_too(self):
        vs.add_documents(1, make_vectors(1), make_chunks("a.pdf", 1),
                         new_pages=self.pages("a.pdf", ["A"]))
        vs.clear_store(1)
        self.assertEqual(vs.load_pages(1), [])
