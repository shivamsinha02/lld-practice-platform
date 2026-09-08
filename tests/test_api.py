"""
Integration tests hitting the real HTTP layer. Uses a temp DB per test
run (via LLD_DB_PATH) so tests never touch data/practice.db.
"""
import os
import time

import pytest

os.environ.setdefault("LLD_DB_PATH", ":memory:")
# NOTE: sqlite ':memory:' is per-connection; since our Database uses one
# connection per thread, this is fine for single-threaded TestClient usage
# but background-evaluation threads would get their own empty DB. We set
# run_in_background off for API tests by monkeypatching below.


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "api_test.db")
    monkeypatch.setenv("LLD_DB_PATH", db_path)
    from fastapi.testclient import TestClient

    # Import after env var is set so main.py picks up the right DB path.
    from app.api import main as main_module

    # Force synchronous evaluation for deterministic assertions in tests.
    main_module.service.run_in_background = False

    return TestClient(main_module.app)


GOOD_SUBMISSION = """
## Requirements & Assumptions
- reqs and assumption text here for the vending machine.

## Classes & Responsibilities
class VendingMachine: owns state. class InventorySlot: tracks stock.

## Relationships / Interactions
VendingMachine depends on InventorySlot via composition.

## Patterns & Trade-offs
State pattern used for machine states; trade-off is more classes for clearer transitions.

## Extensibility
If card payment is added, extend PaymentMethod without touching VendingMachine.
"""


class TestProblemsEndpoints:
    def test_list_problems_returns_seeded_set(self, client):
        resp = client.get("/api/problems")
        assert resp.status_code == 200
        ids = {p["id"] for p in resp.json()}
        assert "parking-lot" in ids
        assert len(ids) == 5

    def test_get_unknown_problem_returns_404(self, client):
        resp = client.get("/api/problems/does-not-exist")
        assert resp.status_code == 404


class TestFullFlow:
    def test_practice_loop_end_to_end(self, client):
        attempt_resp = client.post(
            "/api/attempts", json={"problem_id": "vending-machine", "learner_id": "carol"}
        )
        assert attempt_resp.status_code == 200
        attempt = attempt_resp.json()

        submit_resp = client.post(
            f"/api/attempts/{attempt['id']}/submissions",
            json={"content": GOOD_SUBMISSION, "idempotency_key": "k1"},
        )
        assert submit_resp.status_code == 200
        submission = submit_resp.json()
        assert submission["status"] == "COMPLETED"

        status_resp = client.get(f"/api/submissions/{submission['id']}")
        assert status_resp.status_code == 200
        body = status_resp.json()
        assert body["evaluation"] is not None
        assert len(body["evaluation"]["results"]) == 8  # all rubric criteria present

        history_resp = client.get("/api/learners/carol/history")
        assert history_resp.status_code == 200
        assert len(history_resp.json()) == 1

    def test_duplicate_submission_returns_409(self, client):
        attempt = client.post(
            "/api/attempts", json={"problem_id": "vending-machine", "learner_id": "dave"}
        ).json()
        client.post(
            f"/api/attempts/{attempt['id']}/submissions",
            json={"content": GOOD_SUBMISSION, "idempotency_key": "k1"},
        )
        second = client.post(
            f"/api/attempts/{attempt['id']}/submissions",
            json={"content": GOOD_SUBMISSION, "idempotency_key": "k2"},
        )
        assert second.status_code == 409

    def test_too_short_submission_completes_request_but_marks_failed(self, client):
        attempt = client.post(
            "/api/attempts", json={"problem_id": "vending-machine", "learner_id": "erin"}
        ).json()
        resp = client.post(
            f"/api/attempts/{attempt['id']}/submissions",
            json={"content": "too short", "idempotency_key": "k1"},
        )
        # The HTTP request itself succeeds (200) — failure is a submission
        # STATE, not an HTTP error, since a bad design is an expected outcome.
        assert resp.status_code == 200
        assert resp.json()["status"] == "FAILED"
