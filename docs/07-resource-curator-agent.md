# Agent: Resource curator (`_resource_curator`, part of `generation_crew`)

## Purpose

Produces a learning cheat sheet (commands, config snippets, concepts) and a
short list of high-value links relevant to the target role's tech stack.

## Important known gap in the original prototype

The first working build of this agent used model-recalled links — i.e. the
LLM was asked to produce URLs from its training data. **This is unreliable**:
links can be stale, wrong, or hallucinated outright. Do not ship this agent
without real search wired in. This spec describes the production version.

## Input

`JobProfile` — specifically `tech_stack` and `hard_skills`.

## Output

A `ResourceKit` (see `01-data-models.md`).

## Required implementation: real web search

Wire in an actual search capability rather than relying on model recall.
Two reasonable approaches, in order of preference:

1. **Anthropic's server-side web search tool**, if available in the SDK/API
   version you're building against — check current Anthropic API
   documentation for the exact tool name and request shape, since this is
   the kind of detail that changes between SDK versions and shouldn't be
   guessed from memory.
2. **A standalone search API call** (e.g. any search provider's API) made
   from your own code, with results fed back into a follow-up
   `call_structured` call that asks the model to synthesize the cheat sheet
   from real search snippets rather than from its own recall.

Either way, the **links in the final `ResourceKit.links` must come from
actual search results**, not be generated freestanding by the model.

## System prompt — exact intent to encode (for the synthesis step)

- Produce a concise Markdown cheat sheet: CLI commands, config snippets,
  key concepts — skimmable, not a tutorial.
- Links should be **official documentation** where possible (framework
  docs, language docs) over blog posts or aggregator sites — prefer sources
  a hiring manager would also trust.
- Don't pad the list — 3-6 genuinely high-value links beats 15 mediocre
  ones.

## Edge cases to handle

| Case | Required behavior |
|---|---|
| Search returns no good results for an obscure/niche technology | Return fewer links rather than padding with irrelevant ones. An honest short list is better than a list with weak filler. |
| `tech_stack` is very broad | Curate, don't dump — pick the highest-value 1-2 resources per technology rather than every link found. |

## Model tier

`MODEL_FAST` for the synthesis step, since this is mostly formatting +
summarizing real search results rather than open-ended generation.

## Stub for DRY_RUN testing

A small `ResourceKit` with 2-3 plausible-looking links and a short cheat
sheet — fine to hardcode for dry-run graph-wiring tests, since DRY_RUN mode
is explicitly about testing wiring, not search quality.

## Unit/integration test to write

- Unit test (DRY_RUN): same pattern as other agents, assert the stub
  round-trips through `ResourceKit`.
- Separate integration test (real run, not part of the standard test suite
  that needs to pass with no API key): call the real search-backed version
  with a known tech stack (e.g. `["FastAPI", "Redis"]`) and manually verify
  the returned links actually resolve and are relevant. Document this as a
  manual or opt-in test, not a CI-gating one, since it costs real API/search
  calls.
