# Build prompt

Paste this into your AI coding tool (Claude Code, Cursor, etc.) with the
`docs/` folder from this package present in the working directory.

---

You are building "career crew", a multi-agent system that turns a job
description and a person's real background into an ATS-optimized resume, a
realistic project recommendation, a resource cheat sheet, and a grounded
interview prep kit.

Full specifications are in the `docs/` folder of this repo:

- `docs/00-overview.md` — read this first. It has the architecture diagram,
  the five non-negotiable design principles, the directory structure, the
  tech stack rationale, and the required build order. Follow the build
  order exactly — do not write the API server or CLI before the orchestration
  graph is tested, and do not wire the graph before every individual agent
  has a passing unit test.
- `docs/01-data-models.md` through `docs/13-cli.md` — one deep-dive spec per
  module, in build order. Each one specifies exact field-by-field schemas,
  system prompt intent, edge cases to handle, and the specific unit
  tests to write for that module.
- `docs/14-testing-strategy.md` — the full test plan and the "definition of
  done" checklist for the whole build.

## Rules for this build

1. **Read every doc file before writing any code.** They reference each
   other (e.g. the Critic agent's spec references the data model spec for
   `CriticReport`) — don't start coding from a partial read.

2. **Follow the build order in `00-overview.md` literally.** After each
   stage, run the tests specified for that stage before moving to the next.
   Do not write ahead — e.g. don't draft `app/server.py` while still working
   through the individual agent specs, even if it seems efficient.

3. **Implement `DRY_RUN` mode first and use it constantly.** Every agent
   needs a working stub before you write its real system prompt. Get the
   entire graph running end-to-end with `DRY_RUN=true` and zero API key
   configured before spending a single real model call on testing.

4. **Do not relax the five design principles in `00-overview.md`** even if
   a simpler implementation is tempting — especially principle #1
   (grounding: no agent may state anything not traceable to the Capability
   Ledger) and principle #3 (the revise loop must be a real graph cycle,
   bounded by `max_revisions`, not a TODO or a fake always-passes critic).

5. **Where a spec tells you to check current documentation instead of
   guessing** (this happens for: exact Claude model name strings, the
   Anthropic SDK's rate-limit exception class, LangGraph's checkpointer
   import path and `interrupt_before` API, and Anthropic's web search tool
   shape) — actually look these up rather than inventing plausible-looking
   names. These are exactly the kind of detail that silently breaks at
   runtime if guessed.

6. **After every module, run that module's acceptance tests before
   continuing.** Each spec file ends with an "acceptance test" or "unit
   test to write" section — implement and run these, don't just write
   implementation code and move on.

7. **Build Tier 1 of the human checkpoint and API server before Tier 2.**
   `09-human-checkpoint.md` and `12-api-server.md` both describe a simple
   pass-through version and a more complex true-interrupt version. Get Tier
   1 fully working and tested first.

8. **At the end, verify the full "definition of done" checklist in
   `14-testing-strategy.md`** and report which items pass and which don't,
   rather than declaring the build complete unprompted.

## What to do when you finish each module

After implementing a module, show me:
- The file(s) you created/changed.
- The test(s) you ran for that module and their output (pass/fail).
- Anything from that module's spec you deviated from, and why.

Then stop and wait for me to say "continue" before moving to the next
module in the build order — I want to review each stage, not just the
final result.

## First step

Start by reading `docs/00-overview.md` and `docs/01-data-models.md`, then
implement `app/models.py` and its acceptance test. Stop there and show me
the result before continuing to `app/llm.py`.
