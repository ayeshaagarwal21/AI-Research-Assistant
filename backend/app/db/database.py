"""SQLite persistence for users, conversations, chat messages and user metadata."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from backend.app.core import config


@contextmanager
def get_conn():
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT NOT NULL,
                email         TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at    TEXT NOT NULL,
                last_login    TEXT,
                login_count   INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS conversations (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title      TEXT NOT NULL DEFAULT 'New research chat',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                conversation_id INTEGER REFERENCES conversations(id) ON DELETE CASCADE,
                role            TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                content         TEXT NOT NULL,
                sources         TEXT NOT NULL DEFAULT '[]',
                created_at      TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id, id);
            CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, id);
            CREATE INDEX IF NOT EXISTS idx_conversations_user_updated
                ON conversations(user_id, updated_at DESC);
            """
        )

        # Safe migration for databases created by v5 and earlier.
        user_columns = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "last_login" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN last_login TEXT")
        if "login_count" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN login_count INTEGER NOT NULL DEFAULT 0")

        message_columns = {row[1] for row in conn.execute("PRAGMA table_info(messages)").fetchall()}
        if "conversation_id" not in message_columns:
            conn.execute("ALTER TABLE messages ADD COLUMN conversation_id INTEGER")

        # Put any legacy messages into one conversation per user so old data is not lost.
        users = conn.execute("SELECT id FROM users").fetchall()
        for user in users:
            user_id = user["id"]
            has_legacy = conn.execute(
                "SELECT 1 FROM messages WHERE user_id = ? AND conversation_id IS NULL LIMIT 1",
                (user_id,),
            ).fetchone()
            if has_legacy:
                existing = conn.execute(
                    "SELECT id FROM conversations WHERE user_id = ? ORDER BY id LIMIT 1",
                    (user_id,),
                ).fetchone()
                conv_id = existing["id"] if existing else None
                if conv_id is None:
                    now = _now()
                    cur = conn.execute(
                        "INSERT INTO conversations (user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                        (user_id, "Previous research", now, now),
                    )
                    conv_id = cur.lastrowid
                conn.execute(
                    "UPDATE messages SET conversation_id = ? WHERE user_id = ? AND conversation_id IS NULL",
                    (conv_id, user_id),
                )
                conn.execute(
                    "UPDATE conversations SET updated_at = ? WHERE id = ?",
                    (_now(), conv_id),
                )


# ------------------------------- users ----------------------------------

def create_user(username: str, email: str, password_hash: str) -> int:
    try:
        with get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO users (username, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (username.strip(), email.strip().lower(), password_hash, _now()),
            )
            return cur.lastrowid
    except sqlite3.IntegrityError as exc:
        raise ValueError("email already registered") from exc


def get_user_by_email(email: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, username, email, created_at, last_login, login_count FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def record_login(user_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET last_login = ?, login_count = login_count + 1 WHERE id = ?",
            (_now(), user_id),
        )


# ---------------------------- conversations -----------------------------
def create_conversation(user_id: int, title: str = "New research chat") -> dict:
    now = _now()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO conversations (user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (user_id, (title or "New research chat").strip()[:120], now, now),
        )
        row = conn.execute("SELECT * FROM conversations WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


def get_conversation(user_id: int, conversation_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        ).fetchone()
    return dict(row) if row else None


def get_conversations(user_id: int) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT c.*, COUNT(m.id) AS message_count
               FROM conversations c
               LEFT JOIN messages m ON m.conversation_id = c.id
               WHERE c.user_id = ?
               GROUP BY c.id
               ORDER BY c.updated_at DESC, c.id DESC""",
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def rename_conversation(user_id: int, conversation_id: int, title: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (title.strip()[:120], _now(), conversation_id, user_id),
        )
    return cur.rowcount > 0


def delete_conversation(user_id: int, conversation_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        )
    return cur.rowcount > 0


def touch_conversation(conversation_id: int) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (_now(), conversation_id))


# ------------------------------ messages --------------------------------
def add_message(user_id: int, role: str, content: str, sources=None, conversation_id: int | None = None) -> None:
    with get_conn() as conn:
        if conversation_id is None:
            cur = conn.execute(
                "SELECT id FROM conversations WHERE user_id = ? ORDER BY updated_at DESC, id DESC LIMIT 1",
                (user_id,),
            ).fetchone()
            conversation_id = cur["id"] if cur else None
        conn.execute(
            "INSERT INTO messages (user_id, conversation_id, role, content, sources, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, conversation_id, role, content, json.dumps(sources or []), _now()),
        )
        if conversation_id is not None:
            conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (_now(), conversation_id))


def get_messages(user_id: int, limit: int = 100, conversation_id: int | None = None) -> list:
    with get_conn() as conn:
        if conversation_id is None:
            rows = conn.execute(
                "SELECT role, content, sources, created_at FROM messages WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT role, content, sources, created_at FROM messages
                   WHERE user_id = ? AND conversation_id = ? ORDER BY id DESC LIMIT ?""",
                (user_id, conversation_id, limit),
            ).fetchall()
    messages = []
    for row in reversed(rows):
        item = dict(row)
        item["sources"] = json.loads(item["sources"])
        messages.append(item)
    return messages


def clear_messages(user_id: int, conversation_id: int | None = None) -> None:
    with get_conn() as conn:
        if conversation_id is None:
            conn.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
        else:
            conn.execute(
                "DELETE FROM messages WHERE user_id = ? AND conversation_id = ?",
                (user_id, conversation_id),
            )
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE user_id = ? AND id = ?",
                (_now(), user_id, conversation_id),
            )


# --------------------------- admin reporting ----------------------------

def get_admin_stats() -> dict:
    """Return aggregate, non-secret application statistics for the admin portal."""
    from backend.app.core import config
    from pathlib import Path

    with get_conn() as conn:
        users = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        conversations = conn.execute("SELECT COUNT(*) AS n FROM conversations").fetchone()["n"]
        messages = conn.execute("SELECT COUNT(*) AS n FROM messages").fetchone()["n"]
        active_users = conn.execute(
            "SELECT COUNT(*) AS n FROM users WHERE last_login IS NOT NULL"
        ).fetchone()["n"]

    documents = 0
    vector_dir = Path(
        __import__("os").getenv(
            "VECTOR_STORE_DIR",
            Path(__file__).resolve().parents[3] / "vector_store",
        )
    )
    if vector_dir.exists():
        for chunks_file in vector_dir.glob("user_*/chunks.json"):
            try:
                data = json.loads(chunks_file.read_text(encoding="utf-8"))
                documents += len({item.get("source") for item in data if item.get("source")})
            except (OSError, ValueError, TypeError):
                continue

    return {
        "total_users": users,
        "active_users": active_users,
        "total_conversations": conversations,
        "total_messages": messages,
        "total_documents": documents,
    }


def get_all_users() -> list:
    """Return safe user metadata only; never return password hashes."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT id, username, email, created_at, last_login, login_count
               FROM users ORDER BY created_at DESC, id DESC"""
        ).fetchall()
    return [dict(row) for row in rows]


def get_recent_conversations(limit: int = 100) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT c.id, c.title, c.created_at, c.updated_at,
                      u.username, u.email, COUNT(m.id) AS message_count
               FROM conversations c
               JOIN users u ON u.id = c.user_id
               LEFT JOIN messages m ON m.conversation_id = c.id
               GROUP BY c.id
               ORDER BY c.updated_at DESC, c.id DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]
