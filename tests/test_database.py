import tempfile
import unittest
from pathlib import Path

from backend.app.core import config
from backend.app.db import database as db


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._original = config.DB_PATH
        config.DB_PATH = Path(self._tmp.name) / "test.db"
        db.init_db()

    def tearDown(self):
        config.DB_PATH = self._original
        self._tmp.cleanup()

    def test_create_and_fetch_user(self):
        uid = db.create_user("Ayesha", "Ayesha@Example.com", "hash")
        by_email = db.get_user_by_email("ayesha@example.com")
        self.assertEqual(by_email["id"], uid)
        self.assertEqual(by_email["password_hash"], "hash")
        public = db.get_user_by_id(uid)
        self.assertNotIn("password_hash", public)

    def test_duplicate_email_rejected_case_insensitively(self):
        db.create_user("A", "a@x.com", "h")
        with self.assertRaises(ValueError):
            db.create_user("B", "A@X.COM", "h")

    def test_unknown_user_returns_none(self):
        self.assertIsNone(db.get_user_by_email("nobody@x.com"))
        self.assertIsNone(db.get_user_by_id(999))

    def test_messages_keep_order_sources_and_limit(self):
        uid = db.create_user("A", "a@x.com", "h")
        src = [{"source": "a.pdf", "page": 1, "score": 0.5, "snippet": "s"}]
        db.add_message(uid, "user", "q1")
        db.add_message(uid, "assistant", "a1", src)
        db.add_message(uid, "user", "q2")

        all_msgs = db.get_messages(uid)
        self.assertEqual([m["content"] for m in all_msgs], ["q1", "a1", "q2"])
        self.assertEqual(all_msgs[1]["sources"], src)

        last_two = db.get_messages(uid, limit=2)
        self.assertEqual([m["content"] for m in last_two], ["a1", "q2"])

    def test_history_is_private_per_user_and_clearable(self):
        u1 = db.create_user("A", "a@x.com", "h")
        u2 = db.create_user("B", "b@x.com", "h")
        db.add_message(u1, "user", "mine")
        db.add_message(u2, "user", "theirs")

        db.clear_messages(u1)
        self.assertEqual(db.get_messages(u1), [])
        self.assertEqual(len(db.get_messages(u2)), 1)


if __name__ == "__main__":
    unittest.main()
