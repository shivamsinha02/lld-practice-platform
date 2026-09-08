"""
SQLite implementations of the repository interfaces. All (de)serialization
of dataclasses <-> JSON happens here, kept out of the domain layer.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from typing import List, Optional

from app.domain.models import (
    Attempt,
    AttemptStatus,
    CriterionResult,
    Difficulty,
    Evaluation,
    Problem,
    Submission,
    SubmissionFormat,
    SubmissionStatus,
)
from app.domain.repositories import (
    AttemptRepository,
    EvaluationRepository,
    ProblemRepository,
    SubmissionRepository,
)
from app.infra.db import Database


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


class SqliteProblemRepository(ProblemRepository):
    def __init__(self, db: Database):
        self.db = db

    def save(self, problem: Problem) -> None:
        conn = self.db.connect()
        conn.execute(
            "INSERT OR REPLACE INTO problems (id, data) VALUES (?, ?)",
            (problem.id, json.dumps(asdict(problem))),
        )
        conn.commit()

    def get(self, problem_id: str) -> Optional[Problem]:
        row = self.db.connect().execute(
            "SELECT data FROM problems WHERE id = ?", (problem_id,)
        ).fetchone()
        if not row:
            return None
        d = json.loads(row["data"])
        d["difficulty"] = Difficulty(d["difficulty"])
        return Problem(**d)

    def list_all(self) -> List[Problem]:
        rows = self.db.connect().execute("SELECT data FROM problems").fetchall()
        problems = []
        for row in rows:
            d = json.loads(row["data"])
            d["difficulty"] = Difficulty(d["difficulty"])
            problems.append(Problem(**d))
        return problems


class SqliteAttemptRepository(AttemptRepository):
    def __init__(self, db: Database):
        self.db = db

    def save(self, attempt: Attempt) -> None:
        d = asdict(attempt)
        d["created_at"] = attempt.created_at.isoformat()
        conn = self.db.connect()
        conn.execute(
            """INSERT OR REPLACE INTO attempts (id, learner_id, problem_id, created_at, data)
               VALUES (?, ?, ?, ?, ?)""",
            (attempt.id, attempt.learner_id, attempt.problem_id, d["created_at"], json.dumps(d)),
        )
        conn.commit()

    def _row_to_attempt(self, row) -> Attempt:
        d = json.loads(row["data"])
        d["status"] = AttemptStatus(d["status"])
        d["created_at"] = _dt(d["created_at"])
        return Attempt(**d)

    def get(self, attempt_id: str) -> Optional[Attempt]:
        row = self.db.connect().execute(
            "SELECT data FROM attempts WHERE id = ?", (attempt_id,)
        ).fetchone()
        return self._row_to_attempt(row) if row else None

    def list_for_learner(self, learner_id: str) -> List[Attempt]:
        rows = self.db.connect().execute(
            "SELECT data FROM attempts WHERE learner_id = ?", (learner_id,)
        ).fetchall()
        return [self._row_to_attempt(r) for r in rows]


class SqliteSubmissionRepository(SubmissionRepository):
    def __init__(self, db: Database):
        self.db = db

    def save(self, submission: Submission) -> None:
        d = asdict(submission)
        d["created_at"] = submission.created_at.isoformat()
        d["updated_at"] = submission.updated_at.isoformat()
        conn = self.db.connect()
        conn.execute(
            """INSERT OR REPLACE INTO submissions (id, attempt_id, idempotency_key, data)
               VALUES (?, ?, ?, ?)""",
            (submission.id, submission.attempt_id, submission.idempotency_key, json.dumps(d)),
        )
        conn.commit()

    def _row_to_submission(self, row) -> Submission:
        d = json.loads(row["data"])
        d["format"] = SubmissionFormat(d["format"])
        d["status"] = SubmissionStatus(d["status"])
        d["created_at"] = _dt(d["created_at"])
        d["updated_at"] = _dt(d["updated_at"])
        return Submission(**d)

    def get(self, submission_id: str) -> Optional[Submission]:
        row = self.db.connect().execute(
            "SELECT data FROM submissions WHERE id = ?", (submission_id,)
        ).fetchone()
        return self._row_to_submission(row) if row else None

    def find_by_idempotency_key(self, attempt_id: str, key: str) -> Optional[Submission]:
        row = self.db.connect().execute(
            "SELECT data FROM submissions WHERE attempt_id = ? AND idempotency_key = ?",
            (attempt_id, key),
        ).fetchone()
        return self._row_to_submission(row) if row else None


class SqliteEvaluationRepository(EvaluationRepository):
    def __init__(self, db: Database):
        self.db = db

    def save(self, evaluation: Evaluation) -> None:
        d = asdict(evaluation)
        d["created_at"] = evaluation.created_at.isoformat()
        conn = self.db.connect()
        conn.execute(
            "INSERT OR REPLACE INTO evaluations (id, submission_id, data) VALUES (?, ?, ?)",
            (evaluation.id, evaluation.submission_id, json.dumps(d)),
        )
        conn.commit()

    def get_for_submission(self, submission_id: str) -> Optional[Evaluation]:
        row = self.db.connect().execute(
            "SELECT data FROM evaluations WHERE submission_id = ? ORDER BY rowid DESC LIMIT 1",
            (submission_id,),
        ).fetchone()
        if not row:
            return None
        d = json.loads(row["data"])
        d["created_at"] = _dt(d["created_at"])
        d["results"] = [CriterionResult(**r) for r in d["results"]]
        return Evaluation(**d)
