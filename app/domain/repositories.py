"""
Repository interfaces. The service layer depends on these abstractions,
not on SQLite directly — swapping to Postgres later means writing a new
app/infra/*_repositories.py module, with zero change to app/domain or
app/api.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from app.domain.models import Attempt, Evaluation, Problem, Submission


class ProblemRepository(ABC):
    @abstractmethod
    def get(self, problem_id: str) -> Optional[Problem]: ...

    @abstractmethod
    def list_all(self) -> List[Problem]: ...


class AttemptRepository(ABC):
    @abstractmethod
    def save(self, attempt: Attempt) -> None: ...

    @abstractmethod
    def get(self, attempt_id: str) -> Optional[Attempt]: ...

    @abstractmethod
    def list_for_learner(self, learner_id: str) -> List[Attempt]: ...


class SubmissionRepository(ABC):
    @abstractmethod
    def save(self, submission: Submission) -> None: ...

    @abstractmethod
    def get(self, submission_id: str) -> Optional[Submission]: ...

    @abstractmethod
    def find_by_idempotency_key(self, attempt_id: str, key: str) -> Optional[Submission]: ...


class EvaluationRepository(ABC):
    @abstractmethod
    def save(self, evaluation: Evaluation) -> None: ...

    @abstractmethod
    def get_for_submission(self, submission_id: str) -> Optional[Evaluation]: ...
