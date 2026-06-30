"""
Graph integration tests — the highest-priority tests in the system.

These prove:
  1. Happy path: critic passes first try → END with interview_kit.
  2. Revise loop: critic fails then passes → generation_crew called >1 time.
  3. Bounded loop: critic never passes → terminates at max_revisions.
  4. Feedback propagation: generation_crew receives critic feedback on re-entry.

All run with DRY_RUN=true, no API key required.

See: docs/11-orchestration-graph.md
"""

import os
from unittest import mock

import pytest

from app.models import CriticReport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DRY_ENV = {**os.environ, "DRY_RUN": "true"}
_DRY_ENV.pop("ANTHROPIC_API_KEY", None)


def _reload_and_build():
    """Reload modules with DRY_RUN=true and build the graph."""
    import importlib
    import app.llm
    importlib.reload(app.llm)
    import app.agents
    importlib.reload(app.agents)
    import app.graph
    importlib.reload(app.graph)
    return app.graph, app.agents


def _initial_state(max_revisions=2):
    return {
        "jd_text": "We need a backend engineer with Python, Docker, and PostgreSQL.",
        "raw_profile_text": (
            "I am Jane Doe, a CS student at State University. "
            "I know Python, JavaScript, SQL, and Git. "
            "I built a personal expense tracker with Flask and SQLite. "
            "I interned at TechCorp for 3 months as a junior developer."
        ),
        "revision_count": 0,
        "max_revisions": max_revisions,
    }


# ---------------------------------------------------------------------------
# Test 1: Happy path — critic passes first try
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_reaches_end_with_interview_kit(self):
        with mock.patch.dict(os.environ, _DRY_ENV, clear=False):
            graph_mod, agents_mod = _reload_and_build()
            graph = graph_mod.build_graph()
            final_state = graph.invoke(_initial_state())

            assert "interview_kit" in final_state, "Graph should reach END with interview_kit"
            assert final_state["interview_kit"] is not None
            assert final_state.get("revision_count", 0) == 0, (
                "Happy path should not increment revision_count"
            )


# ---------------------------------------------------------------------------
# Test 2: Revise loop — critic fails N times then passes
# ---------------------------------------------------------------------------


class TestReviseLoop:
    def test_critic_called_multiple_times(self):
        """Mock critic to fail on first call, pass on second."""
        with mock.patch.dict(os.environ, _DRY_ENV, clear=False):
            graph_mod, agents_mod = _reload_and_build()

            call_count = {"n": 0}

            # Build fail/pass stubs
            fail_report = CriticReport(
                passed=False,
                issues=["Resume uses table layout"],
                unsupported_claims=["Claimed senior role"],
                feasibility_concerns=[],
            )
            pass_report = CriticReport(
                passed=True,
                issues=[],
                unsupported_claims=[],
                feasibility_concerns=[],
            )

            original_critic = agents_mod.critic_agent

            def mock_critic(state):
                call_count["n"] += 1
                if call_count["n"] <= 1:
                    # First call: fail
                    return {
                        "critic_report": fail_report,
                        "revision_count": state.get("revision_count", 0) + 1,
                    }
                else:
                    # Second call: pass
                    return {
                        "critic_report": pass_report,
                        "revision_count": state.get("revision_count", 0),
                    }

            with mock.patch.object(agents_mod, "critic_agent", mock_critic):
                # Rebuild graph to pick up the mock
                import importlib
                importlib.reload(graph_mod)
                # But we need to patch at the node level — let's patch the
                # module-level reference that graph.py imports
                with mock.patch("app.agents.critic_agent", mock_critic):
                    importlib.reload(graph_mod)
                    graph = graph_mod.build_graph()
                    final_state = graph.invoke(_initial_state(max_revisions=2))

            assert call_count["n"] > 1, (
                f"Critic was only called {call_count['n']} time(s) — "
                "the conditional edge should route back to generation_crew"
            )
            assert "interview_kit" in final_state, "Should still reach END"
            assert final_state.get("revision_count", 0) >= 1

    def test_feedback_propagation(self):
        """When re-entering generation_crew after failure, critic feedback
        must reach the generation sub-agents."""
        with mock.patch.dict(os.environ, _DRY_ENV, clear=False):
            graph_mod, agents_mod = _reload_and_build()

            generation_calls = []
            call_count = {"n": 0}

            fail_report = CriticReport(
                passed=False,
                issues=["Bad formatting"],
                unsupported_claims=["Fake claim"],
                feasibility_concerns=["Too ambitious"],
            )
            pass_report = CriticReport(
                passed=True,
                issues=[],
                unsupported_claims=[],
                feasibility_concerns=[],
            )

            original_generation = agents_mod.generation_crew

            def tracking_generation(state):
                """Track what state generation_crew receives."""
                generation_calls.append(dict(state))
                return original_generation(state)

            def mock_critic(state):
                call_count["n"] += 1
                if call_count["n"] <= 1:
                    return {
                        "critic_report": fail_report,
                        "revision_count": state.get("revision_count", 0) + 1,
                    }
                return {
                    "critic_report": pass_report,
                    "revision_count": state.get("revision_count", 0),
                }

            with mock.patch("app.agents.critic_agent", mock_critic), \
                 mock.patch("app.agents.generation_crew", tracking_generation):
                import importlib
                importlib.reload(graph_mod)
                graph = graph_mod.build_graph()
                final_state = graph.invoke(_initial_state(max_revisions=2))

            # generation_crew should have been called at least twice
            assert len(generation_calls) >= 2, (
                f"generation_crew was only called {len(generation_calls)} time(s)"
            )

            # The second call should have a critic_report in state
            second_call_state = generation_calls[1]
            assert "critic_report" in second_call_state, (
                "generation_crew's second call should have critic_report in state"
            )
            assert second_call_state["critic_report"].passed is False, (
                "The critic_report should show failure"
            )


# ---------------------------------------------------------------------------
# Test 3: Bounded loop — critic never passes
# ---------------------------------------------------------------------------


class TestBoundedLoop:
    def test_terminates_at_max_revisions(self):
        """Critic never passes — graph must still terminate, not loop forever."""
        with mock.patch.dict(os.environ, _DRY_ENV, clear=False):
            graph_mod, agents_mod = _reload_and_build()

            call_count = {"n": 0}

            always_fail_report = CriticReport(
                passed=False,
                issues=["Persistent formatting issue"],
                unsupported_claims=["Unresolvable claim"],
                feasibility_concerns=[],
            )

            def never_pass_critic(state):
                call_count["n"] += 1
                return {
                    "critic_report": always_fail_report,
                    "revision_count": state.get("revision_count", 0) + 1,
                }

            with mock.patch("app.agents.critic_agent", never_pass_critic):
                import importlib
                importlib.reload(graph_mod)
                graph = graph_mod.build_graph()
                # max_revisions=2 → up to 3 total generation attempts
                final_state = graph.invoke(_initial_state(max_revisions=2))

            # Should terminate, not hang
            assert "interview_kit" in final_state, (
                "Graph should still reach END even when critic never passes"
            )
            # Revision count should be capped
            assert final_state.get("revision_count", 0) <= 3, (
                f"revision_count={final_state.get('revision_count')} exceeds expected bound"
            )
            # Critic should not have been called infinitely
            assert call_count["n"] <= 4, (
                f"Critic called {call_count['n']} times — possible infinite loop"
            )
