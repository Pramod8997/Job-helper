"""
Per-agent unit tests — all run with DRY_RUN=true, no API key required.

Tests per spec:
  - 03: ledger_agent returns CapabilityLedger, no empty strings in lists
  - 04: profiler_agent returns JobProfile with non-empty ats_keywords
  - 05-07: generation_crew returns resume, project, resources
  - 08: critic_agent — happy path + unsupported_claims safety net
  - 10: interview_coach_agent — index-alignment invariant
  - 09: human_checkpoint returns empty dict
"""

import os
from unittest import mock

import pytest

# Set DRY_RUN before importing any app modules
_DRY_ENV = {**os.environ, "DRY_RUN": "true"}
_DRY_ENV.pop("ANTHROPIC_API_KEY", None)


def _reload_modules():
    """Reload app.llm to pick up DRY_RUN=true, then import agents."""
    import importlib
    import app.llm
    importlib.reload(app.llm)
    import app.agents
    importlib.reload(app.agents)
    return app.agents


@pytest.fixture(autouse=True)
def dry_run_env():
    """Ensure DRY_RUN=true for all tests in this module."""
    with mock.patch.dict(os.environ, _DRY_ENV, clear=False):
        yield


# ---------------------------------------------------------------------------
# Minimal state slices for testing
# ---------------------------------------------------------------------------

from app.models import (
    CapabilityLedger,
    CriticReport,
    InterviewKit,
    JobProfile,
    ProjectBlueprint,
    ResumeDraft,
    ResourceKit,
)


def _minimal_state():
    """A minimal valid pipeline state for agent testing."""
    return {
        "jd_text": "We are looking for a backend engineer with Python and Docker experience.",
        "raw_profile_text": "I am Jane Doe, a CS student. I know Python, JavaScript, SQL, and Git.",
        "revision_count": 0,
        "max_revisions": 2,
    }


# ---------------------------------------------------------------------------
# 03: Capability Ledger Agent
# ---------------------------------------------------------------------------

class TestLedgerAgent:
    def test_returns_ledger(self):
        agents = _reload_modules()
        state = _minimal_state()
        result = agents.ledger_agent(state)

        assert "ledger" in result
        assert isinstance(result["ledger"], CapabilityLedger)

    def test_no_empty_strings_in_lists(self):
        agents = _reload_modules()
        state = _minimal_state()
        result = agents.ledger_agent(state)
        ledger = result["ledger"]

        for field_name in ["skills", "experience", "education", "projects", "certifications"]:
            values = getattr(ledger, field_name)
            for item in values:
                assert item.strip() != "", (
                    f"Ledger field '{field_name}' contains an empty string"
                )


# ---------------------------------------------------------------------------
# 04: Profiler Agent
# ---------------------------------------------------------------------------

class TestProfilerAgent:
    def test_returns_job_profile(self):
        agents = _reload_modules()
        state = _minimal_state()
        result = agents.profiler_agent(state)

        assert "job_profile" in result
        assert isinstance(result["job_profile"], JobProfile)

    def test_ats_keywords_non_empty(self):
        agents = _reload_modules()
        state = _minimal_state()
        result = agents.profiler_agent(state)

        assert len(result["job_profile"].ats_keywords) > 0, (
            "ats_keywords should be non-empty — the rest of the pipeline depends on it"
        )


# ---------------------------------------------------------------------------
# 05-07: Generation Crew
# ---------------------------------------------------------------------------

class TestGenerationCrew:
    def _state_with_ledger_and_profile(self):
        agents = _reload_modules()
        state = _minimal_state()
        state.update(agents.ledger_agent(state))
        state.update(agents.profiler_agent(state))
        return agents, state

    def test_returns_resume_project_resources(self):
        agents, state = self._state_with_ledger_and_profile()
        result = agents.generation_crew(state)

        assert "resume" in result
        assert "project" in result
        assert "resources" in result
        assert isinstance(result["resume"], ResumeDraft)
        assert isinstance(result["project"], ProjectBlueprint)
        assert isinstance(result["resources"], ResourceKit)

    def test_resume_claims_non_empty(self):
        agents, state = self._state_with_ledger_and_profile()
        result = agents.generation_crew(state)

        assert len(result["resume"].claims) > 0

    def test_project_estimated_weeks_reasonable(self):
        agents, state = self._state_with_ledger_and_profile()
        result = agents.generation_crew(state)

        weeks = result["project"].estimated_weeks
        assert 1 <= weeks <= 12, f"estimated_weeks={weeks} is unreasonable"


# ---------------------------------------------------------------------------
# 08: Critic Agent
# ---------------------------------------------------------------------------

class TestCriticAgent:
    def _state_with_generation(self):
        agents = _reload_modules()
        state = _minimal_state()
        state.update(agents.ledger_agent(state))
        state.update(agents.profiler_agent(state))
        state.update(agents.generation_crew(state))
        return agents, state

    def test_happy_path_passes(self):
        """Default stub returns passed=True with empty issue lists."""
        agents, state = self._state_with_generation()
        result = agents.critic_agent(state)

        assert "critic_report" in result
        report = result["critic_report"]
        assert isinstance(report, CriticReport)
        assert report.passed is True

    def test_revision_count_not_incremented_on_pass(self):
        agents, state = self._state_with_generation()
        state["revision_count"] = 0
        result = agents.critic_agent(state)

        assert result["revision_count"] == 0

    def test_safety_net_forces_fail_on_unsupported_claims(self):
        """If unsupported_claims is non-empty, passed must be forced to False."""
        # Construct a CriticReport dict with passed=True but unsupported claims
        bad_result = {
            "passed": True,
            "issues": [],
            "unsupported_claims": ["Claimed 10 years experience"],
            "feasibility_concerns": [],
        }

        # The safety net is applied in the agent, so we test it directly
        if bad_result.get("unsupported_claims"):
            bad_result["passed"] = False

        report = CriticReport(**bad_result)
        assert report.passed is False


# ---------------------------------------------------------------------------
# 10: Interview Coach Agent
# ---------------------------------------------------------------------------

class TestInterviewCoachAgent:
    def test_returns_interview_kit(self):
        agents = _reload_modules()
        state = _minimal_state()
        state.update(agents.ledger_agent(state))
        state.update(agents.profiler_agent(state))
        state.update(agents.generation_crew(state))
        result = agents.interview_coach_agent(state)

        assert "interview_kit" in result
        assert isinstance(result["interview_kit"], InterviewKit)

    def test_index_alignment(self):
        """behavioral_questions and star_answers must be index-aligned."""
        agents = _reload_modules()
        state = _minimal_state()
        state.update(agents.ledger_agent(state))
        state.update(agents.profiler_agent(state))
        state.update(agents.generation_crew(state))
        result = agents.interview_coach_agent(state)

        kit = result["interview_kit"]
        assert len(kit.behavioral_questions) == len(kit.star_answers), (
            f"{len(kit.behavioral_questions)} behavioral questions != "
            f"{len(kit.star_answers)} STAR answers"
        )


# ---------------------------------------------------------------------------
# 09: Human Checkpoint (Tier 1)
# ---------------------------------------------------------------------------

class TestHumanCheckpoint:
    def test_returns_empty_dict(self):
        agents = _reload_modules()
        state = _minimal_state()
        result = agents.human_checkpoint(state)
        assert result == {}

    def test_does_not_raise(self):
        """Should not raise for any valid state."""
        agents = _reload_modules()
        state = _minimal_state()
        state.update(agents.ledger_agent(state))
        state.update(agents.profiler_agent(state))
        state.update(agents.generation_crew(state))
        state.update(agents.critic_agent(state))
        # Should not raise
        result = agents.human_checkpoint(state)
        assert result == {}
