# Agent: Market & ATS profiler (`profiler_agent`)

## Purpose

Converts a raw job description into a structured keyword map. This is what
lets the Resume Architect optimize for ATS keyword matching deliberately
rather than hoping relevant terms appear by accident.

## Input

`state["jd_text"]` — raw job description text, any format the user pastes in
(may include boilerplate company description, benefits section, etc.).

## Output

A `JobProfile` (see `01-data-models.md`), returned as
`{"job_profile": JobProfile(...)}`.

## System prompt — exact intent to encode

- Extract `role_title`, `hard_skills`, `soft_skills`, `ats_keywords`,
  `tech_stack`, `culture_signals`.
- `ats_keywords` specifically means **exact phrases** an automated ATS
  scanner is likely to pattern-match on — not paraphrases or synonyms. E.g.
  if the JD says "CI/CD pipelines", the keyword is `"CI/CD"`, not
  `"automated deployment processes"`.
- `culture_signals` should be inferred from tone/phrasing (e.g. "move fast",
  "ownership mindset", "work-life balance") — these are softer and more
  interpretive than the other fields, which is fine; flag them clearly as
  signals, not hard requirements.
- Ignore irrelevant JD boilerplate (equal-opportunity statements, generic
  company mission text, benefits lists) — don't let it dilute the keyword
  extraction.

## Edge cases to handle

| Case | Required behavior |
|---|---|
| JD lists 30+ requirements (sprawling, unfocused posting) | Prioritize: extract what's clearly emphasized (repeated, listed under "must have") over what appears once under "nice to have". Don't return an unranked dump of every noun phrase in the document. |
| JD is vague/marketing-heavy with few concrete skills | Return what's genuinely extractable; short lists are an acceptable, honest output. Don't fabricate specificity that isn't there. |
| JD has a "nice to have" section | Still extract these into the relevant lists, but downstream agents (Project Strategist especially) should weight "must have" items more heavily when deciding what gap to close — this distinction can optionally be preserved as an ordering convention (must-haves first in each list) since the schema doesn't have a separate priority field. |

## Model tier

`MODEL_FAST` — extraction, not generation.

## Stub for DRY_RUN testing

A small, realistic `JobProfile` for a generic backend/software role — see
the working prototype's stub in `app/agents.py` for a concrete example
shape if you have access to it; otherwise invent one with 3-5 items per
list field.

## Unit test to write

Call `profiler_agent({"jd_text": "..."})` in DRY_RUN mode and assert the
returned `JobProfile` has non-empty `ats_keywords` (this is the field the
rest of the pipeline depends on most).
