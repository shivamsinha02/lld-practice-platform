"""
Domain models for the LLD Practice Platform.

Deliberately framework-free: no ORM base classes, no FastAPI/pydantic
imports here. This layer should still make sense if we swapped SQLite
for Postgres, or FastAPI for a CLI. Persistence and delivery concerns
live in app/infra and app/api respectively.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Problem
# ---------------------------------------------------------------------------

class Difficulty(str, Enum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"


@dataclass
class Problem:
    """A single LLD practice problem. Content is intentionally static –
    problems are curated, not user-generated, for this MVP."""

    id: str
    title: str
    difficulty: Difficulty
    tags: List[str]
    description: str
    requirements: List[str]
    # What we expect learners to think about is intentionally NOT a
    # single "reference solution" (the guide warns against that) —
    # it's a set of discussion points the evaluator's prompt is grounded in.
    discussion_points: List[str]


# ---------------------------------------------------------------------------
# Submission format (Strategy hook for Change Test A)
# ---------------------------------------------------------------------------

class SubmissionFormat(str, Enum):
    """Only TEXT_DESIGN is implemented in this MVP. Adding CODE or
    DIAGRAM later means: (1) add an enum value, (2) add a validator in
    submission_format.py, (3) add an evaluator that understands it.
    No change to Attempt/Submission/Evaluation state machines."""

    TEXT_DESIGN = "TEXT_DESIGN"


class SubmissionStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    EVALUATING = "EVALUATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

    def can_transition_to(self, target: "SubmissionStatus") -> bool:
        allowed = {
            SubmissionStatus.SUBMITTED: {SubmissionStatus.EVALUATING},
            SubmissionStatus.EVALUATING: {
                SubmissionStatus.COMPLETED,
                SubmissionStatus.FAILED,
            },
            # A FAILED submission may be retried, which re-enters EVALUATING.
            SubmissionStatus.FAILED: {SubmissionStatus.EVALUATING},
            SubmissionStatus.COMPLETED: set(),
        }
        return target in allowed[self]


@dataclass
class Submission:
    """A learner's design for one Attempt. 1:1 with Attempt: 'trying
    again' means starting a new Attempt, not editing this one. That
    keeps the state machine linear and keeps history meaningful (each
    Attempt is an immutable snapshot of one try)."""

    id: str
    attempt_id: str
    format: SubmissionFormat
    content: str
    idempotency_key: str
    status: SubmissionStatus = SubmissionStatus.SUBMITTED
    created_at: datetime = field(default_factory=now)
    updated_at: datetime = field(default_factory=now)
    failure_reason: Optional[str] = None

    def transition(self, target: SubmissionStatus, failure_reason: Optional[str] = None) -> None:
        if not self.status.can_transition_to(target):
            raise InvalidStateTransition(
                f"Cannot move submission {self.id} from {self.status} to {target}"
            )
        self.status = target
        self.updated_at = now()
        if target == SubmissionStatus.FAILED:
            self.failure_reason = failure_reason


class InvalidStateTransition(Exception):
    pass


# ---------------------------------------------------------------------------
# Attempt
# ---------------------------------------------------------------------------

class AttemptStatus(str, Enum):
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"


@dataclass
class Attempt:
    """One practice session against one Problem by one learner."""

    id: str
    problem_id: str
    learner_id: str
    status: AttemptStatus = AttemptStatus.IN_PROGRESS
    created_at: datetime = field(default_factory=now)
    submission_id: Optional[str] = None

    def mark_submitted(self, submission_id: str) -> None:
        if self.status != AttemptStatus.IN_PROGRESS:
            raise InvalidStateTransition(
                f"Attempt {self.id} already has a submission; start a new attempt to try again."
            )
        self.status = AttemptStatus.SUBMITTED
        self.submission_id = submission_id


# ---------------------------------------------------------------------------
# Rubric-based evaluation
# ---------------------------------------------------------------------------

@dataclass
class CriterionResult:
    """One rubric dimension's result. This shape (score + evidence +
    concern + suggestion + confidence) is fixed for every evaluator —
    heuristic or LLM — so the frontend never special-cases who produced
    the feedback."""

    criterion_key: str
    criterion_name: str
    score: float  # 0.0 - 1.0
    evidence: str
    concern: str
    suggestion: str
    confidence: float  # 0.0 - 1.0, evaluator's self-reported confidence


@dataclass
class Evaluation:
    """The result of running one Evaluator over one Submission."""

    id: str
    submission_id: str
    evaluator_name: str
    results: List[CriterionResult]
    overall_score: float
    summary: str
    created_at: datetime = field(default_factory=now)

    @staticmethod
    def weighted_score(results: List[CriterionResult], weights: dict) -> float:
        total_weight = sum(weights.get(r.criterion_key, 0.0) for r in results)
        if total_weight == 0:
            return 0.0
        return round(
            sum(r.score * weights.get(r.criterion_key, 0.0) for r in results) / total_weight,
            3,
        )
