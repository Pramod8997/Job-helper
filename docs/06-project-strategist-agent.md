# Agent: Project strategist (`_project_strategist`, part of `generation_crew`)

## Purpose

Designs exactly one project recommendation that closes the gap between what
the candidate can currently do (Ledger) and what the target role wants
(JobProfile). The original blueprint's flaw here was "enterprise-grade
project" language with no constraint on the candidate's actual ability to
build it — this agent exists specifically to fix that.

## Input

- `CapabilityLedger`
- `JobProfile`
- `feedback: str | None` — Critic's feasibility concerns on a revision pass

## Output

A `ProjectBlueprint` (see `01-data-models.md`).

## System prompt — exact intent to encode

- Design **one** project, not a menu of options — indecision isn't useful
  output here.
- The project must close a real, specific gap: identify what's in
  `JobProfile.hard_skills` / `tech_stack` that is **absent** from
  `CapabilityLedger.skills`, and design around that gap specifically.
- Must be realistically buildable by **this specific person** — reference
  their actual current skill level (from the Ledger) when deciding scope.
  A student with no Docker experience should not be assigned a
  multi-service Kubernetes orchestration project as their entry point into
  containers.
- Be concrete: `architecture` should name actual components, not vague
  phrases like "modern, scalable architecture". `milestones` should be
  ordered, buildable steps a person could literally check off one at a
  time.
- `estimated_weeks` must be realistic for someone building this **alongside
  other commitments** (classes, a job, other applications) — bias toward
  smaller, finishable scope over an impressive-sounding but abandoned
  project. An unfinished "enterprise-grade" project helps nobody in an
  interview; a finished small one does.

## Revision behavior

Same pattern as the Resume Architect: append `feedback` (the Critic's
feasibility concerns) to the prompt and require the regenerated blueprint
to specifically address each one — e.g. if flagged as "too large for the
estimated timeframe", the fix should be either a smaller scope or a longer
timeframe, not just a more confident-sounding milestone list for the same
scope.

## Edge cases to handle

| Case | Required behavior |
|---|---|
| Candidate's skills already closely match the JD (no real gap) | Design a project that demonstrates depth/scale in an existing skill rather than forcing an artificial gap. Still produce a genuinely useful project. |
| JD's tech stack is very large (many unfamiliar technologies) | Pick the **highest-leverage** one or two gaps to address, not all of them — a project trying to demonstrate 8 new technologies at once isn't buildable or convincing. |

## Model tier

`MODEL_SMART`.

## Unit test to write

Call with a Ledger missing "Docker" and a JobProfile requiring "Docker",
and assert (in a real call, documented as manual QA since stub data won't
exercise this) that the resulting `tech_stack` includes Docker and
`estimated_weeks` is a small, plausible integer (e.g. 1-6), not something
absurd like 0 or 52.
