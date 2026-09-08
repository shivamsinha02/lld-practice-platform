import pytest

from app.domain.models import InvalidStateTransition, SubmissionStatus
from app.domain.services import NotFoundError
from tests.conftest import GOOD_SUBMISSION, TOO_SHORT_SUBMISSION


class TestHappyPath:
    def test_full_practice_loop(self, service):
        attempt = service.start_attempt("parking-lot", "alice")
        assert attempt.status.value == "IN_PROGRESS"

        submission = service.submit(attempt.id, GOOD_SUBMISSION, "key-1")
        assert submission.status == SubmissionStatus.COMPLETED

        evaluation = service.get_evaluation(submission.id)
        assert evaluation is not None
        assert evaluation.overall_score > 0

        history = service.learner_history("alice")
        assert len(history) == 1
        assert history[0]["submission"].id == submission.id
        assert history[0]["evaluation"].id == evaluation.id


class TestIdempotency:
    def test_same_idempotency_key_returns_existing_submission(self, service):
        attempt = service.start_attempt("parking-lot", "alice")
        first = service.submit(attempt.id, GOOD_SUBMISSION, "same-key")
        second = service.submit(attempt.id, GOOD_SUBMISSION, "same-key")
        assert first.id == second.id

    def test_different_key_on_already_submitted_attempt_is_rejected(self, service):
        attempt = service.start_attempt("parking-lot", "alice")
        service.submit(attempt.id, GOOD_SUBMISSION, "key-1")
        with pytest.raises(InvalidStateTransition):
            service.submit(attempt.id, GOOD_SUBMISSION, "key-2")


class TestStructuralFailureAndRetry:
    def test_too_short_submission_fails_without_crashing(self, service):
        attempt = service.start_attempt("vending-machine", "alice")
        submission = service.submit(attempt.id, TOO_SHORT_SUBMISSION, "key-1")
        assert submission.status == SubmissionStatus.FAILED
        assert submission.failure_reason is not None

    def test_retry_on_failed_submission_is_allowed(self, service):
        attempt = service.start_attempt("vending-machine", "alice")
        submission = service.submit(attempt.id, TOO_SHORT_SUBMISSION, "key-1")
        retried = service.retry_evaluation(submission.id)
        # content unchanged, so it fails the gate again — but critically,
        # this does not raise, and the submission is never lost
        assert retried.status == SubmissionStatus.FAILED

    def test_cannot_retry_a_completed_submission(self, service):
        attempt = service.start_attempt("parking-lot", "alice")
        submission = service.submit(attempt.id, GOOD_SUBMISSION, "key-1")
        assert submission.status == SubmissionStatus.COMPLETED
        with pytest.raises(InvalidStateTransition):
            service.retry_evaluation(submission.id)


class TestEvaluatorFailure:
    def test_evaluator_exception_becomes_failed_submission_not_a_crash(
        self, service_with_flaky_evaluator
    ):
        svc = service_with_flaky_evaluator
        attempt = svc.start_attempt("parking-lot", "alice")
        submission = svc.submit(attempt.id, GOOD_SUBMISSION, "key-1")
        assert submission.status == SubmissionStatus.FAILED
        assert "simulated evaluator crash" in submission.failure_reason


class TestNotFoundEdgeCases:
    def test_start_attempt_on_unknown_problem_raises(self, service):
        with pytest.raises(NotFoundError):
            service.start_attempt("no-such-problem", "alice")

    def test_submit_on_unknown_attempt_raises(self, service):
        with pytest.raises(NotFoundError):
            service.submit("no-such-attempt", GOOD_SUBMISSION, "key-1")

    def test_retry_on_unknown_submission_raises(self, service):
        with pytest.raises(NotFoundError):
            service.retry_evaluation("no-such-submission")

    def test_history_for_unknown_learner_is_empty_not_an_error(self, service):
        assert service.learner_history("nobody-ever-practiced") == []
