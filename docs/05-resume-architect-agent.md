# Agent: Resume architect (`_resume_architect`, part of `generation_crew`)

## Purpose

Writes the actual ATS-optimized resume. This is the highest-stakes
generation step in the system — it's also the one most tempted to
embellish, since "make me sound impressive" is the implicit subtext of any
resume-writing task. The system prompt has to actively counteract that.

## Input

- `CapabilityLedger` — the only allowed source of facts.
- `JobProfile` — keywords to weave in truthfully.
- `feedback: str | None` — on a revision pass, the Critic's prior issues,
  unsupported claims, and feasibility concerns, joined into one string.

## Output

A `ResumeDraft` (see `01-data-models.md`).

## System prompt — exact intent to encode

- Single-column, ATS-optimized Markdown. Explicitly forbid: tables,
  multi-column layout markers, images, special characters that ATS parsers
  mishandle.
- **You may ONLY use facts present in the Capability Ledger.** Never invent
  skills, metrics, or experience not in the Ledger. This sentence (or
  equivalent) should appear close to verbatim in the system prompt — it's
  the single most important constraint in this whole system.
- Weave in `JobProfile.ats_keywords` naturally, and **only where truthfully
  applicable** — do not force a keyword in next to a skill the Ledger
  doesn't support.
- Populate the `claims` output field with every factual statement made in
  the resume, one per item, in a form specific enough for the Critic to
  check (e.g. `"Led a team of 4 engineers"` is checkable; `"Strong leader"`
  is not — discourage the latter style of claim entirely, since unverifiable
  fluff isn't useful in a resume anyway and ATS keyword density matters more
  than adjectives).

## Revision behavior

When `feedback` is not `None` (i.e. the Critic failed a prior attempt),
append it to the user prompt as a labeled section, e.g. "Prior critic
feedback to address: {feedback}", and instruct the model to specifically
resolve each listed issue — not just regenerate from scratch and hope.

## Edge cases to handle

| Case | Required behavior |
|---|---|
| Ledger is sparse (few skills/experience) | Write an honest, shorter resume. Do not pad with generic statements to "fill space" — a short, accurate resume beats a long, inflated one. |
| No Ledger items match any `ats_keywords` | Don't force-fit keywords. `keywords_used` can legitimately be a short or empty list; this is useful signal that there's a real skill gap (which the Project Strategist should be addressing). |
| `feedback` flags an unsupported claim from the previous draft | The regenerated resume must not just rephrase the same unsupported claim — it must either find a truthful way to express it or drop it. |

## Model tier

`MODEL_SMART` — this needs real generation quality and the judgment to
balance ATS optimization against truthfulness.

## Unit test to write

1. Call with a Ledger containing exactly one skill ("Python") and assert
   the resume markdown mentions it and `claims` is non-empty.
2. Call with `feedback="resume claims AWS experience not in ledger"` and
   (in a real, non-dry-run smoke test, not a unit test) manually inspect
   that the regenerated draft doesn't repeat that specific claim — this one
   is hard to assert programmatically with stub data, so document it as a
   manual QA step instead of trying to force a unit test for it.
