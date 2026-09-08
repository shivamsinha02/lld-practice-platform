# LLD Practice Platform

A small, working prototype of a practice loop for Low-Level Design: choose a
problem, write a design, submit it, get rubric-based feedback grounded in
evidence from your own submission, and see your history across attempts.

See **RESEARCH.md** for the problem/market research, **DESIGN.md** for the
domain model, evaluation approach, and trade-offs, and **AI_USAGE.md** for
how AI was used to build this.

## Stack

- **Backend**: Python 3.11+, FastAPI, SQLite (via stdlib `sqlite3`, no ORM)
- **Frontend**: a single static HTML/JS/CSS page (no build step, no framework)
- **AI (optional)**: Anthropic API for the LLM rubric evaluator — the
  prototype runs fully without it, using a deterministic heuristic evaluator
  as an automatic fallback

## Project layout

```
app/
  domain/        # framework-free domain logic: models, rubric, evaluators, service
  infra/         # SQLite repositories + seed data
  api/           # FastAPI routes, request/response schemas
frontend/
  index.html     # single-page UI, served as static files by FastAPI
tests/           # pytest: domain, evaluators, service, API integration
RESEARCH.md
DESIGN.md
AI_USAGE.md
```

## How to run it
Live Link : https://lld-practice-platform.onrender.com/
```bash
cd lld-practice-platform
python3 -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt

# Optional: enable real LLM-based feedback (otherwise runs with a
# deterministic heuristic evaluator automatically — no config needed)
export ANTHROPIC_API_KEY=sk-ant-...

uvicorn app.api.main:app --reload
```

Open **http://localhost:8000** in a browser. Set a Learner ID (any string —
there's no auth in this MVP), pick a problem, write a design, submit, and
watch it move through `Submitted → Evaluating → Completed`. Check the
**History** tab to see past attempts.

### Running the tests

```bash
pytest tests/ -v
```

Covers: submission/attempt state machine transitions (including illegal
transitions), the structural gate (pass/fail/edge cases like empty input),
the heuristic evaluator, the full service flow (happy path, idempotent
resubmission, structural failure, evaluator-crash failure, retry, 404s), and
HTTP-level integration tests (200/404/409 status codes) via FastAPI's
`TestClient`.

> **A note on how this was verified.** The sandbox I built this in had no
> network access, so I couldn't `pip install` FastAPI/pytest/anthropic there
> to run the full suite end-to-end. I syntax-checked every file
> (`py_compile`) and — more importantly — hand-ran the entire domain and
> service layer (the actual LLD, with no framework dependencies) directly
> against SQLite: full happy path, idempotency, structural-gate failure,
> evaluator-crash failure, retry, concurrent-retry locking, and background
> threaded evaluation with polling. That caught and fixed one real bug (a
> stale in-memory object being returned instead of the post-evaluation
> state). The FastAPI layer is a thin, mechanical wrapper over that same
> service — but I'd run `pytest tests/` myself as the very first step in any
> real environment before trusting it further.

## What I'd extend first

In priority order, and why:

1. **A real task queue for evaluation** (Celery/RQ) instead of a Python
   thread. The thread works for a prototype but doesn't survive a process
   restart mid-evaluation, and doesn't scale past one machine. This is the
   first thing I'd change if this had real users — and per DESIGN.md §7,
   it's a swap behind the existing `Evaluator` interface, not a rewrite.
2. **Draft-saving for in-progress attempts.** Right now an `Attempt` isn't
   persisted with any content until submit — closing the tab mid-design
   loses your draft. Small addition to `Attempt` + a periodic-save endpoint.
3. **A second submission format (diagram or code)**, to actually exercise
   Change Test A rather than just design for it. Diagram is more
   interesting for LLD; code would need a sandboxed execution step, which
   is a genuinely bigger lift.
4. **Inter-rater calibration for the LLM evaluator** — spot-check its scores
   against a human reviewer on a sample of submissions periodically, since
   right now the rubric's weights and the LLM's judgment are the only
   quality control on feedback.
5. **Basic auth**, once `learner_id` needs to mean something real rather
   than being a free-text convenience field.

## Known limitations

- No authentication — `learner_id` is a free-text field the client provides.
- The heuristic evaluator (used when no API key is set) is a deliberately
  crude keyword-based approximation, not real design review — it exists so
  the loop is demonstrable offline, and it labels itself as such everywhere
  it surfaces.
- Attempt and Submission are 1:1 — no draft-saving, no multiple submissions
  per attempt (see DESIGN.md §8).
- SQLite, single process — appropriate for this assignment's scope
  boundary, not for real concurrent load.
