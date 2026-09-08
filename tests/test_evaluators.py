import pytest

from app.domain.evaluators import (
    CompositeEvaluator,
    HeuristicRubricEvaluator,
    StructuralGateEvaluator,
    StructuralGateFailure,
)
from app.domain.models import Submission, SubmissionFormat, SubmissionStatus, new_id
from app.domain.rubric import DEFAULT_RUBRIC
from tests.conftest import GOOD_SUBMISSION, TOO_SHORT_SUBMISSION


def make_submission(content):
    return Submission(
        id=new_id("sub"),
        attempt_id="att_1",
        format=SubmissionFormat.TEXT_DESIGN,
        content=content,
        idempotency_key="k1",
        status=SubmissionStatus.EVALUATING,
    )


class TestStructuralGate:
    def test_well_formed_submission_passes(self):
        result = StructuralGateEvaluator().check(make_submission(GOOD_SUBMISSION))
        assert result.passed
        assert result.class_count >= 1

    def test_too_short_submission_fails(self):
        result = StructuralGateEvaluator().check(make_submission(TOO_SHORT_SUBMISSION))
        assert not result.passed
        assert not result.length_ok

    def test_missing_sections_are_reported_individually(self):
        content = "x" * 250 + " this has requirements and assumption but nothing else useful class Foo"
        result = StructuralGateEvaluator().check(make_submission(content))
        assert "relationships" in result.missing
        assert "tradeoffs" in result.missing

    def test_empty_submission_fails(self):
        result = StructuralGateEvaluator().check(make_submission(""))
        assert not result.passed
        assert result.class_count == 0


class TestHeuristicRubricEvaluator:
    def test_scores_all_rubric_criteria(self, repos):
        problem = repos["problems"].get("parking-lot")
        evaluation = HeuristicRubricEvaluator().evaluate(problem, make_submission(GOOD_SUBMISSION))
        criterion_keys = {r.criterion_key for r in evaluation.results}
        expected_keys = {c.key for c in DEFAULT_RUBRIC}
        assert criterion_keys == expected_keys

    def test_overall_score_is_between_0_and_1(self, repos):
        problem = repos["problems"].get("parking-lot")
        evaluation = HeuristicRubricEvaluator().evaluate(problem, make_submission(GOOD_SUBMISSION))
        assert 0.0 <= evaluation.overall_score <= 1.0

    def test_richer_submission_scores_at_least_as_well_as_sparse_one(self, repos):
        problem = repos["problems"].get("parking-lot")
        sparse = "class Foo: does things. " * 20  # padding to pass length gate
        rich_eval = HeuristicRubricEvaluator().evaluate(problem, make_submission(GOOD_SUBMISSION))
        sparse_eval = HeuristicRubricEvaluator().evaluate(problem, make_submission(sparse))
        assert rich_eval.overall_score >= sparse_eval.overall_score

    def test_confidence_is_capped_reflecting_heuristic_nature(self, repos):
        problem = repos["problems"].get("parking-lot")
        evaluation = HeuristicRubricEvaluator().evaluate(problem, make_submission(GOOD_SUBMISSION))
        assert all(r.confidence <= 0.5 for r in evaluation.results)


class TestCompositeEvaluator:
    def test_gate_failure_raises_before_rubric_evaluation_runs(self, repos):
        problem = repos["problems"].get("parking-lot")
        composite = CompositeEvaluator(rubric_evaluator=HeuristicRubricEvaluator())
        with pytest.raises(StructuralGateFailure):
            composite.evaluate(problem, make_submission(TOO_SHORT_SUBMISSION))

    def test_gate_pass_returns_full_evaluation(self, repos):
        problem = repos["problems"].get("parking-lot")
        composite = CompositeEvaluator(rubric_evaluator=HeuristicRubricEvaluator())
        evaluation = composite.evaluate(problem, make_submission(GOOD_SUBMISSION))
        assert evaluation.overall_score > 0
