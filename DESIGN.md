# Design Note — LLD Practice Platform

## 1. MVP scope

The practice loop, and nothing beyond it:

```
Choose problem → Design (text) → Submit → Structural gate → Rubric evaluation
    → Feedback (per-dimension, evidence-linked) → History → Try again (new attempt)
```

5 curated problems (Parking Lot, Elevator, Vending Machine, Library
Management, Rate Limiter), one submission format, one evaluation pipeline,
persistent attempt history. Explicitly **not** built: user accounts/auth
(a `learner_id` string stands in for identity), a diagram editor, code
execution/compilation, multi-evaluator voting, or any HLD-scale concerns
(this is a single-process monolith with SQLite — intentionally, per the
assignment's scope boundary).

## 2. The submission format decision

LLD can be expressed as text, code, a diagram, or some combination. I chose
**structured text** alone for the MVP:

| Format | What it proves | Cost to support well |
|---|---|---|
| Text design | Requirements, responsibilities, relationships, reasoning | Low — a textarea + a rubric prompt |
| Code | Concrete interfaces, coupling, testability | High — needs a sandboxed execution/compile step, language-specific analysis |
| Diagram | Structure, relationships, abstraction at a glance | High — needs a diagram editor/renderer and a way to feed it to an evaluator |

Text is the smallest format that still forces a learner to externalize the
things this assignment's rubric cares about: *why* they split responsibility
this way, not just *that* classes exist. It's also the only format where a
plain-text prompt to an LLM (or a regex-based heuristic) can evaluate it
directly, with no additional infrastructure. Code and diagrams are real,
valuable extensions — not requirements for proving the core loop works.

## 3. User flow

1. Learner browses 5 problems (title, difficulty, tags).
2. Learner opens a problem, reads requirements, clicks **Start Attempt** →
   creates an `Attempt` (`IN_PROGRESS`).
3. Learner writes a design in a guided textarea (template: Requirements &
   Assumptions / Classes & Responsibilities / Relationships / Patterns &
   Trade-offs / Extensibility) and clicks **Submit**.
4. Submission is persisted immediately (`SUBMITTED`), *before* any
   evaluation runs.
5. A structural gate runs synchronously and cheaply. If it fails (too short,
   missing sections, no named classes), the submission is marked `FAILED`
   with the exact missing pieces — no AI call spent on unreviewable input.
6. If the gate passes, evaluation continues in the background
   (`EVALUATING`) — an LLM evaluator if configured, otherwise a deterministic
   heuristic evaluator — against a fixed 8-criterion rubric.
7. On completion (`COMPLETED`) the learner sees an overall score plus, per
   criterion: score, evidence quoted/paraphrased from *their* submission, the
   biggest concern, one concrete suggestion, and the evaluator's confidence.
8. The learner can review this any time via **History**, and start a new
   `Attempt` on the same or a different problem to try again.

## 4. Core domain model

```
Problem            (curated; id, title, description, requirements, discussion points)
  └── Attempt       (one practice session: problem_id, learner_id, status)
        └── Submission   (1:1 with Attempt; content, format, status)
              └── Evaluation  (produced by an Evaluator; results + overall_score)
                    └── CriterionResult[]  (per rubric dimension)
```

**Why Attempt and Submission are 1:1, not 1:many.** "Try again" in the
practice loop means *starting a new Attempt*, not editing a past submission.
This keeps both state machines linear (no "which revision is this feedback
for?" ambiguity) and makes History meaningful: each Attempt is an immutable
snapshot, so a learner can watch the *same rubric dimensions* move across
attempts over time — which is the actual point of History, not just a
changelog of edits.

**Key classes and their responsibilities:**

| Class | Owns | Explicitly does not own |
|---|---|---|
| `Problem` | Static curated content | Any mutable state |
| `Attempt` | Learner/problem pairing, IN_PROGRESS→SUBMITTED transition | Submission content, evaluation |
| `Submission` | Content, its own state machine (`SUBMITTED→EVALUATING→COMPLETED/FAILED`, with `FAILED→EVALUATING` for retry) | How it's evaluated |
| `Evaluator` (interface) | Producing an `Evaluation` from a `Problem` + `Submission` | Persistence, HTTP, retry policy |
| `StructuralGateEvaluator` | Deterministic completeness check | Any judgment about design quality |
| `HeuristicRubricEvaluator` / `LLMRubricEvaluator` | Rubric-based scoring, one implementation each | Knowing which one should run — that's the factory's job |
| `CompositeEvaluator` | Orchestrating gate → rubric evaluator | Anything gate/rubric-specific |
| `PracticeService` | The whole learner journey: attempts, submission, idempotency, background evaluation, history | Persistence details (delegates to repositories), HTTP concerns (delegates to the API layer) |
| `*Repository` (interfaces) | Persistence contract | Domain logic |

Each class exists because it owns exactly one of: content, a state
transition, a scoring strategy, or orchestration. `Attempt`/`Submission` are
split (rather than one fat "Submission" class) specifically so that adding a
second submission per attempt later — or letting an attempt be abandoned —
doesn't require touching the state machine that governs evaluation.

## 5. Evaluation approach

**What's deterministic vs. what needs judgment**, mapped directly onto two
components with a hard boundary between them:

- **Deterministic — `StructuralGateEvaluator`**: required sections present,
  minimum length, at least one named class. Fast, free, and — importantly —
  it runs *first*, so a submission too sparse to say anything meaningful
  about never reaches (and never wastes) an AI call. This directly answers
  the assignment's question about where the deterministic/AI line should
  sit: structure and completeness are checkable with regex; whether those
  classes have good responsibilities is not.
- **Judgment-heavy — rubric evaluators**: `HeuristicRubricEvaluator`
  (keyword/structure signals, deterministic but only an approximation — it's
  labelled as such everywhere it surfaces, confidence capped at 0.5) and
  `LLMRubricEvaluator` (structured prompt, fixed rubric, forced JSON output:
  `criterion → score → evidence → concern → suggestion → confidence`). The
  factory (`build_default_evaluator`) picks the LLM evaluator automatically
  when `ANTHROPIC_API_KEY` is set, and falls back to the heuristic evaluator
  otherwise — so the prototype runs with **zero configuration**, and a real
  LLM review is a one-line env var away.

**Avoiding "give it a score out of 100."** The rubric is fixed and public
(`app/domain/rubric.py`): 8 named dimensions with explicit weights
(requirement understanding, class responsibilities, coupling/cohesion,
encapsulation/interfaces, abstraction & pattern use, extensibility, edge
cases & testability, explanation quality). The LLM prompt requires evidence
from the learner's own text for every score, explicitly instructs the model
to judge the submission on its own merits rather than against one reference
solution, and rejects any criterion key it doesn't recognize rather than
silently trusting whatever the model returns.

## 6. Handling time and failure (kept practical, per the scope boundary)

- **Submission is persisted before evaluation starts.** A crash mid-evaluation
  never loses the learner's work — it's re-run via retry, not re-typed.
- **Evaluation doesn't block the submit request.** It runs on a background
  thread (`PracticeService._run_evaluation`); the client polls
  `GET /api/submissions/{id}` for status. In a real deployment this thread
  becomes a task queue (Celery/RQ) — the `Evaluator` interface and
  `PracticeService` public methods wouldn't change at all.
- **Explicit states**: `Submitted → Evaluating → Completed / Failed`, with
  `Failed → Evaluating` allowed for retry. Illegal transitions
  (e.g. `Submitted → Completed`) raise `InvalidStateTransition` rather than
  silently succeeding.
- **Idempotency**: `submit()` is keyed on `(attempt_id, idempotency_key)`. A
  client retry after a timeout returns the existing submission instead of
  creating a duplicate or double-spending an LLM call. A per-submission
  in-memory lock additionally prevents two concurrent evaluation runs (e.g. a
  UI double-click on Retry) from both hitting the LLM at once.
- **Evaluator failures degrade to a clear state, not a crash.** Both a
  structural-gate failure and an unhandled evaluator exception (network
  error, unparseable LLM output) result in a `FAILED` submission with a
  human-readable reason and a retry option — the distinction between "your
  design isn't ready for review" (gate) and "the reviewer broke" (evaluator
  exception) is preserved in the failure reason rather than collapsed into
  one generic error.

## 7. The two change tests

**Change Test A — add a new submission format (e.g. class diagram) later.**
`SubmissionFormat` is already an enum with one member; `Submission.content`
is opaque to the domain layer (a string today, could be a diagram DSL/JSON
tomorrow). `Attempt`, the state machine, `PracticeService`, and the
`Evaluator` interface are all format-agnostic. The actual work is: (1) add
`SubmissionFormat.DIAGRAM`, (2) write a validator, (3) write a
`DiagramRubricEvaluator` implementing the same `Evaluator` interface. Nothing
about attempts, history, or the state machine changes.

**Change Test B — add a second evaluation approach (rule-based static
analysis, or human review) later.** `Evaluator` is already an interface with
three implementations (structural, heuristic, LLM) composed via
`CompositeEvaluator`. A human-review evaluator would implement the same
interface and could return a `Submission` held in a `PENDING_REVIEW`-like
state (one more `SubmissionStatus` member) or simply queue for a reviewer
and complete asynchronously exactly like the LLM path does today.
`PracticeService.submit()` and the API layer never inspect *which*
evaluator ran — they only depend on the interface.

## 8. Key trade-offs and limitations

- **SQLite + one process.** Fine for a prototype and for the assignment's
  explicit "simple monolith is completely acceptable" guidance. The
  repository interfaces exist specifically so this is swappable without
  touching domain logic — see README §"What I'd extend first" for what
  actually breaks first at scale (spoiler: the background-thread evaluator,
  not the database).
- **Heuristic evaluator is intentionally weak.** It's a fallback for running
  without an API key, not a claim that keyword-matching is real design
  review — every piece of heuristic output says so.
- **No reference solution, on purpose** — but that also means the rubric's
  weighting and the LLM's judgment are the only checks on evaluation
  quality. A production version would want inter-rater calibration (e.g.
  spot-checking LLM scores against a human reviewer periodically).
- **Attempt/Submission 1:1** simplifies the state machine but means a
  learner can't "save a draft and come back" mid-design — `IN_PROGRESS`
  attempts aren't persisted until submit. Acceptable for a 2-day MVP; a
  natural next step (see README).
- **The idempotency-key race in retry** (two concurrent retries can both
  pass the "is it FAILED?" check before either transitions the state) is
  caught by the evaluation lock, not the state check itself — good enough
  for a prototype, not how I'd rely on it under real concurrent load.
