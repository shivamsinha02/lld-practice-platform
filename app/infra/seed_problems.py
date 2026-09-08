from __future__ import annotations

from app.domain.models import Difficulty, Problem
from app.domain.repositories import ProblemRepository

SEED_PROBLEMS = [
    Problem(
        id="parking-lot",
        title="Parking Lot System",
        difficulty=Difficulty.MEDIUM,
        tags=["OOP basics", "state"],
        description=(
            "Design a parking lot that supports multiple levels, multiple spot sizes "
            "(motorcycle, compact, large), and multiple entry/exit points."
        ),
        requirements=[
            "A vehicle is assigned the smallest spot size that fits it.",
            "The system tracks real-time availability per spot size and per level.",
            "A ticket is issued on entry and a fee is computed on exit based on duration.",
            "Support at least three vehicle types: motorcycle, car, bus.",
        ],
        discussion_points=[
            "How is spot allocation strategy decoupled from the parking lot itself?",
            "What happens when the lot is full — is that handled gracefully?",
            "How would a new pricing scheme be added without touching spot logic?",
            "Is a bus (needs multiple contiguous spots) handled without special-casing everywhere?",
        ],
    ),
    Problem(
        id="elevator-system",
        title="Elevator System",
        difficulty=Difficulty.HARD,
        tags=["scheduling", "state machine"],
        description=(
            "Design the control system for a bank of elevators in a building, handling "
            "external hall calls and internal cabin requests."
        ),
        requirements=[
            "Support multiple elevators serving the same set of floors.",
            "An elevator has a direction (up/idle/down) and a queue of requests.",
            "The dispatch logic decides which elevator answers a new hall call.",
            "Requests in the current direction of travel are served before reversing.",
        ],
        discussion_points=[
            "Where does scheduling/dispatch logic live relative to a single Elevator's own state machine?",
            "How would you swap the dispatch strategy (nearest-car vs zone-based) later?",
            "How are simultaneous requests from multiple floors handled without race conditions?",
            "What's the elevator's own state machine — idle/moving/door-open — and who's allowed to change it?",
        ],
    ),
    Problem(
        id="vending-machine",
        title="Vending Machine",
        difficulty=Difficulty.EASY,
        tags=["state machine"],
        description=(
            "Design a vending machine that accepts coins, lets a user select a product, "
            "dispenses it if funds and stock are sufficient, and returns change."
        ),
        requirements=[
            "Track inventory per product slot, including quantity.",
            "Accept incremental coin insertion before a selection is made.",
            "Reject a selection if stock is insufficient or funds are insufficient.",
            "Return correct change, or refund fully if the product can't be dispensed.",
        ],
        discussion_points=[
            "Is the machine's behaviour modeled as an explicit state machine (idle, has-money, dispensing, out-of-stock)?",
            "What prevents an invalid transition, like dispensing twice for one payment?",
            "How would adding a card-payment method change the design?",
            "How is 'insufficient change available' as an edge case handled?",
        ],
    ),
    Problem(
        id="library-management",
        title="Library Management System",
        difficulty=Difficulty.MEDIUM,
        tags=["domain modeling"],
        description=(
            "Design a system for a library to manage its catalog, member checkouts, "
            "holds, and overdue fines."
        ),
        requirements=[
            "A book title can have multiple physical copies, each independently checked out.",
            "A member can hold a limited number of items at once.",
            "Support placing a hold on a book that's fully checked out, with a queue.",
            "Compute overdue fines based on days late.",
        ],
        discussion_points=[
            "Is the distinction between a Book (title/metadata) and a BookCopy (physical item) modeled explicitly?",
            "How is the hold queue's fairness (FIFO) enforced and where does that logic live?",
            "How would supporting e-books (no physical copy, no due-date fines) change the model?",
            "What happens if a member tries to check out with existing unpaid fines?",
        ],
    ),
    Problem(
        id="rate-limiter",
        title="API Rate Limiter",
        difficulty=Difficulty.MEDIUM,
        tags=["algorithms", "concurrency"],
        description=(
            "Design an in-process rate limiter that can be applied per API client, "
            "supporting at least two different limiting algorithms."
        ),
        requirements=[
            "Support a fixed limit of N requests per time window per client.",
            "Be able to swap the underlying algorithm (e.g. fixed window vs token bucket) without changing calling code.",
            "Be safe under concurrent requests from the same client.",
            "Provide a clear allow/deny decision plus a retry-after hint when denied.",
        ],
        discussion_points=[
            "Is the algorithm behind a common interface (Strategy) so it can be swapped per-route or per-client?",
            "Where does per-client state live, and how is it cleaned up so memory doesn't grow unbounded?",
            "How is thread-safety achieved without serializing all requests through one global lock?",
            "How would a distributed version (shared state across processes) change the design, at a high level?",
        ],
    ),
]


def seed(repo: ProblemRepository, saver) -> None:
    """`saver` is a callable that persists a Problem (kept separate from
    the read-only ProblemRepository interface, since seeding is an
    infra-time concern, not a normal domain operation)."""
    for problem in SEED_PROBLEMS:
        saver(problem)
