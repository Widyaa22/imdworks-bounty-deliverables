import sqlite3
import threading
import time
import uuid


class ConflictError(Exception):
    pass


class StaleUpdateError(Exception):
    pass


class SubmissionStore:
    _schema_lock = threading.Lock()

    def __init__(self, path):
        self.path = str(path)
        self._local = threading.local()
        with self._schema_lock:
            self._init_schema()

    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=30000")
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _connection(self):
        if not hasattr(self._local, "connection"):
            self._local.connection = self._connect()
        return self._local.connection

    def _init_schema(self):
        connection = self._connect()
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS submissions (
                id TEXT PRIMARY KEY,
                wallet TEXT NOT NULL,
                bounty TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                content TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending','approved','rejected')),
                version INTEGER NOT NULL DEFAULT 0 CHECK(version >= 0),
                created_ns INTEGER NOT NULL,
                updated_ns INTEGER NOT NULL,
                UNIQUE(wallet, bounty),
                UNIQUE(wallet, bounty, idempotency_key)
            );
            CREATE TABLE IF NOT EXISTS trace_events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                submission_id TEXT,
                wallet TEXT,
                bounty TEXT,
                detail TEXT NOT NULL DEFAULT '',
                created_ns INTEGER NOT NULL
            );
        """)
        connection.close()

    @staticmethod
    def _as_dict(row):
        return dict(row)

    @staticmethod
    def _record(connection, action, row=None, detail=""):
        connection.execute(
            "INSERT INTO trace_events(action,submission_id,wallet,bounty,detail,created_ns) "
            "VALUES(?,?,?,?,?,?)",
            (
                action,
                row["id"] if row else None,
                row["wallet"] if row else None,
                row["bounty"] if row else None,
                detail,
                time.time_ns(),
            ),
        )

    def submit(self, wallet, bounty, idempotency_key, content):
        connection = self._connection()
        now = time.time_ns()
        submission_id = str(uuid.uuid4())
        connection.execute("BEGIN IMMEDIATE")
        try:
            row = connection.execute(
                "SELECT * FROM submissions WHERE wallet=? AND bounty=?",
                (wallet, bounty),
            ).fetchone()
            if row:
                if row["idempotency_key"] == idempotency_key and row["content"] == content:
                    self._record(connection, "idempotent_hit", row)
                    connection.commit()
                    return self._as_dict(row)
                self._record(connection, "submit_conflict", row)
                connection.commit()
                raise ConflictError("an active submission already exists")
            connection.execute(
                "INSERT INTO submissions(id,wallet,bounty,idempotency_key,content,created_ns,updated_ns) VALUES(?,?,?,?,?,?,?)",
                (submission_id, wallet, bounty, idempotency_key, content, now, now),
            )
            row = connection.execute("SELECT * FROM submissions WHERE id=?", (submission_id,)).fetchone()
            self._record(connection, "submitted", row)
            connection.commit()
            return self._as_dict(row)
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise

    def get(self, submission_id):
        row = self._connection().execute(
            "SELECT * FROM submissions WHERE id=?", (submission_id,)
        ).fetchone()
        return self._as_dict(row) if row else None

    def find(self, wallet, bounty):
        row = self._connection().execute(
            "SELECT * FROM submissions WHERE wallet=? AND bounty=?", (wallet, bounty)
        ).fetchone()
        return self._as_dict(row) if row else None

    def review(self, submission_id, status, expected_version):
        if status not in ("approved", "rejected"):
            raise ValueError("review status must be approved or rejected")
        connection = self._connection()
        connection.execute("BEGIN IMMEDIATE")
        try:
            row = connection.execute(
                "SELECT * FROM submissions WHERE id=?", (submission_id,)
            ).fetchone()
            if row is None:
                raise KeyError(submission_id)
            if row["version"] != expected_version:
                raise StaleUpdateError(
                    f"expected version {expected_version}, current version {row['version']}"
                )
            if row["status"] != "pending":
                raise ConflictError("reviewed submissions are immutable")
            now = time.time_ns()
            changed = connection.execute(
                "UPDATE submissions SET status=?, version=version+1, updated_ns=? "
                "WHERE id=? AND status='pending' AND version=?",
                (status, now, submission_id, expected_version),
            ).rowcount
            if changed != 1:
                raise StaleUpdateError("concurrent update won")
            result = connection.execute(
                "SELECT * FROM submissions WHERE id=?", (submission_id,)
            ).fetchone()
            self._record(connection, status, result)
            connection.commit()
            return self._as_dict(result)
        except Exception:
            connection.rollback()
            raise

    def trace(self):
        rows = self._connection().execute(
            "SELECT * FROM trace_events ORDER BY seq"
        ).fetchall()
        return [self._as_dict(row) for row in rows]

    def count_submissions(self):
        return self._connection().execute("SELECT COUNT(*) FROM submissions").fetchone()[0]

    def close(self):
        if hasattr(self._local, "connection"):
            self._local.connection.close()
            del self._local.connection
