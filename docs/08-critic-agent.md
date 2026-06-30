# Agent: QA & feasibility critic (`critic_agent`)

## Purpose

The single most important agent for the system's integrity guarantee. It is
the only agent whose job is to **disagree** with the generation crew, and
it's what makes the revise loop meaningful rather than decorative. Build
this carefully — a critic that rubber-stamps everything makes the whole
"grounding" architecture pointless.

## Input

- `CapabilityLedger`
- `ResumeDraft`
- `ProjectBlueprint`

## Output

A `CriticReport` (see `01-data-models.md`), plus a state update that
increments `revision_count`:

```
{
  "critic_report": CriticReport(...),
  "revision_count": state.get("revision_count", 0) + (0 if report.passed else 1),
}
```

## System prompt — exact intent to encode

The critic must perform three distinct checks, and the prompt should ask
for all three explicitly rather than a vague "review this":

1. **Claim verification.** For every item in `resume.claims`, check whether
   it is traceable to the `CapabilityLedger`. Anything not traceable goes
   into `unsupported_claims`. Be strict here — "traceable" means the
   Ledger actually supports the claim, not that the claim is merely
   plausible.
2. **ATS-parseability check.** Scan the resume markdown for structural
   issues: tables, multi-column hints, embedded images/graphics, unusual
   characters. List any found in `issues`.
3. **Feasibility check.** Evaluate the `ProjectBlueprint` against the
   Ledger's apparent skill level and the stated `estimated_weeks`. Flag
   anything that looks unrealistic (scope too large for the timeframe, or
   requiring skills/tools far beyond what the Ledger shows) in
   `feasibility_concerns`.

The prompt must also instruct: **set `passed=false` if there are any
unsupported claims or serious feasibility concerns** — minor wording issues
alone don't need to fail the gate, but factual integrity and basic
buildability do.

## Critical implementation detail: don't trust the model's `passed` field blindly

Add a code-level safety net after parsing the model's JSON response,
**before** returning the state update:

```
if result["unsupported_claims"]:
    result["passed"] = False
```

This guards against the model setting `passed=true` while still listing
unsupported claims — a real failure mode language models exhibit
(inconsistency between structured sub-fields and an overall verdict field).
Do not rely on prompt wording alone to prevent this; enforce it in code.

## Revision loop interaction

This agent's output is read by `route_after_critic` in the graph (see
`11-orchestration-graph.md`) to decide whether to loop back to
`generation_crew` or proceed to `human_checkpoint`. The `revision_count`
increment happening **inside this agent** (not in the routing function) is
deliberate — it keeps the counting logic next to the thing being counted,
and means the routing function can stay a pure "read state, return a
string" function with no side effects.

## Edge cases to handle

| Case | Required behavior |
|---|---|
| Resume makes zero claims (very sparse) | `unsupported_claims` should be empty (nothing to be unsupported), `passed` can be `true` if no other issues — sparse-but-honest should pass. |
| Project blueprint is conservative/small | Should generally pass feasibility — being *too* easy isn't a failure mode this system needs to police as strictly as being too ambitious. |
| Same issue gets flagged on consecutive revision attempts | This is a signal the generation crew isn't addressing feedback, not a critic bug — the `max_revisions` cap in the graph handles this case, not this agent. |

## Model tier

`MODEL_JUDGE` — this requires real judgment, not extraction. Do not
downgrade to `MODEL_FAST` to save cost; a weak critic defeats the purpose
of the entire architecture.

## Stub for DRY_RUN testing

Provide **two** stubs for integration testing, not just one:
- A `passed=True` stub with empty issue lists, for testing the happy path.
- A `passed=False` stub with at least one item in `unsupported_claims`, for
  testing the revise loop actually triggers (see `11-orchestration-graph.md`
  for how to use this in an integration test that mocks the critic to fail
  N times before passing).

## Unit tests to write

1. DRY_RUN happy-path stub round-trips correctly and `passed=True`.
2. Construct a `CriticReport` dict with `passed=True` but a non-empty
   `unsupported_claims` list, run it through the post-processing safety net
   described above, and assert it gets corrected to `passed=False`.
