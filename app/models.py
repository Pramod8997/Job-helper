"""
Data contracts for the Career Crew pipeline.

Every agent's input and output is a typed Pydantic model, not freeform text.
This is what makes the Critic agent possible — it can programmatically
iterate resume.claims and check each one against the Capability Ledger.

See: docs/01-data-models.md
"""

from __future__ import annotations

from typing import List, Optional
from typing_extensions import TypedDict

from pydantic import BaseModel, field_validator


# ---------------------------------------------------------------------------
# Pydantic models — validated data flowing between agents
# ---------------------------------------------------------------------------


class CapabilityLedger(BaseModel):
    """Single source of truth about the candidate.

    Every later claim in the resume or interview kit must be traceable to
    a field in this object.
    """

    name: str
    summary: str  # 1-2 sentence factual summary, not marketing copy
    skills: List[str] = []
    experience: List[str] = []  # one bullet per item, factual
    education: List[str] = []
    projects: List[str] = []
    certifications: List[str] = []

    @field_validator("skills", "experience", "education", "projects", "certifications", mode="before")
    @classmethod
    def strip_and_filter_blanks(cls, v: List[str]) -> List[str]:
        """Strip whitespace and filter out empty strings.

        The LLM extraction agent occasionally returns [""] for an absent
        field instead of []. This validator normalises that to [].
        """
        if not isinstance(v, list):
            return v
        return [item.strip() for item in v if isinstance(item, str) and item.strip()]


class JobProfile(BaseModel):
    """Output of the Market & ATS Profiler."""

    role_title: str
    hard_skills: List[str]
    soft_skills: List[str]
    ats_keywords: List[str]  # exact phrases an ATS scanner would match on
    tech_stack: List[str]
    culture_signals: List[str]  # e.g. "fast-paced", "collaborative"


class ResumeDraft(BaseModel):
    """ATS-optimized resume draft produced by the Resume Architect."""

    markdown: str  # single-column markdown, no tables/multi-column
    keywords_used: List[str]  # subset of JobProfile.ats_keywords
    claims: List[str]  # every factual statement, one per item


class ProjectBlueprint(BaseModel):
    """Realistically buildable project recommendation."""

    title: str
    description: str
    architecture: str  # short architecture description
    tech_stack: List[str]
    milestones: List[str]  # ordered, concrete, buildable steps
    estimated_weeks: int = 4  # realistic for part-time work


class ResourceKit(BaseModel):
    """Learning cheat sheet and curated links."""

    cheat_sheet_markdown: str  # CLI commands, config snippets, key concepts
    links: List[str]  # must come from real search, not model recall


class CriticReport(BaseModel):
    """QA & feasibility report from the Critic agent."""

    passed: bool
    issues: List[str]  # general problems (ATS-parseability, formatting)
    unsupported_claims: List[str]  # claims not traceable to CapabilityLedger
    feasibility_concerns: List[str]  # reasons ProjectBlueprint may fail


class InterviewKit(BaseModel):
    """Interview prep kit — the final system output."""

    technical_questions: List[str]
    behavioral_questions: List[str]
    star_answers: List[str]  # STAR-framed outlines, index-aligned with behavioral_questions


# ---------------------------------------------------------------------------
# LangGraph state shape — TypedDict with total=False
# ---------------------------------------------------------------------------


class PipelineState(TypedDict, total=False):
    """LangGraph state shape.

    Uses TypedDict with total=False because LangGraph nodes return partial
    state updates — each node only returns the keys it sets, and LangGraph
    merges them into the running state.

    Why TypedDict and not a Pydantic model for state specifically: LangGraph's
    default state-merge behavior expects dict-like objects with key-by-key
    updates. Wrapping each field's *value* in Pydantic gives you validation
    on the data; using TypedDict for the *container* keeps you compatible
    with how StateGraph reduces node outputs into state.
    """

    jd_text: str
    raw_profile_text: str
    ledger: CapabilityLedger
    job_profile: JobProfile
    resume: ResumeDraft
    project: ProjectBlueprint
    resources: ResourceKit
    critic_report: CriticReport
    revision_count: int
    max_revisions: int
    human_approved: bool
    human_feedback: Optional[str]
    interview_kit: InterviewKit
