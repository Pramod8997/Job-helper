# Stage: Human checkpoint (`human_checkpoint`)

## Purpose

Ensures a human reviews the draft resume, project recommendation, and
Critic's report **before** the system spends another model call generating
the interview kit. This exists because the interview kit is the most
expensive stage and the least useful one to generate against a resume the
candidate wouldn't actually want to use.

## Two implementation tiers — build the simple one first, then upgrade

### Tier 1: pass-through (build this first)

A no-op node that returns `{}` and does nothing. The actual "human review"
happens in the CLI (printing the draft and prompting for y/N before writing
the final file) or is left to the API caller (the `/run` endpoint returns
both the draft and the final kit in one response, with a note to review the
draft before trusting the kit). This is good enough for v1 — it proves the
graph shape is right without requiring real pause/resume infrastructure.

### Tier 2: true interrupt/resume (build this second, once Tier 1 works end-to-end)

For a real product (e.g. a web frontend where the user clicks "approve" on
a draft they're looking at, possibly hours later), you need the graph to
**actually pause** and resume from exactly where it left off. This requires:

1. A LangGraph checkpointer — e.g. `SqliteSaver` (or a Postgres-backed
   equivalent for production) — passed to `graph.compile(checkpointer=...)`.
   Look up the current LangGraph documentation for the exact import path and
   constructor signature, since checkpointer APIs have changed across
   LangGraph versions and should not be guessed from memory.
2. Compile the graph with `interrupt_before=["interview_coach_agent"]` (or
   pass this at invoke time, depending on the LangGraph version's API).
3. A `thread_id` (part of LangGraph's `config` parameter) generated per run,
   used to look up the paused state later.
4. Two API endpoints instead of one:
   - `POST /run` — starts the graph, runs through the critic/revise loop,
     stops at the interrupt, returns the draft + a `run_id` (the
     `thread_id`).
   - `POST /approve/{run_id}` — resumes the graph from the checkpoint
     (`graph.invoke(None, config={"configurable": {"thread_id": run_id}})`)
     and returns the final `InterviewKit`.
   - Optionally `POST /reject/{run_id}` accepting human feedback text, which
     re-runs `generation_crew` with that feedback instead of proceeding —
     i.e. a human-triggered version of the same revise loop the Critic
     triggers automatically.

## Edge cases to handle (Tier 2 only)

| Case | Required behavior |
|---|---|
| `/approve/{run_id}` called with an unknown or already-completed `run_id` | Return a clear 404/409, not a raw exception. |
| Human rejects with feedback after the Critic already passed | Treat it the same as a Critic failure: route back to `generation_crew` with the human's feedback merged into the `feedback` string passed to the generation agents. |

## What NOT to do

Don't build Tier 2 before Tier 1 is fully tested end-to-end (including the
Critic's revise loop). Checkpointer setup adds real complexity (persistence,
thread IDs, resume semantics) — verify the rest of the graph is correct
first so you're not debugging two things at once.

## Acceptance test

- Tier 1: assert `human_checkpoint(state)` returns `{}` and doesn't raise
  for any valid state.
- Tier 2: an integration test that calls `/run`, confirms the response does
  NOT contain a final `interview_kit` yet (true pause), then calls
  `/approve/{run_id}` and confirms it does.
