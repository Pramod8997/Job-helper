"""
Acceptance tests for app/models.py — data contracts.

Per docs/01-data-models.md:
  Construct one instance of each model with valid data and assert
  .model_dump() round-trips through .model_dump_json() and back via
  Model(**json.loads(...)) without error.

Also tests the CapabilityLedger blank-string filtering validator.
"""

import json

from app.models import (
    CapabilityLedger,
    CriticReport,
    InterviewKit,
    JobProfile,
    PipelineState,
    ProjectBlueprint,
    ResumeDraft,
    ResourceKit,
)


# ---------------------------------------------------------------------------
# Fixtures — one valid instance per model
# ---------------------------------------------------------------------------

def _make_ledger() -> CapabilityLedger:
    return CapabilityLedger(
        name="Alice Engineer",
        summary="Backend developer with 3 years of Python experience.",
        skills=["Python", "SQL", "Git"],
        experience=["Built REST APIs at Acme Corp for 2 years"],
        education=["B.S. Computer Science, State University"],
        projects=["Personal expense-tracker web app"],
        certifications=["AWS Cloud Practitioner"],
    )


def _make_job_profile() -> JobProfile:
    return JobProfile(
        role_title="Senior Backend Engineer",
        hard_skills=["Python", "PostgreSQL", "Docker"],
        soft_skills=["Communication", "Mentoring"],
        ats_keywords=["CI/CD", "microservices", "REST API"],
        tech_stack=["Python", "FastAPI", "PostgreSQL", "Docker"],
        culture_signals=["fast-paced", "ownership mindset"],
    )


def _make_resume_draft() -> ResumeDraft:
    return ResumeDraft(
        markdown="# Alice Engineer\n\n## Experience\n\n- Built REST APIs at Acme Corp",
        keywords_used=["REST API", "CI/CD"],
        claims=["Built REST APIs at Acme Corp for 2 years"],
    )


def _make_project_blueprint() -> ProjectBlueprint:
    return ProjectBlueprint(
        title="Containerised Task Queue",
        description="A Docker-based task queue to learn containerisation.",
        architecture="FastAPI server -> Redis queue -> Worker container",
        tech_stack=["Docker", "FastAPI", "Redis"],
        milestones=[
            "Set up Docker Compose",
            "Create FastAPI endpoint",
            "Add Redis-backed queue",
            "Add worker container",
        ],
        estimated_weeks=3,
    )


def _make_resource_kit() -> ResourceKit:
    return ResourceKit(
        cheat_sheet_markdown="## Docker basics\n\n```bash\ndocker build -t app .\n```",
        links=[
            "https://docs.docker.com/get-started/",
            "https://fastapi.tiangolo.com/tutorial/",
        ],
    )


def _make_critic_report() -> CriticReport:
    return CriticReport(
        passed=True,
        issues=[],
        unsupported_claims=[],
        feasibility_concerns=[],
    )


def _make_interview_kit() -> InterviewKit:
    return InterviewKit(
        technical_questions=[
            "Explain how Docker networking works.",
            "What is a REST API?",
        ],
        behavioral_questions=["Tell me about a time you led a project."],
        star_answers=[
            "Situation: Led a personal project to build an expense tracker. "
            "Task: Design and ship MVP. Action: Used Python/FastAPI, deployed "
            "with Docker. Result: Completed in 3 weeks, learned Docker basics."
        ],
    )


# ---------------------------------------------------------------------------
# Round-trip tests: model_dump → model_dump_json → json.loads → Model(...)
# ---------------------------------------------------------------------------

MODELS_AND_FACTORIES = [
    (CapabilityLedger, _make_ledger),
    (JobProfile, _make_job_profile),
    (ResumeDraft, _make_resume_draft),
    (ProjectBlueprint, _make_project_blueprint),
    (ResourceKit, _make_resource_kit),
    (CriticReport, _make_critic_report),
    (InterviewKit, _make_interview_kit),
]


class TestModelRoundTrip:
    """Each Pydantic model must survive a JSON round-trip."""

    def _round_trip(self, model_cls, factory):
        instance = factory()
        dumped = instance.model_dump()
        json_str = instance.model_dump_json()
        reloaded = model_cls(**json.loads(json_str))

        # The reloaded instance should be identical to the original
        assert reloaded.model_dump() == dumped, (
            f"{model_cls.__name__} round-trip failed: "
            f"expected {dumped!r}, got {reloaded.model_dump()!r}"
        )

    def test_capability_ledger_round_trip(self):
        self._round_trip(CapabilityLedger, _make_ledger)

    def test_job_profile_round_trip(self):
        self._round_trip(JobProfile, _make_job_profile)

    def test_resume_draft_round_trip(self):
        self._round_trip(ResumeDraft, _make_resume_draft)

    def test_project_blueprint_round_trip(self):
        self._round_trip(ProjectBlueprint, _make_project_blueprint)

    def test_resource_kit_round_trip(self):
        self._round_trip(ResourceKit, _make_resource_kit)

    def test_critic_report_round_trip(self):
        self._round_trip(CriticReport, _make_critic_report)

    def test_interview_kit_round_trip(self):
        self._round_trip(InterviewKit, _make_interview_kit)


# ---------------------------------------------------------------------------
# CapabilityLedger blank-string filter tests
# ---------------------------------------------------------------------------


class TestCapabilityLedgerValidator:
    """The LLM sometimes returns [""] for an absent field. We must filter."""

    def test_empty_strings_filtered(self):
        ledger = CapabilityLedger(
            name="Test",
            summary="Test summary",
            skills=["Python", "", "  ", "SQL"],
            experience=[""],
            education=[],
            projects=["  ", "Project A"],
        )
        assert ledger.skills == ["Python", "SQL"]
        assert ledger.experience == []
        assert ledger.education == []
        assert ledger.projects == ["Project A"]
        assert ledger.certifications == []

    def test_whitespace_stripped(self):
        ledger = CapabilityLedger(
            name="Test",
            summary="Summary",
            skills=["  Python  ", "SQL  "],
        )
        assert ledger.skills == ["Python", "SQL"]


# ---------------------------------------------------------------------------
# PipelineState TypedDict shape test
# ---------------------------------------------------------------------------


class TestPipelineState:
    """PipelineState is a TypedDict with total=False — all keys optional."""

    def test_empty_state_is_valid(self):
        state: PipelineState = {}
        assert isinstance(state, dict)

    def test_partial_state_is_valid(self):
        state: PipelineState = {
            "jd_text": "We are looking for a senior engineer...",
            "revision_count": 0,
            "max_revisions": 2,
        }
        assert state["jd_text"].startswith("We are")
        assert state["revision_count"] == 0

    def test_full_state_is_valid(self):
        state: PipelineState = {
            "jd_text": "Job description text",
            "raw_profile_text": "Profile text",
            "ledger": _make_ledger(),
            "job_profile": _make_job_profile(),
            "resume": _make_resume_draft(),
            "project": _make_project_blueprint(),
            "resources": _make_resource_kit(),
            "critic_report": _make_critic_report(),
            "revision_count": 1,
            "max_revisions": 2,
            "human_approved": True,
            "human_feedback": None,
            "interview_kit": _make_interview_kit(),
        }
        assert state["human_approved"] is True
        assert state["human_feedback"] is None
