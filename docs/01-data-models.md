# Module: `app/models.py` — data contracts

## Purpose

Every agent's input and output is a typed Pydantic model, not freeform text.
This is what makes the Critic agent possible — it can programmatically
iterate `resume.claims` and check each one, rather than trying to parse
claims out of prose. Build this file first; nothing else compiles without it.

## Models to implement

### `CapabilityLedger`

The single source of truth about the candidate. Every later claim in the
resume or interview kit must be traceable to a field in this object.

| Field | Type | Notes |
|---|---|---|
| `name` | `str` | |
| `summary` | `str` | 1-2 sentence factual summary, not marketing copy |
| `skills` | `List[str]` | Default empty list |
| `experience` | `List[str]` | One bullet per item, factual, no embellishment |
| `education` | `List[str]` | |
| `projects` | `List[str]` | |
| `certifications` | `List[str]` | Default empty list |

**Validation rule to implement:** none of the list fields should contain
empty strings — strip and filter blanks when constructing this from LLM
output (the LLM extraction agent occasionally returns `[""]` for an absent
field instead of `[]`).

### `JobProfile`

Output of the Market & ATS Profiler.

| Field | Type | Notes |
|---|---|---|
| `role_title` | `str` | |
| `hard_skills` | `List[str]` | |
| `soft_skills` | `List[str]` | |
| `ats_keywords` | `List[str]` | Exact phrases an ATS scanner would match on — not synonyms |
| `tech_stack` | `List[str]` | |
| `culture_signals` | `List[str]` | e.g. "fast-paced", "collaborative" — inferred from JD tone/wording |

### `ResumeDraft`

| Field | Type | Notes |
|---|---|---|
| `markdown` | `str` | Single-column markdown. No tables, no multi-column layout hints — ATS parsers choke on these. |
| `keywords_used` | `List[str]` | Subset of `JobProfile.ats_keywords` that actually appear in `markdown` |
| `claims` | `List[str]` | **Critical field.** Every factual statement made in the resume, one per list item, in a form the Critic can string-match or semantically check against the Ledger. E.g. `"Built a multi-agent ML pipeline using Python"`, not `"Strong technical skills"`. |

### `ProjectBlueprint`

| Field | Type | Notes |
|---|---|---|
| `title` | `str` | |
| `description` | `str` | |
| `architecture` | `str` | Short architecture description, not a full design doc |
| `tech_stack` | `List[str]` | |
| `milestones` | `List[str]` | Ordered, concrete, buildable steps |
| `estimated_weeks` | `int` | Default `4`. Must be realistic for one person working part-time alongside other commitments — not an "enterprise-grade" multi-month fantasy. |

### `ResourceKit`

| Field | Type | Notes |
|---|---|---|
| `cheat_sheet_markdown` | `str` | CLI commands, config snippets, key concepts |
| `links` | `List[str]` | See `07-resource-curator-agent.md` — these must come from real search, not model recall, in the production build |

### `CriticReport`

| Field | Type | Notes |
|---|---|---|
| `passed` | `bool` | |
| `issues` | `List[str]` | General problems (ATS-parseability, formatting) |
| `unsupported_claims` | `List[str]` | Items from `ResumeDraft.claims` that do NOT trace back to the `CapabilityLedger` |
| `feasibility_concerns` | `List[str]` | Reasons the `ProjectBlueprint` may not be buildable in scope/time given the Ledger's skill level |

**Rule to implement in the agent, not the model:** `passed` must be `False`
if `unsupported_claims` is non-empty, regardless of what else is true. Don't
let the LLM set `passed=true` with unsupported claims present — validate
this in code as a safety net (see `08-critic-agent.md`).

### `InterviewKit`

| Field | Type | Notes |
|---|---|---|
| `technical_questions` | `List[str]` | |
| `behavioral_questions` | `List[str]` | |
| `star_answers` | `List[str]` | STAR-framed outlines, one per behavioral question, grounded in the Ledger and the new ProjectBlueprint — index-aligned with `behavioral_questions` |

### `PipelineState` (TypedDict, not BaseModel)

This is the LangGraph state shape. Use `TypedDict` with `total=False` (all
keys optional) because LangGraph nodes return **partial** state updates —
each node only returns the keys it sets, and LangGraph merges them into the
running state.

| Key | Type |
|---|---|
| `jd_text` | `str` |
| `raw_profile_text` | `str` |
| `ledger` | `CapabilityLedger` |
| `job_profile` | `JobProfile` |
| `resume` | `ResumeDraft` |
| `project` | `ProjectBlueprint` |
| `resources` | `ResourceKit` |
| `critic_report` | `CriticReport` |
| `revision_count` | `int` |
| `max_revisions` | `int` |
| `human_approved` | `bool` |
| `human_feedback` | `Optional[str]` |
| `interview_kit` | `InterviewKit` |

**Why TypedDict and not a Pydantic model for state specifically:** LangGraph's
default state-merge behavior expects dict-like objects with key-by-key
updates. Wrapping each field's *value* in Pydantic (as above) gives you
validation on the data; using TypedDict for the *container* keeps you
compatible with how `StateGraph` reduces node outputs into state without
extra configuration.

## Acceptance test for this module

Write a test that constructs one instance of each model with valid data and
asserts `.model_dump()` round-trips through `.model_dump_json()` and back via
`Model(**json.loads(...))` without error. This catches schema typos before
any agent code is written against it.
