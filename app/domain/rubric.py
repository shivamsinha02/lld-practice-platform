"""
The fixed rubric. Both the heuristic and the LLM evaluator score
against exactly these dimensions, with exactly these weights, so
results are comparable across evaluators and across attempts over
time (the point of History is to show improvement on the *same*
dimensions, not a shifting scoring scheme).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class Criterion:
    key: str
    name: str
    description: str
    weight: float


DEFAULT_RUBRIC: List[Criterion] = [
    Criterion(
        "requirement_understanding",
        "Requirement Understanding",
        "Did the learner capture the problem's functional requirements and state reasonable assumptions?",
        0.15,
    ),
    Criterion(
        "class_responsibilities",
        "Class Responsibilities",
        "Are responsibilities clearly assigned to classes, each with a single, coherent purpose?",
        0.20,
    ),
    Criterion(
        "coupling_cohesion",
        "Coupling & Cohesion",
        "Are related behaviours grouped together, and are classes loosely coupled to one another?",
        0.15,
    ),
    Criterion(
        "encapsulation_interfaces",
        "Encapsulation & Interfaces",
        "Is internal state hidden behind interfaces/abstractions rather than exposed directly?",
        0.15,
    ),
    Criterion(
        "abstraction_patterns",
        "Abstraction & Pattern Use",
        "Are abstractions (interfaces, base classes, patterns) used where they earn their complexity, and avoided where they don't?",
        0.15,
    ),
    Criterion(
        "extensibility",
        "Extensibility",
        "How much of the design would need to change for a plausible new requirement?",
        0.10,
    ),
    Criterion(
        "edge_cases_testability",
        "Edge Cases & Testability",
        "Does the design consider edge cases (concurrency, capacity, invalid input) and can it be tested in isolation?",
        0.05,
    ),
    Criterion(
        "explanation_quality",
        "Explanation Quality",
        "Is the reasoning behind the design choices clear, not just the choices themselves?",
        0.05,
    ),
]


def weights() -> Dict[str, float]:
    return {c.key: c.weight for c in DEFAULT_RUBRIC}


def by_key(key: str) -> Criterion:
    for c in DEFAULT_RUBRIC:
        if c.key == key:
            return c
    raise KeyError(key)
