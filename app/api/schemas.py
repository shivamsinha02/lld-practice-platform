from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ProblemSummary(BaseModel):
    id: str
    title: str
    difficulty: str
    tags: List[str]


class ProblemDetail(ProblemSummary):
    description: str
    requirements: List[str]


class StartAttemptRequest(BaseModel):
    problem_id: str
    learner_id: str = Field(..., min_length=1)


class AttemptOut(BaseModel):
    id: str
    problem_id: str
    learner_id: str
    status: str
    created_at: str
    submission_id: Optional[str] = None


class SubmitRequest(BaseModel):
    content: str
    idempotency_key: str = Field(..., min_length=1)


class SubmissionOut(BaseModel):
    id: str
    attempt_id: str
    status: str
    created_at: str
    updated_at: str
    failure_reason: Optional[str] = None


class CriterionResultOut(BaseModel):
    criterion_key: str
    criterion_name: str
    score: float
    evidence: str
    concern: str
    suggestion: str
    confidence: float


class EvaluationOut(BaseModel):
    id: str
    evaluator_name: str
    overall_score: float
    summary: str
    results: List[CriterionResultOut]
    created_at: str


class SubmissionStatusOut(BaseModel):
    submission: SubmissionOut
    evaluation: Optional[EvaluationOut] = None


class HistoryItemOut(BaseModel):
    attempt: AttemptOut
    submission: Optional[SubmissionOut] = None
    evaluation: Optional[EvaluationOut] = None
