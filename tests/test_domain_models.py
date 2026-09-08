import pytest

from app.domain.models import (
    Attempt,
    AttemptStatus,
    InvalidStateTransition,
    Submission,
    SubmissionFormat,
    SubmissionStatus,
    new_id,
)


def make_submission(status=SubmissionStatus.SUBMITTED):
    return Submission(
        id=new_id("sub"),
        attempt_id="att_1",
        format=SubmissionFormat.TEXT_DESIGN,
        content="x" * 300,
        idempotency_key="k1",
        status=status,
    )


class TestSubmissionStateMachine:
    def test_submitted_to_evaluating_is_allowed(self):
        s = make_submission(SubmissionStatus.SUBMITTED)
        s.transition(SubmissionStatus.EVALUATING)
        assert s.status == SubmissionStatus.EVALUATING

    def test_evaluating_to_completed_is_allowed(self):
        s = make_submission(SubmissionStatus.EVALUATING)
        s.transition(SubmissionStatus.COMPLETED)
        assert s.status == SubmissionStatus.COMPLETED

    def test_evaluating_to_failed_is_allowed(self):
        s = make_submission(SubmissionStatus.EVALUATING)
        s.transition(SubmissionStatus.FAILED, failure_reason="boom")
        assert s.status == SubmissionStatus.FAILED
        assert s.failure_reason == "boom"

    def test_failed_to_evaluating_is_allowed_for_retry(self):
        s = make_submission(SubmissionStatus.FAILED)
        s.transition(SubmissionStatus.EVALUATING)
        assert s.status == SubmissionStatus.EVALUATING

    def test_submitted_cannot_jump_to_completed(self):
        s = make_submission(SubmissionStatus.SUBMITTED)
        with pytest.raises(InvalidStateTransition):
            s.transition(SubmissionStatus.COMPLETED)

    def test_completed_is_terminal(self):
        s = make_submission(SubmissionStatus.COMPLETED)
        with pytest.raises(InvalidStateTransition):
            s.transition(SubmissionStatus.EVALUATING)


class TestAttemptStateMachine:
    def test_mark_submitted_sets_submission_id(self):
        a = Attempt(id="att_1", problem_id="p1", learner_id="alice")
        a.mark_submitted("sub_1")
        assert a.status == AttemptStatus.SUBMITTED
        assert a.submission_id == "sub_1"

    def test_cannot_mark_submitted_twice(self):
        a = Attempt(id="att_1", problem_id="p1", learner_id="alice")
        a.mark_submitted("sub_1")
        with pytest.raises(InvalidStateTransition):
            a.mark_submitted("sub_2")
