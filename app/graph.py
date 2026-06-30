"""
Orchestration graph — wires agents into a LangGraph StateGraph.

This is the highest-risk integration point: every agent can be individually
correct and the system can still be broken if this wiring is wrong.

Graph shape:
  entry: ledger_agent
  ledger_agent -> profiler_agent
  profiler_agent -> generation_crew
  generation_crew -> critic_agent
  critic_agent -> [conditional] -> generation_crew  (fail + retries left)
  critic_agent -> [conditional] -> human_checkpoint  (pass OR retries exhausted)
  human_checkpoint -> interview_coach_agent
  interview_coach_agent -> END

See: docs/11-orchestration-graph.md, docs/09-human-checkpoint.md
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.agents import (
    critic_agent,
    generation_crew,
    human_checkpoint,
    interview_coach_agent,
    ledger_agent,
    profiler_agent,
)
from app.models import PipelineState


# ---------------------------------------------------------------------------
# Conditional routing function — exact logic from spec
# ---------------------------------------------------------------------------


def route_after_critic(state: dict) -> str:
    """Decide whether to revise or proceed after the critic runs.

    Logic:
      - If the critic passed → proceed to human checkpoint.
      - If retries are exhausted → proceed anyway (don't loop forever).
        The human will see the unresolved issues and can decide.
      - Otherwise → loop back to generation_crew for revision.
    """
    report = state.get("critic_report")
    if report and report.passed:
        return "human_checkpoint"
    if state.get("revision_count", 0) >= state.get("max_revisions", 2):
        return "human_checkpoint"  # proceed anyway, don't loop forever
    return "generation_crew"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_graph() -> StateGraph:
    """Build and compile the Career Crew orchestration graph.

    Returns a compiled graph ready to be invoked with an initial state dict.
    """
    builder = StateGraph(PipelineState)

    # Register nodes
    builder.add_node("ledger_agent", ledger_agent)
    builder.add_node("profiler_agent", profiler_agent)
    builder.add_node("generation_crew", generation_crew)
    builder.add_node("critic_agent", critic_agent)
    builder.add_node("human_checkpoint", human_checkpoint)
    builder.add_node("interview_coach_agent", interview_coach_agent)

    # Linear edges
    builder.set_entry_point("ledger_agent")
    builder.add_edge("ledger_agent", "profiler_agent")
    builder.add_edge("profiler_agent", "generation_crew")
    builder.add_edge("generation_crew", "critic_agent")

    # Conditional edge: the revise loop
    builder.add_conditional_edges(
        "critic_agent",
        route_after_critic,
        {
            "generation_crew": "generation_crew",
            "human_checkpoint": "human_checkpoint",
        },
    )

    # Post-checkpoint → interview → end
    builder.add_edge("human_checkpoint", "interview_coach_agent")
    builder.add_edge("interview_coach_agent", END)

    return builder.compile()
