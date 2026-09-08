from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.schemas import (
    AttemptOut,
    CriterionResultOut,
    EvaluationOut,
    HistoryItemOut,
    ProblemDetail,
    ProblemSummary,
    StartAttemptRequest,
    SubmissionOut,
    SubmissionStatusOut,
    SubmitRequest,
)
from app.domain.evaluators import build_default_evaluator
from app.domain.models import Evaluation, InvalidStateTransition, Submission
from app.domain.services import NotFoundError, PracticeService
from app.infra.db import Database
from app.infra.seed_problems import seed
from app.infra.sqlite_repositories import (
    SqliteAttemptRepository,
    SqliteEvaluationRepository,
    SqliteProblemRepository,
    SqliteSubmissionRepository,
)

DB_PATH = os.environ.get("LLD_DB_PATH", "data/practice.db")

db = Database(DB_PATH)
problem_repo = SqliteProblemRepository(db)
attempt_repo = SqliteAttemptRepository(db)
submission_repo = SqliteSubmissionRepository(db)
evaluation_repo = SqliteEvaluationRepository(db)

if not problem_repo.list_all():
    seed(problem_repo, problem_repo.save)

service = PracticeService(
    problems=problem_repo,
    attempts=attempt_repo,
    submissions=submission_repo,
    evaluations=evaluation_repo,
    evaluator=build_default_evaluator(),
)

app = FastAPI(title="LLD Practice Platform")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


# --- serialization helpers -------------------------------------------------

def _submission_out(s: Submission) -> SubmissionOut:
    return SubmissionOut(
        id=s.id,
        attempt_id=s.attempt_id,
        status=s.status.value,
        created_at=s.created_at.isoformat(),
        updated_at=s.updated_at.isoformat(),
        failure_reason=s.failure_reason,
    )


def _evaluation_out(e: Evaluation) -> EvaluationOut:
    return EvaluationOut(
        id=e.id,
        evaluator_name=e.evaluator_name,
        overall_score=e.overall_score,
        summary=e.summary,
        results=[
            CriterionResultOut(
                criterion_key=r.criterion_key,
                criterion_name=r.criterion_name,
                score=r.score,
                evidence=r.evidence,
                concern=r.concern,
                suggestion=r.suggestion,
                confidence=r.confidence,
            )
            for r in e.results
        ],
        created_at=e.created_at.isoformat(),
    )


def _attempt_out(a) -> AttemptOut:
    return AttemptOut(
        id=a.id,
        problem_id=a.problem_id,
        learner_id=a.learner_id,
        status=a.status.value,
        created_at=a.created_at.isoformat(),
        submission_id=a.submission_id,
    )


# --- routes ------------------------------------------------------------

@app.get("/api/problems", response_model=list[ProblemSummary])
def list_problems():
    return [
        ProblemSummary(id=p.id, title=p.title, difficulty=p.difficulty.value, tags=p.tags)
        for p in service.list_problems()
    ]


@app.get("/api/problems/{problem_id}", response_model=ProblemDetail)
def get_problem(problem_id: str):
    try:
        p = service.get_problem(problem_id)
    except NotFoundError as e:
        raise HTTPException(404, str(e))
    return ProblemDetail(
        id=p.id,
        title=p.title,
        difficulty=p.difficulty.value,
        tags=p.tags,
        description=p.description,
        requirements=p.requirements,
    )


@app.post("/api/attempts", response_model=AttemptOut)
def start_attempt(req: StartAttemptRequest):
    try:
        attempt = service.start_attempt(req.problem_id, req.learner_id)
    except NotFoundError as e:
        raise HTTPException(404, str(e))
    return _attempt_out(attempt)


@app.get("/api/attempts/{attempt_id}", response_model=AttemptOut)
def get_attempt(attempt_id: str):
    try:
        return _attempt_out(service.get_attempt(attempt_id))
    except NotFoundError as e:
        raise HTTPException(404, str(e))


@app.post("/api/attempts/{attempt_id}/submissions", response_model=SubmissionOut)
def submit(attempt_id: str, req: SubmitRequest):
    try:
        submission = service.submit(attempt_id, req.content, req.idempotency_key)
    except NotFoundError as e:
        raise HTTPException(404, str(e))
    except InvalidStateTransition as e:
        raise HTTPException(409, str(e))
    return _submission_out(submission)


@app.get("/api/submissions/{submission_id}", response_model=SubmissionStatusOut)
def get_submission(submission_id: str):
    try:
        submission = service.get_submission(submission_id)
    except NotFoundError as e:
        raise HTTPException(404, str(e))
    evaluation = service.get_evaluation(submission_id)
    return SubmissionStatusOut(
        submission=_submission_out(submission),
        evaluation=_evaluation_out(evaluation) if evaluation else None,
    )


@app.post("/api/submissions/{submission_id}/retry", response_model=SubmissionOut)
def retry(submission_id: str):
    try:
        submission = service.retry_evaluation(submission_id)
    except NotFoundError as e:
        raise HTTPException(404, str(e))
    except InvalidStateTransition as e:
        raise HTTPException(409, str(e))
    return _submission_out(submission)


@app.get("/api/learners/{learner_id}/history", response_model=list[HistoryItemOut])
def history(learner_id: str):
    items = service.learner_history(learner_id)
    return [
        HistoryItemOut(
            attempt=_attempt_out(item["attempt"]),
            submission=_submission_out(item["submission"]) if item["submission"] else None,
            evaluation=_evaluation_out(item["evaluation"]) if item["evaluation"] else None,
        )
        for item in items
    ]


# Serve the frontend as static files at "/"
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
