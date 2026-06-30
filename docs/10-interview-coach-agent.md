# Agent: Interview & mock coach (`interview_coach_agent`)

## Purpose

Final stage. Builds the interview prep kit from everything produced so far.
This is the payoff stage — the system's entire value proposition is "you can
walk into the interview room with this."

## Input

- `CapabilityLedger`
- `JobProfile`
- `ProjectBlueprint` (the new project, since the candidate should be able to
  speak to it as if mid-progress or completed)

## Output

An `InterviewKit` (see `01-data-models.md`).

## System prompt — exact intent to encode

- Generate role-specific **technical questions** based on `JobProfile`
  (hard skills, tech stack).
- Generate **behavioral questions** appropriate to the role and seniority
  implied by the JD.
- Generate **STAR-framed answer outlines** for the behavioral questions —
  index-aligned with `behavioral_questions` (the Nth answer outline
  corresponds to the Nth behavioral question) — grounded **only** in the
  `CapabilityLedger` and the `ProjectBlueprint`. Never invent an achievement
  to fit a STAR answer; if the Ledger doesn't support a strong answer to a
  given behavioral question, the outline should say so honestly (e.g. point
  to the closest real example, even if imperfect) rather than fabricate a
  better one.

## Edge cases to handle

| Case | Required behavior |
|---|---|
| Ledger has very limited experience (e.g. a student) | Behavioral questions and STAR outlines should lean on academic/project experience and the new `ProjectBlueprint`, not assume professional work history that doesn't exist. |
| JD implies a senior/leadership role but Ledger shows junior-level experience | Generate questions appropriate to the role (since that's what they'll actually be asked), but STAR outlines must stay honest about the candidate's actual level — don't invent leadership experience to answer a leadership question. It's fine, and often necessary, for an outline to candidly acknowledge limited experience and instead emphasize related transferable experience. |

## Model tier

`MODEL_JUDGE` — same tier as the Critic, since generating a STAR outline
that stays honestly grounded while still being a *good* answer requires
judgment, not just extraction.

## Stub for DRY_RUN testing

A small `InterviewKit` with 2 technical questions, 1 behavioral question,
and exactly 1 STAR answer outline (matching the 1 behavioral question, to
test the index-alignment expectation even in stub form).

## Unit test to write

Call in DRY_RUN mode and assert `len(interview_kit.behavioral_questions) ==
len(interview_kit.star_answers)` — this index-alignment invariant should be
enforced as an assertion in the agent function itself (not just hoped for),
since misaligned lists would silently produce a STAR answer that doesn't
match its question once rendered into the final kit.
