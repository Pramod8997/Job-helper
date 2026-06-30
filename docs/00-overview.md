# Career crew — system overview

## What this system does

Given (a) a job description and (b) a person's real background, it produces
an **interview prep kit**: an ATS-optimized resume, one realistically
buildable project recommendation that closes the candidate's skill gap, a
resource cheat sheet, and a grounded interview question bank — without
fabricating anything the candidate hasn't actually done.

## Why a multi-agent graph instead of one prompt

A single prompt asked to do resume writing + project design + resource
search + interview prep at once suffers from **context dilution**: the model
spreads its attention thin and quality drops on every sub-task. Splitting
into specialized agents, each with a narrow system prompt and a typed
input/output contract, fixes this. The architecture is a **graph**, not a
simple pipeline, because one stage (QA) needs to be able to send work back
for revision — that requires a cycle, not just sequential steps.

## Non-negotiable design principles

These five constraints are the actual point of this architecture. Every
module spec in this folder exists to enforce one of them. Do not relax these
during implementation even if it's tempting to simplify:

1. **Grounding over generation.** No agent may state a skill, achievement,
   or metric that isn't traceable to the Capability Ledger (see
   `03-capability-ledger-agent.md`). The Ledger is built once, early, from
   the user's real input, and every later agent reads from it — never from
   the raw freeform text directly.
2. **Verification is a separate agent from generation.** The agent that
   writes the resume must not also be the agent that checks it. Use a
   distinct Critic agent (`08-critic-agent.md`) so there's no incentive
   alignment problem (a generator grading its own work tends to pass it).
3. **Revision is bounded, not optional and not infinite.** If the Critic
   fails the output, the graph must route back to generation — a real cycle,
   not a TODO comment. But it must also have a `max_revisions` cap so a
   stubborn disagreement between Critic and Generator can't loop forever.
4. **A human approves before the expensive step runs.** Interview kit
   generation (the last, most expensive stage) only runs after a human has
   seen the draft resume + project and the Critic's report. This is a real
   pause-and-resume, not a fire-and-forget pipeline.
5. **Every agent is testable without spending a token.** Each agent function
   must support a `DRY_RUN` mode that returns deterministic stub data so the
   *graph wiring* (especially the revise loop and the routing logic) can be
   verified independently of LLM output quality. Build and pass dry-run
   tests before ever calling a real model.

## Architecture

```
[job description text] + [raw profile text]
              │
              ▼
     ┌─────────────────┐
     │ Capability ledger│  (extraction, no creativity)
     └────────┬─────────┘
              ▼
     ┌─────────────────┐
     │ Market & ATS     │  (extraction, no creativity)
     │ profiler         │
     └────────┬─────────┘
              ▼
     ┌─────────────────────────────┐
     │ Generation crew              │
     │ (resume + project + resources)│
     └────────┬─────────────────────┘
              ▼
     ┌─────────────────┐     fail, retries left
     │ QA & feasibility │ ───────────────────────┐
     │ critic           │                         │
     └────────┬─────────┘                         │
              │ pass, or retries exhausted          │
              ▼                                    │
     ┌─────────────────┐                           │
     │ Human checkpoint │                           │
     └────────┬─────────┘                           │
              ▼                                    │
     ┌─────────────────┐                           │
     │ Interview coach  │                           │
     └────────┬─────────┘                           │
              ▼                                    │
        [interview kit]                    (back to generation crew)
```

## Directory structure to build

```
career-crew/
  app/
    __init__.py
    models.py        # 01-data-models.md
    llm.py            # 02-llm-client.md
    agents.py         # 03 through 08, 10
    graph.py          # 09-human-checkpoint.md, 11-orchestration-graph.md
    server.py         # 12-api-server.md
    main.py           # 13-cli.md
  tests/              # 14-testing-strategy.md
  sample_data/
    jd.txt
    profile.txt
  requirements.txt
  .env.example
  README.md
```

## Tech stack and why

| Layer | Choice | Why |
|---|---|---|
| Agent orchestration | LangGraph (`StateGraph`) | Needs a real cycle (critic → generation). CrewAI's sequential/hierarchical model can't express this cleanly. |
| LLM | Claude, via the `anthropic` SDK directly | Avoids an extra abstraction layer; structured output is handled with explicit JSON-mode prompting, not a framework's opinionated wrapper. |
| Backend API | FastAPI | Auto-documented endpoints, plain Pydantic request/response models. |
| Data contracts | Pydantic | Lets the Critic agent programmatically check fields (e.g. iterate `resume.claims`) instead of parsing freeform text. |
| State shape | `TypedDict` (LangGraph state) wrapping Pydantic models | LangGraph nodes return partial-state dicts; Pydantic models nested inside give you validation without fighting the graph library's state-merging conventions. |

## Build order

Build and test in this order — each stage should be runnable and testable
in isolation before moving to the next:

1. `01-data-models.md` — no logic, just schemas. Nothing else compiles without this.
2. `02-llm-client.md` — the structured-call wrapper, with DRY_RUN support.
3. `03` through `08`, `10` — each agent function, one at a time, each with its own stub and its own unit test using the stub.
4. `11-orchestration-graph.md` — wire agents into the graph, test the revise loop specifically (this is the highest-risk integration point).
5. `09-human-checkpoint.md` — upgrade the pass-through checkpoint to a real interrupt/resume.
6. `12-api-server.md` and `13-cli.md` — the two entry points, built last since they depend on everything above.
7. `14-testing-strategy.md` — full test suite, including the end-to-end dry-run.

Do not write the API server or CLI before the graph is tested. Do not wire
the graph before every individual agent has a passing unit test against its
own stub.
