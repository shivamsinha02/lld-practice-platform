"""
PracticeService — the single orchestrator of the learner journey:
choose problem -> start attempt -> submit -> evaluate -> review -> retry.

Key decisions (mirrors the assignment's "keep scale practical" guidance):
  - The submission is persisted with status SUBMITTED *before* evaluation
    starts, so a crash mid-evaluation never loses the learner's work.
  - Evaluation runs on a background thread (simulating an async worker)
    so submitting doesn't block on LLM latency. A real deployment would
    swap the thread for a task queue (Celery/RQ) — the service's public
    interface would not change.
  - Idempotency: re-submitting the same content for the same attempt
    (e.g. a double-click, or a client retry after a timed-out request)
    returns the existing submission rather than creating a duplicate or
    double-charging an LLM call.
  - A submission's own in-memory lock prevents two threads from
    processing the same submission concurrently (defence against a
    retry racing an in-flight evaluation).
"""
from __future__ import annotations

import threading
from typing import Dict, List, Optional

from app.domain.evaluators import Evaluator, StructuralGateFailure
from app.domain.models import (
    Attempt,
    AttemptStatus,
    Evaluation,
    InvalidStateTransition,
    Submission,
    SubmissionFormat,
    SubmissionStatus,
    new_id,
)
from app.domain.repositories import (
    AttemptRepository,
    EvaluationRepository,
    ProblemRepository,
    SubmissionRepository,
)


class NotFoundError(Exception):
    pass


class PracticeService:
    def __init__(
        self,
        problems: ProblemRepository,
        attempts: AttemptRepository,
        submissions: SubmissionRepository,
        evaluations: EvaluationRepository,
        evaluator: Evaluator,
        run_in_background: bool = True,
    ):
        self.problems = problems
        self.attempts = attempts
        self.submissions = submissions
        self.evaluations = evaluations
        self.evaluator = evaluator
        self.run_in_background = run_in_background
        self._locks: Dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    # -- Problems -----------------------------------------------------

    def list_problems(self):
        return self.problems.list_all()

    def get_problem(self, problem_id: str):
        problem = self.problems.get(problem_id)
        if not problem:
            raise NotFoundError(f"No such problem: {problem_id}")
        return problem

    # -- Attempts -------------------------------------------------------

    def start_attempt(self, problem_id: str, learner_id: str) -> Attempt:
        self.get_problem(problem_id)  # raises NotFoundError if invalid
        attempt = Attempt(id=new_id("att"), problem_id=problem_id, learner_id=learner_id)
        self.attempts.save(attempt)
        return attempt

    def get_attempt(self, attempt_id: str) -> Attempt:
        attempt = self.attempts.get(attempt_id)
        if not attempt:
            raise NotFoundError(f"No such attempt: {attempt_id}")
        return attempt

    def learner_history(self, learner_id: str) -> List[dict]:
        """Returns attempts newest-first, each enriched with its
        submission + evaluation if present — exactly what the History
        view needs in one call."""
        attempts = sorted(
            self.attempts.list_for_learner(learner_id), key=lambda a: a.created_at, reverse=True
        )
        out = []
        for attempt in attempts:
            submission = self.submissions.get(attempt.submission_id) if attempt.submission_id else None
            evaluation = self.evaluations.get_for_submission(submission.id) if submission else None
            out.append({"attempt": attempt, "submission": submission, "evaluation": evaluation})
        return out

    # -- Submission -----------------------------------------------------

    def submit(
        self,
        attempt_id: str,
        content: str,
        idempotency_key: str,
        submission_format: SubmissionFormat = SubmissionFormat.TEXT_DESIGN,
    ) -> Submission:
        attempt = self.get_attempt(attempt_id)

        existing = self.submissions.find_by_idempotency_key(attempt_id, idempotency_key)
        if existing:
            return existing  # idempotent replay: no duplicate work, no duplicate AI spend

        if attempt.status != AttemptStatus.IN_PROGRESS:
            raise InvalidStateTransition(
                f"Attempt {attempt_id} already has a submission. Start a new attempt to try again."
            )

        submission = Submission(
            id=new_id("sub"),
            attempt_id=attempt_id,
            format=submission_format,
            content=content,
            idempotency_key=idempotency_key,
            status=SubmissionStatus.SUBMITTED,
        )
        # Persist BEFORE evaluation starts: the learner's work survives
        # even if the evaluator crashes or the process restarts.
        self.submissions.save(submission)
        attempt.mark_submitted(submission.id)
        self.attempts.save(attempt)

        self._run_evaluation(submission.id)
        # Re-fetch: in synchronous/test mode, evaluation has already run by
        # this point and mutated the persisted record; in background mode
        # this is still SUBMITTED, which is the correct thing to return.
        return self.submissions.get(submission.id)

    def retry_evaluation(self, submission_id: str) -> Submission:
        submission = self.submissions.get(submission_id)
        if not submission:
            raise NotFoundError(f"No such submission: {submission_id}")
        if submission.status not in (SubmissionStatus.FAILED,):
            raise InvalidStateTransition(
                f"Can only retry a FAILED submission (current status: {submission.status})"
            )
        self._run_evaluation(submission_id)
        return self.submissions.get(submission_id)

    def _lock_for(self, submission_id: str) -> threading.Lock:
        with self._locks_guard:
            if submission_id not in self._locks:
                self._locks[submission_id] = threading.Lock()
            return self._locks[submission_id]

    def _run_evaluation(self, submission_id: str) -> None:
        if self.run_in_background:
            t = threading.Thread(target=self._evaluate_now, args=(submission_id,), daemon=True)
            t.start()
        else:
            self._evaluate_now(submission_id)

    def _evaluate_now(self, submission_id: str) -> None:
        lock = self._lock_for(submission_id)
        if not lock.acquire(blocking=False):
            return  # an evaluation for this submission is already in flight

        try:
            submission = self.submissions.get(submission_id)
            if submission is None:
                return
            if submission.status == SubmissionStatus.EVALUATING:
                return

            submission.transition(SubmissionStatus.EVALUATING)
            self.submissions.save(submission)

            problem_id = self._attempt_problem_id(submission)
            problem = self.problems.get(problem_id)

            try:
                evaluation = self.evaluator.evaluate(problem, submission)
                self.evaluations.save(evaluation)
                submission.transition(SubmissionStatus.COMPLETED)
            except StructuralGateFailure as gate_fail:
                submission.transition(SubmissionStatus.FAILED, failure_reason=str(gate_fail))
            except Exception as e:  # EvaluationError and anything unexpected
                submission.transition(SubmissionStatus.FAILED, failure_reason=str(e))

            self.submissions.save(submission)
        finally:
            lock.release()

    def _attempt_problem_id(self, submission: Submission) -> str:
        attempt = self.attempts.get(submission.attempt_id)
        return attempt.problem_id

    def get_submission(self, submission_id: str) -> Submission:
        submission = self.submissions.get(submission_id)
        if not submission:
            raise NotFoundError(f"No such submission: {submission_id}")
        return submission

    def get_evaluation(self, submission_id: str) -> Optional[Evaluation]:
        return self.evaluations.get_for_submission(submission_id)
