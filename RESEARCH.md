# Research Note — LLD Practice Platform

## 1. The learner problem

Low-Level Design is unusual as a skill to self-practice: unlike an algorithms
problem, there's rarely a single correct answer to check against, and unlike
a code kata, "does it compile" says almost nothing about whether it's *well
designed*. A learner can produce a Parking Lot or Vending Machine design and
still have no reliable way to know whether their class boundaries,
responsibilities, and abstractions are actually good — or just plausible.

Talking to this problem from first principles (per the candidate guide):

- **How does a learner currently practice?** Mostly by reading a reference
  solution and comparing it to their own attempt, or by rehearsing out loud
  with no feedback at all.
- **How do they know if it's good?** Usually they don't, beyond "did I use a
  design pattern" — a weak proxy that rewards pattern-spotting over
  judgment.
- **What happens when two valid designs look very different?** Existing
  tools mostly don't address this — feedback (where it exists) is often
  framed as "here's the model answer," not "here's what's strong/weak about
  *your* answer."

## 2. What I looked at

I reviewed a handful of existing LLD prep tools and resources (~2.5 hours):

| Tool | What it actually offers |
|---|---|
| [awesome-low-level-design](https://github.com/ashishps1/awesome-low-level-design) (12k+ stars) / AlgoMaster.io | A large curated library of problems + reference solutions, OOP/pattern/UML theory. Read-only: no submission, no feedback loop. Notably, community comments on this exact repo point out that most of its own reference solutions barely use design patterns beyond Singleton — a reminder that a single "reference solution" is a shaky evaluation baseline even when written by experts. |
| [Hello Interview — LLD Guided Practice](https://www.hellointerview.com/practice/low-level-design) | Walks a learner through an LLD problem step-by-step with "personalized feedback" and worked problem breakdowns. Feedback mechanism isn't detailed publicly; the emphasis is guided walkthroughs of a canonical approach rather than critiquing an independently-produced design. |
| [LLDCanvas](https://www.lldcanvas.in/) | A UML class-diagram editor with 23 pre-wired pattern skeletons, a timed "Interview Mode," and session analytics — streaks, activity heatmaps, practice-time graphs. Strong on *practice habit* tracking; the retained history is about session cadence, not about whether design quality is improving attempt-over-attempt. |
| [LowLevelDesignMastery](https://www.lowleveldesignmastery.com/playground/) | Interactive problems with a UML builder and "AI-powered code review," solutions in six languages. Closest existing analog to an evaluation loop, but marketing emphasis is on the pattern/diagram library and multi-language solutions, not on a transparent, structured rubric behind the AI review. |
| [InterviewBit LLD guide](https://www.interviewbit.com/low-level-design-interview-questions/) / CodeZym | Curated question lists and prep articles/machine-coding drills. Read/consume oriented; no structured submit-and-get-feedback loop on a learner's own design. |

## 3. Gaps this points to

1. **Most tools are libraries, not practice loops.** The dominant pattern is
   "here are problems + here are solutions." Very few let a learner submit
   *their own* design and get feedback on it specifically.
2. **Where feedback loops exist, they're a black box.** "AI code review" or
   "personalized feedback" is mentioned, but not backed by a visible,
   consistent rubric — which risks the exact anti-pattern this assignment
   calls out: asking a model "is this good?" and getting an unfalsifiable
   score.
3. **Reference-solution bias.** Tools built around one canonical answer per
   problem structurally can't handle "two valid designs that look very
   different" — a real design decision is either penalized for not matching,
   or the tool has no opinion at all.
4. **History tracks engagement, not improvement.** Streaks and heatmaps
   (LLDCanvas) measure whether someone practiced, not whether their
   responsibility-assignment or coupling/cohesion is getting better across
   attempts on the *same* dimensions.

## 4. Product direction

Build a small, focused practice loop — choose problem → design → submit →
get rubric-based feedback with evidence → review → try again — where:

- Feedback is scored against a **fixed, published rubric** (same dimensions
  every time), so history is comparable across attempts and isn't a single
  opaque "AI score."
- Every score is **evidence-linked** back to something the learner actually
  wrote, and paired with one concrete concern + one concrete next step —
  useful even when there's no "wrong" answer to compare against.
- The **submission format is text**, not a diagram tool or a code sandbox —
  deliberately the smallest format that still forces a learner to externalize
  requirements, responsibilities, relationships, and trade-offs (see
  DESIGN.md §2 for why this beats over-investing in UML/code tooling for an
  MVP).
- Evaluation is **explicitly split** into a deterministic structural check
  (fast, free, catches "too sparse to review" before spending an AI call)
  and a judgment-heavy rubric pass (heuristic fallback, or an LLM when
  configured) — matching the assignment's own framing of what should and
  shouldn't be deterministic.
