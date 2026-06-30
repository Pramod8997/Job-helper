"""
Tests for app/main.py — CLI entrypoint and render_kit function.

Per docs/13-cli.md:
  1. render_kit with fully-populated state produces Markdown with all sections.
  2. render_kit with failed critic_report includes QA notes section.
  3. Full CLI smoke test with DRY_RUN=true.
"""

import os
import subprocess
import sys
from unittest import mock

import pytest

from app.models import (
    CapabilityLedger,
    CriticReport,
    InterviewKit,
    JobProfile,
    ProjectBlueprint,
    ResumeDraft,
    ResourceKit,
)


def _full_state(critic_passed=True):
    """Build a fully-populated pipeline state for testing."""
    critic = CriticReport(
        passed=critic_passed,
        issues=[] if critic_passed else ["Resume uses table layout"],
        unsupported_claims=[] if critic_passed else ["Claimed 10 years experience"],
        feasibility_concerns=[] if critic_passed else ["Project scope too large"],
    )

    return {
        "jd_text": "Job description",
        "raw_profile_text": "Profile text",
        "ledger": CapabilityLedger(
            name="Jane Doe",
            summary="CS graduate with Python experience.",
            skills=["Python", "SQL"],
            experience=["Interned at TechCorp"],
            education=["B.S. CS, State University"],
            projects=["Expense tracker"],
        ),
        "job_profile": JobProfile(
            role_title="Backend Engineer",
            hard_skills=["Python"],
            soft_skills=["Communication"],
            ats_keywords=["REST API"],
            tech_stack=["Python", "Docker"],
            culture_signals=["fast-paced"],
        ),
        "resume": ResumeDraft(
            markdown="# Jane Doe\n\n## Experience\n\n- Interned at TechCorp",
            keywords_used=["REST API"],
            claims=["Interned at TechCorp"],
        ),
        "project": ProjectBlueprint(
            title="Docker Task Queue",
            description="Learn Docker by building a task queue.",
            architecture="FastAPI -> Redis -> Docker",
            tech_stack=["Docker", "FastAPI"],
            milestones=["Set up Docker", "Add Redis"],
            estimated_weeks=3,
        ),
        "resources": ResourceKit(
            cheat_sheet_markdown="## Docker\n\n```bash\ndocker build .\n```",
            links=["https://docs.docker.com/"],
        ),
        "critic_report": critic,
        "revision_count": 0 if critic_passed else 2,
        "max_revisions": 2,
        "human_approved": True,
        "interview_kit": InterviewKit(
            technical_questions=["Explain Docker networking."],
            behavioral_questions=["Tell me about a project."],
            star_answers=["Situation: Built expense tracker..."],
        ),
    }


class TestRenderKit:
    def test_fully_populated_state(self):
        from app.main import render_kit

        output = render_kit(_full_state(critic_passed=True))

        assert "# Resume" in output
        assert "Jane Doe" in output
        assert "# Project Recommendation" in output
        assert "Docker Task Queue" in output
        assert "# Resources" in output
        assert "https://docs.docker.com/" in output
        assert "# Interview Prep" in output
        assert "Explain Docker networking" in output
        # No QA notes when critic passed
        assert "QA Notes" not in output

    def test_failed_critic_includes_qa_notes(self):
        from app.main import render_kit

        output = render_kit(_full_state(critic_passed=False))

        assert "QA Notes" in output
        assert "Resume uses table layout" in output
        assert "Claimed 10 years experience" in output
        assert "Project scope too large" in output


class TestCLISmokeTest:
    def test_dry_run_produces_output(self, tmp_path):
        """Full CLI smoke test: DRY_RUN=true, no API key."""
        out_file = tmp_path / "test_kit.md"

        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        env["DRY_RUN"] = "true"

        result = subprocess.run(
            [
                sys.executable, "-m", "app.main",
                "--jd", "sample_data/jd.txt",
                "--profile", "sample_data/profile.txt",
                "--out", str(out_file),
            ],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0, f"CLI failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        assert out_file.exists(), "Output file should exist"
        content = out_file.read_text()
        assert len(content) > 0, "Output file should be non-empty"
        assert "# Resume" in content
