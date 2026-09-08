import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.domain.evaluators import CompositeEvaluator, Evaluator, HeuristicRubricEvaluator
from app.domain.services import PracticeService
from app.infra.db import Database
from app.infra.seed_problems import seed
from app.infra.sqlite_repositories import (
    SqliteAttemptRepository,
    SqliteEvaluationRepository,
    SqliteProblemRepository,
    SqliteSubmissionRepository,
)

GOOD_SUBMISSION = """
## Requirements & Assumptions
- Vehicles: motorcycle, car, bus. Assumption: bus needs 3 contiguous compact spots.

## Classes & Responsibilities
class ParkingLot: owns levels, coordinates spot allocation.
class Level: owns spots for one floor.
class ParkingSpot: represents a single spot, knows its size and occupancy.
class SpotAllocationStrategy: interface for choosing a spot (Strategy pattern).

## Relationships / Interactions
ParkingLot depends on SpotAllocationStrategy via interface. Level aggregates ParkingSpot.

## Patterns & Trade-offs
Used Strategy pattern for allocation so the policy can change independently of ParkingLot.

## Extensibility
If a new vehicle type is added, only allocation rules change; ParkingLot itself is untouched.
"""

TOO_SHORT_SUBMISSION = "Just a parking lot with cars."


@pytest.fixture
def db(tmp_path):
    return Database(str(tmp_path / "test.db"))


@pytest.fixture
def repos(db):
    problems = SqliteProblemRepository(db)
    seed(problems, problems.save)
    return {
        "problems": problems,
        "attempts": SqliteAttemptRepository(db),
        "submissions": SqliteSubmissionRepository(db),
        "evaluations": SqliteEvaluationRepository(db),
    }


class FlakyEvaluator(Evaluator):
    """Always raises — simulates an LLM/network failure for testing the
    failure path without needing real network access."""

    name = "flaky-test"

    def evaluate(self, problem, submission):
        raise RuntimeError("simulated evaluator crash")


@pytest.fixture
def service(repos):
    evaluator = CompositeEvaluator(rubric_evaluator=HeuristicRubricEvaluator())
    return PracticeService(
        problems=repos["problems"],
        attempts=repos["attempts"],
        submissions=repos["submissions"],
        evaluations=repos["evaluations"],
        evaluator=evaluator,
        run_in_background=False,  # synchronous for deterministic tests
    )


@pytest.fixture
def service_with_flaky_evaluator(repos):
    evaluator = CompositeEvaluator(rubric_evaluator=FlakyEvaluator())
    return PracticeService(
        problems=repos["problems"],
        attempts=repos["attempts"],
        submissions=repos["submissions"],
        evaluations=repos["evaluations"],
        evaluator=evaluator,
        run_in_background=False,
    )
