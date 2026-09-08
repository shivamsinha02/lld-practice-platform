# AI Usage

AI tools were used during the development of this prototype as a development and research assistant.

The primary uses of AI were:
- Exploring possible domain models and class responsibilities.
- Reviewing alternative approaches for the evaluation pipeline.
- Improving implementation details and identifying edge cases.
- Assisting with test-case ideas and documentation structure.
- Reviewing trade-offs around extensibility, asynchronous evaluation, and persistence.

The final architecture was reviewed and adapted to fit the scope and constraints of the assignment.

## Key Design Decisions

### 1. Attempt and Submission Relationship

An Attempt and Submission are modeled as 1:1 for the MVP.

A "Try Again" action creates a new Attempt rather than modifying a previous submission. This keeps the evaluation state machine simple and makes attempt history easier to compare over time.

A future version could support multiple submissions or drafts within a single Attempt if iterative editing becomes an important part of the product.

### 2. Heuristic Evaluator as a Fallback

The prototype supports two rubric evaluation approaches:

- LLM-based evaluation when an API key is configured.
- A deterministic heuristic evaluator when an API key is unavailable.

This allows the application to remain runnable without external configuration while still supporting richer AI-based evaluation when available.

The heuristic evaluator is intentionally treated as a fallback approximation rather than a replacement for human-quality design review.

### 3. Structured Rubric-Based Evaluation

Instead of asking an evaluator for a single score, the system uses a fixed eight-criterion rubric.

Each criterion produces:
- Score
- Evidence
- Concern
- Suggestion
- Confidence

This makes feedback more actionable and allows learners to compare their performance across attempts using consistent dimensions.

The evaluator is also instructed to judge the learner's design on its own merits rather than requiring it to match a single reference solution.

### 4. Background Evaluation

Evaluation can involve an external LLM and therefore should not block the submission request.

For the MVP, evaluation runs through a background thread. The submission is persisted before evaluation begins and its state progresses through:

`SUBMITTED → EVALUATING → COMPLETED / FAILED`

A production implementation could replace the thread with a durable task queue such as Celery or another job-processing system without changing the core Evaluator interface.

### 5. Repository Abstraction

Persistence is kept behind repository interfaces even though the MVP uses SQLite.

This keeps the domain and service layers independent from storage details and makes the system easier to test and extend.

The abstraction is intentionally limited to the repositories required by the current domain rather than introducing a larger dependency-injection or enterprise architecture.

## AI-Assisted Development Principles

AI suggestions were treated as inputs rather than automatically accepted decisions.

For architectural choices, alternatives were considered based on:
- Assignment scope
- Simplicity
- Testability
- Extensibility
- Failure handling
- Implementation cost

The resulting implementation intentionally keeps the system as a small monolith and avoids unnecessary distributed-system complexity.