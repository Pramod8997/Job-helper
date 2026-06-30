# Agent: Capability ledger (`ledger_agent`)

## Purpose

This is the grounding stage that the original blueprint was missing. It
converts raw, freeform profile text into a structured `CapabilityLedger`
that every later agent must treat as the only allowed source of truth.
Get this agent wrong (i.e. let it embellish) and the anti-hallucination
guarantee of the whole system collapses, because everything downstream
trusts its output.

## Input

`state["raw_profile_text"]` — a freeform string. Expect this to be informal:
bullet points, run-on sentences, possibly inconsistent tense. Do not require
a specific format from the user; the agent's job is to handle messiness.

## Output

A `CapabilityLedger` (see `01-data-models.md`), returned as the state update
`{"ledger": CapabilityLedger(...)}`.

## System prompt — exact intent to encode

The system prompt must instruct the model to:
- Extract a structured profile **strictly** from what is explicitly stated.
- **Never invent, infer, or embellish** anything not explicitly present.
- When something is ambiguous (e.g. "I know some Docker" — does that count
  as a skill?), prefer **omission over guessing**. It is better for the
  Ledger to under-claim than over-claim, because the Critic agent can only
  catch over-claiming in the *resume*, not under-claiming in the Ledger —
  an omitted true fact just means a slightly thinner resume, while an
  invented Ledger fact propagates as a lie all the way to the interview kit.
- Treat this output as the only source of truth all later resume and
  interview content must be traceable to.

## Edge cases to handle

| Case | Required behavior |
|---|---|
| Profile text mentions a skill only in passing ("read about Kubernetes") | Do not list it under `skills` as if hands-on. If you want to preserve the signal, it's acceptable to leave it out entirely — under-claiming is the safe failure mode here. |
| Profile text is very short (one or two sentences) | Still produce a valid `CapabilityLedger` with mostly-empty lists rather than erroring. The Critic and downstream agents must handle a sparse Ledger gracefully. |
| Profile text contains conflicting statements (e.g. mentions two different "final year"s) | Extract the more specific/recent statement; do not average or invent a resolution. |
| Profile text in a language other than English | Out of scope for v1 — assume English input. Note this as a known limitation in the README rather than silently mishandling it. |

## Model tier

`MODEL_FAST` — this is extraction, not creative generation. No reasoning
about job fit happens here.

## Stub for DRY_RUN testing

Return a small, clearly-synthetic `CapabilityLedger` dict with 3-5 skills,
1-2 experience bullets, one education entry, and one project — enough for
downstream agents (Resume Architect, Critic) to have real content to
operate on in dry-run integration tests.

## Unit test to write

Call `ledger_agent({"raw_profile_text": "..."})` in DRY_RUN mode and assert:
- Returns a dict with key `"ledger"`.
- The value is an instance of `CapabilityLedger`.
- No list field contains an empty string.
