"""
Thin SQLite wrapper. We store domain objects as JSON blobs alongside a
few indexed columns needed for lookups — enough structure to query
efficiently, without leaking ORM concerns into the domain layer above.
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS problems (
    id TEXT PRIMARY KEY,
    data TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS attempts (
    id TEXT PRIMARY KEY,
    learner_id TEXT NOT NULL,
    problem_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_attempts_learner ON attempts(learner_id);

CREATE TABLE IF NOT EXISTS submissions (
    id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_submissions_attempt ON submissions(attempt_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_submissions_idem ON submissions(attempt_id, idempotency_key);

CREATE TABLE IF NOT EXISTS evaluations (
    id TEXT PRIMARY KEY,
    submission_id TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_evaluations_submission ON evaluations(submission_id);
"""

_local = threading.local()


class Database:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self):
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    def connect(self) -> sqlite3.Connection:
        # One connection per thread: evaluation runs on a background
        # thread, and sqlite3 connections aren't safe to share across
        # threads without check_same_thread=False + our own care.
        key = f"conn_{self.path}"
        conn = getattr(_local, key, None)
        if conn is None:
            conn = sqlite3.connect(self.path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            setattr(_local, key, conn)
        return conn
