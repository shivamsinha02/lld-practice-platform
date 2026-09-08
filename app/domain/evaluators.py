"""
Evaluation strategies.

Design intent (answers the assignment's "which parts should be
deterministic" question directly):

  1. StructuralGateEvaluator — deterministic, free, instant. Checks
     that the submission has enough substance to evaluate at all
     (required sections present, minimum length, at least one class
     named). If this fails, we never spend an AI call: the submission
     is marked FAILED with actionable, specific feedback.

  2. A RubricEvaluator (HeuristicRubricEvaluator or LLMRubricEvaluator)
     — judgment-heavy dimensions (responsibilities, coupling, pattern
     use, extensibility) that a keyword check cannot meaningfully
     assess. LLMRubricEvaluator is used automatically when an API key
     is configured; HeuristicRubricEvaluator is a deterministic,
     always-available fallback so the prototype runs with zero setup.

  3. CompositeEvaluator — orchestrates 1 then 2, and is the only thing
     the rest of the app depends on (Evaluator interface). Swapping in
     a third evaluator (rule-based static analysis, human review) is
     "implement Evaluator, register it" — no change to the practice
     flow, submission state machine, or API layer. This is the
     assignment's "Change Test B".
"""
from __future__ import annotations

import json
import os
import re
from abc import ABC, abstractmethod
from typing import List, Optional

from app.domain.models import CriterionResult, Evaluation, Problem, Submission, new_id
from app.domain.rubric import DEFAULT_RUBRIC, weights


class EvaluationError(Exception):
    """Raised when an evaluator cannot produce a result (timeout, bad
    LLM output, network failure, ...). Caught by the service layer and
    turned into a FAILED submission with a retry option — never a
    crash, and never a silently wrong score."""


class Evaluator(ABC):
    name: str

    @abstractmethod
    def evaluate(self, problem: Problem, submission: Submission) -> Evaluation:
        ...


# ---------------------------------------------------------------------------
# 1. Deterministic structural gate
# ---------------------------------------------------------------------------

REQUIRED_SECTIONS = {
    "requirements": [r"requirement", r"assumption"],
    "responsibilities": [r"class", r"responsibilit"],
    "relationships": [r"relationship", r"interact", r"depends on", r"composition", r"aggregat"],
    "tradeoffs": [r"trade-?off", r"pattern", r"decision"],
    "extensibility": [r"extend", r"extensib", r"if .* changes?", r"future"],
}

MIN_LENGTH = 200


class StructuralGateResult:
    def __init__(self, passed: bool, missing: List[str], length_ok: bool, class_count: int):
        self.passed = passed
        self.missing = missing
        self.length_ok = length_ok
        self.class_count = class_count


class StructuralGateEvaluator:
    """Not a full Evaluator (doesn't produce rubric scores) — a cheap
    pre-check the CompositeEvaluator runs first."""

    name = "structural-gate"

    def check(self, submission: Submission) -> StructuralGateResult:
        text = submission.content.lower()
        missing = []
        for section, patterns in REQUIRED_SECTIONS.items():
            if not any(re.search(p, text) for p in patterns):
                missing.append(section)

        # crude but effective: "class Foo", "Foo class", "ParkingSpot",
        # capitalized-word heuristics for identifying named classes.
        class_count = len(
            set(re.findall(r"\bclass\s+([A-Z][A-Za-z0-9_]*)", submission.content))
            | set(re.findall(r"\b([A-Z][a-zA-Z]+(?:[A-Z][a-zA-Z]+)+)\b", submission.content))
        )

        length_ok = len(submission.content.strip()) >= MIN_LENGTH
        passed = length_ok and len(missing) == 0 and class_count >= 1
        return StructuralGateResult(passed, missing, length_ok, class_count)


# ---------------------------------------------------------------------------
# 2a. Heuristic rubric evaluator (deterministic fallback / offline mode)
# ---------------------------------------------------------------------------

_KEYWORD_SIGNALS = {
    "requirement_understanding": [r"requirement", r"assumption", r"scope", r"use case"],
    "class_responsibilities": [r"responsib", r"single responsibility", r"owns\b"],
    "coupling_cohesion": [r"coupl", r"cohesi", r"depends on", r"loosely"],
    "encapsulation_interfaces": [r"interface", r"encapsulat", r"private", r"abstract"],
    "abstraction_patterns": [r"pattern", r"strategy", r"factory", r"observer", r"state pattern", r"decorator"],
    "extensibility": [r"extend", r"extensib", r"plug", r"new requirement", r"if .* added"],
    "edge_cases_testability": [r"edge case", r"concurren", r"thread", r"test", r"invalid", r"capacity"],
    "explanation_quality": [r"because", r"trade-?off", r"chose", r"rationale", r"reason"],
}


class HeuristicRubricEvaluator(Evaluator):
    """Deterministic keyword/structure scoring. This is intentionally
    labelled as an approximation everywhere it surfaces (confidence is
    capped at 0.5) — it exists so the prototype is usable without any
    API key, and as the documented fallback when the LLM evaluator
    fails or is disabled, not as a claim that keyword-spotting is real
    design review."""

    name = "heuristic-v1"

    def evaluate(self, problem: Problem, submission: Submission) -> Evaluation:
        text = submission.content.lower()
        results = []
        for criterion in DEFAULT_RUBRIC:
            patterns = _KEYWORD_SIGNALS[criterion.key]
            hits = [p for p in patterns if re.search(p, text)]
            score = min(1.0, 0.25 + 0.25 * len(hits)) if hits else 0.15
            evidence = (
                f"Found signal(s): {', '.join(hits)}"
                if hits
                else "No related terms found in the submission."
            )
            concern = (
                "This is a keyword-based approximation, not a real design review."
                if hits
                else f"Submission doesn't appear to discuss {criterion.name.lower()}."
            )
            suggestion = f"Explicitly call out {criterion.name.lower()} with a concrete example from your design."
            results.append(
                CriterionResult(
                    criterion_key=criterion.key,
                    criterion_name=criterion.name,
                    score=score,
                    evidence=evidence,
                    concern=concern,
                    suggestion=suggestion,
                    confidence=0.4,
                )
            )
        overall = Evaluation.weighted_score(results, weights())
        summary = (
            "Heuristic evaluation (no LLM configured): scores are a rough, keyword-based "
            "approximation intended to keep the practice loop usable offline. Set "
            "ANTHROPIC_API_KEY for a real design review."
        )
        return Evaluation(
            id=new_id("eval"),
            submission_id=submission.id,
            evaluator_name=self.name,
            results=results,
            overall_score=overall,
            summary=summary,
        )


# ---------------------------------------------------------------------------
# 2b. LLM rubric evaluator
# ---------------------------------------------------------------------------

PROMPT_TEMPLATE = """You are evaluating a Low-Level Design (LLD) solution written by a learner practicing software design.

PROBLEM:
{problem_title}

{problem_description}

Requirements:
{requirements}

Discussion points a strong solution might address (not a required checklist, and not the only valid answer):
{discussion_points}

LEARNER'S SUBMISSION:
---
{submission_content}
---

Score the submission against EXACTLY these rubric criteria. For each, return a JSON object with:
- "criterion_key": the exact key given
- "score": a float from 0.0 to 1.0
- "evidence": a short quote or precise paraphrase from the submission that justifies the score (or "not addressed")
- "concern": the single biggest issue for this criterion, or "" if none
- "suggestion": one concrete, actionable improvement
- "confidence": your confidence in this score, 0.0 to 1.0

Criteria:
{criteria_list}

Judge on the merits of THIS design, not similarity to any single reference solution — multiple valid designs exist. Be specific: cite what the learner actually wrote, don't give generic advice.

Respond with ONLY a JSON object of this exact shape, no markdown fences, no commentary:
{{"criteria": [ ... one object per criterion above ... ], "summary": "2-3 sentence overall summary"}}
"""


class LLMRubricEvaluator(Evaluator):
    """Calls the Anthropic API with a fixed rubric and demands
    structured JSON output — deliberately not "is this a good design?
    give it a score out of 100", per the assignment's own warning
    against unconstrained scoring prompts."""

    name = "llm-claude-v1"

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-6"):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model
        if not self.api_key:
            raise EvaluationError("No ANTHROPIC_API_KEY configured for LLMRubricEvaluator")

    def _build_prompt(self, problem: Problem, submission: Submission) -> str:
        criteria_list = "\n".join(
            f'- key="{c.key}" name="{c.name}": {c.description}' for c in DEFAULT_RUBRIC
        )
        return PROMPT_TEMPLATE.format(
            problem_title=problem.title,
            problem_description=problem.description,
            requirements="\n".join(f"- {r}" for r in problem.requirements),
            discussion_points="\n".join(f"- {d}" for d in problem.discussion_points),
            submission_content=submission.content,
            criteria_list=criteria_list,
        )

    def evaluate(self, problem: Problem, submission: Submission) -> Evaluation:
        try:
            import anthropic
        except ImportError as e:
            raise EvaluationError(f"anthropic package not installed: {e}")

        try:
            client = anthropic.Anthropic(api_key=self.api_key)
            resp = client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[{"role": "user", "content": self._build_prompt(problem, submission)}],
            )
            raw = "".join(block.text for block in resp.content if hasattr(block, "text"))
            raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            data = json.loads(raw)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            raise EvaluationError(f"LLM returned unparseable output: {e}")
        except Exception as e:  # network/auth/rate-limit/etc.
            raise EvaluationError(f"LLM call failed: {e}")

        rubric_keys = {c.key for c in DEFAULT_RUBRIC}
        results = []
        for item in data.get("criteria", []):
            if item.get("criterion_key") not in rubric_keys:
                continue  # ignore hallucinated criteria rather than fail the whole evaluation
            from app.domain.rubric import by_key
            crit = by_key(item["criterion_key"])
            results.append(
                CriterionResult(
                    criterion_key=crit.key,
                    criterion_name=crit.name,
                    score=max(0.0, min(1.0, float(item.get("score", 0)))),
                    evidence=str(item.get("evidence", ""))[:600],
                    concern=str(item.get("concern", ""))[:400],
                    suggestion=str(item.get("suggestion", ""))[:400],
                    confidence=max(0.0, min(1.0, float(item.get("confidence", 0.6)))),
                )
            )
        if not results:
            raise EvaluationError("LLM response contained no usable rubric results")

        overall = Evaluation.weighted_score(results, weights())
        return Evaluation(
            id=new_id("eval"),
            submission_id=submission.id,
            evaluator_name=self.name,
            results=results,
            overall_score=overall,
            summary=str(data.get("summary", "")).strip(),
        )


# ---------------------------------------------------------------------------
# 3. Composite: gate + rubric evaluator, with graceful fallback
# ---------------------------------------------------------------------------

class CompositeEvaluator(Evaluator):
    """The only Evaluator the service layer talks to directly."""

    name = "composite-v1"

    def __init__(self, rubric_evaluator: Evaluator, gate: Optional[StructuralGateEvaluator] = None):
        self.rubric_evaluator = rubric_evaluator
        self.gate = gate or StructuralGateEvaluator()

    def evaluate(self, problem: Problem, submission: Submission) -> Evaluation:
        gate_result = self.gate.check(submission)
        if not gate_result.passed:
            reasons = []
            if not gate_result.length_ok:
                reasons.append(f"submission is too short (< {MIN_LENGTH} characters)")
            if gate_result.missing:
                reasons.append("missing sections: " + ", ".join(gate_result.missing))
            if gate_result.class_count == 0:
                reasons.append("no named classes were detected")
            raise StructuralGateFailure("; ".join(reasons))

        return self.rubric_evaluator.evaluate(problem, submission)


class StructuralGateFailure(Exception):
    """Distinct from EvaluationError: this is not a system failure, it's
    a deterministic 'not ready for AI review yet' verdict, so the
    service layer reports it differently (immediately, with specific
    missing-sections feedback, no retry-suggests-it-might-just-work
    framing)."""


def build_default_evaluator() -> CompositeEvaluator:
    """Factory: picks the LLM evaluator when a key is configured,
    otherwise falls back to the heuristic evaluator. This is the single
    place that decision is made."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        try:
            return CompositeEvaluator(rubric_evaluator=LLMRubricEvaluator(api_key=api_key))
        except EvaluationError:
            pass
    return CompositeEvaluator(rubric_evaluator=HeuristicRubricEvaluator())
