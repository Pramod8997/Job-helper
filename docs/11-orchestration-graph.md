# Module: `app/graph.py` — orchestration graph

## Purpose

Wires the individual agents into a LangGraph `StateGraph` with one real
cycle (the revise loop). This is the highest-risk integration point in the
whole system — every agent can be individually correct and the system can
still be broken if this wiring is wrong. Test it in isolation, with mocked
agents, before trusting any end-to-end run.

## Graph shape to implement

```
entry: ledger_agent
ledger_agent -> profiler_agent
profiler_agent -> generation_crew
generation_crew -> critic_agent
critic_agent -> [conditional] -> generation_crew   (if failed AND retries remain)
critic_agent -> [conditional] -> human_checkpoint  (if passed OR retries exhausted)
human_checkpoint -> interview_coach_agent
interview_coach_agent -> END
```

## Nodes

Register each agent function from `app/agents.py` as a node with
`graph.add_node(name, fn)`. The `generation_crew` node should internally
call all three generation sub-agents (Resume Architect, Project Strategist,
Resource Curator) — either sequentially, or in parallel via a thread pool /
async gather for latency, since the three calls are independent of each
other and only need the same two inputs (`ledger`, `job_profile`).

## The conditional routing function — exact logic

```
def route_after_critic(state):
    report = state.get("critic_report")
    if report and report.passed:
        return "human_checkpoint"
    if state.get("revision_count", 0) >= state.get("max_revisions", 2):
        return "human_checkpoint"   # proceed anyway, don't loop forever
    return "generation_crew"
```

Register with `graph.add_conditional_edges("critic_agent", route_after_critic,
{"generation_crew": "generation_crew", "human_checkpoint": "human_checkpoint"})`.

**Why "proceed anyway" rather than failing the whole run when retries are
exhausted:** the alternative (erroring out) wastes all the work already
done and gives the human nothing to look at. Proceeding to the human
checkpoint with the Critic's unresolved issues still attached to state
means a human can see exactly what's wrong and decide whether to manually
fix the resume themselves — strictly more useful than a crashed pipeline.

## `generation_crew`'s feedback wiring

When re-entering `generation_crew` after a failed critic pass, it must read
`state["critic_report"]` and build a feedback string (join `issues +
unsupported_claims + feasibility_concerns`) to pass into the Resume
Architect and Project Strategist calls — see `05-resume-architect-agent.md`
and `06-project-strategist-agent.md` for how those agents use it. If this
wiring is missing, the revise loop will technically execute (the graph will
visit `generation_crew` again) but produce no actual improvement, since the
generation agents won't know what was wrong.

## `max_revisions` default and configurability

Default `2` (meaning: the critic gets up to 2 chances to pass after the
first attempt — i.e. up to 3 total generation attempts). Make this
overridable by the caller (CLI flag, API request field) rather than hardcoded,
since different use cases may want a stricter or looser bound.

## Critical integration test: prove the loop actually loops

This is the single most important test in the whole system, because it's
the one thing that distinguishes this architecture from a simple linear
pipeline. Write it like this:

1. Build the graph normally.
2. Patch/mock `critic_agent` (not the LLM call inside it — the whole node
   function) with a fake that fails on its first two calls and passes on
   its third, tracking a call counter.
3. Invoke the graph with `max_revisions=2`.
4. Assert:
   - The fake critic was called more than once (proves the conditional edge
     actually routes back, not just falls through to the end).
   - `revision_count` in the final state reflects the number of failed
     attempts.
   - `interview_kit` is present in the final state (proves the graph
     reaches `END` rather than looping forever or erroring).
5. Repeat with a critic that *never* passes, and assert the graph still
   terminates (because `max_revisions` was hit) rather than running
   forever — this is the test that would catch a missing or off-by-one
   bound in `route_after_critic`.

## Acceptance criteria for this module

- [ ] Happy path (critic passes first try) reaches `END` with a populated
      `interview_kit`.
- [ ] Critic-fails-then-passes path calls `generation_crew` more than once
      and still reaches `END`.
- [ ] Critic-never-passes path terminates at `max_revisions` rather than
      looping indefinitely.
- [ ] `generation_crew`, when re-entered after a failure, receives and uses
      the Critic's feedback (verify by inspecting the prompt/arguments
      passed to the mocked generation sub-agents in the test, not just that
      the node ran).
