"""
Agent functions for the Career Crew pipeline.

Each agent is a function that takes a PipelineState (or subset) and returns
a partial state update dict. Every agent supports DRY_RUN mode via the
call_structured stub mechanism.

Agents implemented (in build order per docs/00-overview.md):
  - ledger_agent        (03-capability-ledger-agent.md)
  - profiler_agent      (04-profiler-agent.md)
  - generation_crew     (05, 06, 07 — resume architect, project strategist, resource curator)
  - critic_agent        (08-critic-agent.md)
  - interview_coach_agent (10-interview-coach-agent.md)

See individual spec files in docs/ for detailed requirements.
"""

from __future__ import annotations

from app.llm import MODEL_FAST, MODEL_SMART, MODEL_JUDGE, call_structured
from app.models import (
    CapabilityLedger,
    CriticReport,
    InterviewKit,
    JobProfile,
    ProjectBlueprint,
    ResumeDraft,
    ResourceKit,
)


# ═══════════════════════════════════════════════════════════════════════════
# DRY_RUN stubs — deterministic, clearly-synthetic data for graph testing
# ═══════════════════════════════════════════════════════════════════════════

_LEDGER_STUB = {
    "name": "Jane Doe",
    "summary": "CS student with Python and web development experience.",
    "skills": ["Python", "JavaScript", "SQL", "Git"],
    "experience": [
        "Developed a REST API for a student club management app using Flask",
        "Interned at TechCorp as a junior developer for 3 months",
    ],
    "education": ["B.S. Computer Science, State University (2024)"],
    "projects": ["Built a personal expense tracker with Flask and SQLite"],
    "certifications": [],
}

_JOB_PROFILE_STUB = {
    "role_title": "Backend Software Engineer",
    "hard_skills": ["Python", "PostgreSQL", "Docker", "REST APIs", "Redis"],
    "soft_skills": ["Communication", "Problem-solving", "Teamwork"],
    "ats_keywords": ["CI/CD", "microservices", "REST API", "Docker", "PostgreSQL"],
    "tech_stack": ["Python", "FastAPI", "PostgreSQL", "Docker", "Redis"],
    "culture_signals": ["fast-paced", "ownership mindset", "collaborative"],
}

_RESUME_STUB = {
    "markdown": (
        "# Jane Doe\n\n"
        "## Summary\n\n"
        "CS graduate with hands-on Python and web development experience.\n\n"
        "## Experience\n\n"
        "- Developed a REST API for a student club management app using Flask\n"
        "- Interned at TechCorp as a junior developer for 3 months\n\n"
        "## Education\n\n"
        "- B.S. Computer Science, State University (2024)\n\n"
        "## Projects\n\n"
        "- Built a personal expense tracker with Flask and SQLite\n\n"
        "## Skills\n\n"
        "Python, JavaScript, SQL, Git\n"
    ),
    "keywords_used": ["REST API"],
    "claims": [
        "Developed a REST API for a student club management app using Flask",
        "Interned at TechCorp as a junior developer for 3 months",
        "Has a B.S. Computer Science from State University",
        "Built a personal expense tracker with Flask and SQLite",
    ],
}

_PROJECT_STUB = {
    "title": "Dockerised Task Queue API",
    "description": (
        "Build a FastAPI-based task queue service with Docker to learn "
        "containerisation and close the Docker gap in your skill set."
    ),
    "architecture": "FastAPI server -> Redis message queue -> Docker Compose orchestration",
    "tech_stack": ["Docker", "FastAPI", "Redis", "Python"],
    "milestones": [
        "Set up a basic FastAPI app with one endpoint",
        "Add Redis as a task queue backend",
        "Write a Dockerfile and docker-compose.yml",
        "Add a worker service that processes queued tasks",
        "Write integration tests for the queue flow",
    ],
    "estimated_weeks": 3,
}

_RESOURCE_STUB = {
    "cheat_sheet_markdown": (
        "## Docker Basics\n\n"
        "```bash\n"
        "docker build -t myapp .\n"
        "docker run -p 8000:8000 myapp\n"
        "docker-compose up -d\n"
        "```\n\n"
        "## FastAPI Quick Reference\n\n"
        "```python\n"
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n\n"
        "@app.get('/health')\n"
        "def health(): return {'status': 'ok'}\n"
        "```\n"
    ),
    "links": [
        "https://docs.docker.com/get-started/",
        "https://fastapi.tiangolo.com/tutorial/",
        "https://redis.io/docs/getting-started/",
    ],
}

_CRITIC_PASS_STUB = {
    "passed": True,
    "issues": [],
    "unsupported_claims": [],
    "feasibility_concerns": [],
}

_CRITIC_FAIL_STUB = {
    "passed": False,
    "issues": ["Resume uses a table layout which may break ATS parsing"],
    "unsupported_claims": ["Interned at TechCorp as a senior developer"],
    "feasibility_concerns": [],
}

_INTERVIEW_KIT_STUB = {
    "technical_questions": [
        "Explain how Docker networking works between containers.",
        "What is the difference between a SQL JOIN and a subquery?",
    ],
    "behavioral_questions": [
        "Tell me about a time you had to learn a new technology quickly.",
    ],
    "star_answers": [
        "Situation: Needed to build a REST API for a student club app but had "
        "not used Flask before. Task: Deliver a working API in 2 weeks. "
        "Action: Followed the Flask tutorial, built endpoints incrementally, "
        "tested with Postman. Result: Delivered on time, API served 50+ club "
        "members for event sign-ups.",
    ],
}


# ═══════════════════════════════════════════════════════════════════════════
# Agent: Capability Ledger (03)
# ═══════════════════════════════════════════════════════════════════════════

_LEDGER_SYSTEM_PROMPT = """\
You are a strict fact-extraction agent. Your job is to convert raw, freeform \
profile text into a structured JSON profile.

CRITICAL RULES:
- Extract ONLY what is explicitly stated in the input text.
- NEVER invent, infer, or embellish anything not explicitly present.
- When something is ambiguous (e.g. "I know some Docker"), prefer OMISSION \
over guessing. It is better to under-claim than over-claim.
- A skill mentioned only in passing ("read about Kubernetes") should NOT be \
listed under skills as if it were hands-on experience.
- This output is the single source of truth that all later resume and \
interview content must be traceable to.

Return a JSON object with these fields:
- name (string)
- summary (string, 1-2 factual sentences, not marketing copy)
- skills (list of strings)
- experience (list of strings, one bullet per item, factual)
- education (list of strings)
- projects (list of strings)
- certifications (list of strings)
"""


def ledger_agent(state: dict) -> dict:
    """Extract a CapabilityLedger from raw profile text."""
    raw_profile = state["raw_profile_text"]

    result = call_structured(
        system_prompt=_LEDGER_SYSTEM_PROMPT,
        user_prompt=f"Extract a structured profile from this text:\n\n{raw_profile}",
        model=MODEL_FAST,
        stub=_LEDGER_STUB,
    )

    ledger = CapabilityLedger(**result)
    return {"ledger": ledger}


# ═══════════════════════════════════════════════════════════════════════════
# Agent: Market & ATS Profiler (04)
# ═══════════════════════════════════════════════════════════════════════════

_PROFILER_SYSTEM_PROMPT = """\
You are a job-description analysis agent. Extract structured keyword data \
from a raw job description.

RULES:
- ats_keywords must be EXACT phrases an ATS scanner would match on — not \
paraphrases or synonyms. If the JD says "CI/CD pipelines", use "CI/CD", \
not "automated deployment processes".
- culture_signals are softer, inferred from tone/phrasing (e.g. "move fast", \
"ownership mindset").
- Ignore irrelevant boilerplate (equal-opportunity statements, generic \
company mission text, benefits lists).
- Prioritise clearly emphasised requirements (repeated, under "must have") \
over "nice to have" items. Order must-haves first in each list.
- If the JD is vague, return short lists — don't fabricate specificity.

Return a JSON object with these fields:
- role_title (string)
- hard_skills (list of strings)
- soft_skills (list of strings)
- ats_keywords (list of strings)
- tech_stack (list of strings)
- culture_signals (list of strings)
"""


def profiler_agent(state: dict) -> dict:
    """Extract a JobProfile from the job description text."""
    jd_text = state["jd_text"]

    result = call_structured(
        system_prompt=_PROFILER_SYSTEM_PROMPT,
        user_prompt=f"Analyse this job description:\n\n{jd_text}",
        model=MODEL_FAST,
        stub=_JOB_PROFILE_STUB,
    )

    job_profile = JobProfile(**result)
    return {"job_profile": job_profile}


# ═══════════════════════════════════════════════════════════════════════════
# Generation sub-agents (05, 06, 07) — called together by generation_crew
# ═══════════════════════════════════════════════════════════════════════════

# --- Resume Architect (05) ---

_RESUME_SYSTEM_PROMPT = """\
You are a resume-writing agent. Produce an ATS-optimized resume in \
single-column Markdown format.

CRITICAL CONSTRAINT: You may ONLY use facts present in the Capability \
Ledger provided below. NEVER invent skills, metrics, or experience not \
in the Ledger. This is the most important rule in the entire system.

RULES:
- Single-column Markdown only. NO tables, multi-column layout markers, \
images, or special characters that ATS parsers mishandle.
- Weave in ATS keywords naturally, ONLY where truthfully applicable. \
Do not force a keyword next to a skill the Ledger doesn't support.
- Populate the "claims" field with every factual statement in the resume, \
one per item, specific enough for verification (e.g. "Led a team of 4 \
engineers" not "Strong leader").
- If the Ledger is sparse, write a shorter resume. Do NOT pad with generic \
statements.
- If no Ledger items match ATS keywords, keywords_used can be empty.

Return a JSON object with these fields:
- markdown (string — the full resume in Markdown)
- keywords_used (list of strings — ATS keywords actually used)
- claims (list of strings — every factual statement, one per item)
"""


def _resume_architect(
    ledger: CapabilityLedger, job_profile: JobProfile, feedback: str | None
) -> ResumeDraft:
    """Generate an ATS-optimized resume draft."""
    user_prompt = (
        f"Capability Ledger:\n{ledger.model_dump_json(indent=2)}\n\n"
        f"Job Profile (ATS keywords to weave in):\n{job_profile.model_dump_json(indent=2)}"
    )
    if feedback:
        user_prompt += f"\n\nPrior critic feedback to address:\n{feedback}"

    result = call_structured(
        system_prompt=_RESUME_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=MODEL_SMART,
        stub=_RESUME_STUB,
    )

    return ResumeDraft(**result)


# --- Project Strategist (06) ---

_PROJECT_SYSTEM_PROMPT = """\
You are a project recommendation agent. Design exactly ONE project that \
closes the gap between the candidate's current skills and the target role.

RULES:
- Identify what's in the job's hard_skills/tech_stack that is ABSENT from \
the candidate's skills, and design around that gap.
- Must be realistically buildable by THIS person given their current skill \
level. A student with no Docker experience should not be assigned a \
multi-service Kubernetes orchestration project.
- architecture should name actual components, not vague phrases.
- milestones should be ordered, concrete, buildable steps.
- estimated_weeks must be realistic for part-time work alongside other \
commitments. Bias toward smaller, finishable scope.
- If skills already match the JD, design a depth/scale project instead.
- If the JD has many gaps, pick the 1-2 highest-leverage ones.

Return a JSON object with these fields:
- title (string)
- description (string)
- architecture (string — short architecture description)
- tech_stack (list of strings)
- milestones (list of strings — ordered buildable steps)
- estimated_weeks (integer)
"""


def _project_strategist(
    ledger: CapabilityLedger, job_profile: JobProfile, feedback: str | None
) -> ProjectBlueprint:
    """Design a gap-closing project recommendation."""
    user_prompt = (
        f"Capability Ledger:\n{ledger.model_dump_json(indent=2)}\n\n"
        f"Job Profile:\n{job_profile.model_dump_json(indent=2)}"
    )
    if feedback:
        user_prompt += f"\n\nPrior critic feasibility feedback to address:\n{feedback}"

    result = call_structured(
        system_prompt=_PROJECT_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=MODEL_SMART,
        stub=_PROJECT_STUB,
    )

    return ProjectBlueprint(**result)


# --- Resource Curator (07) ---

_RESOURCE_SYSTEM_PROMPT = """\
You are a resource curation agent. Produce a concise Markdown cheat sheet \
and a short list of high-value links for the target role's tech stack.

RULES:
- Cheat sheet: CLI commands, config snippets, key concepts — skimmable, \
not a tutorial.
- Links should be official documentation where possible (framework docs, \
language docs) over blog posts.
- Don't pad the list — 3-6 genuinely high-value links beats 15 mediocre ones.
- Links MUST come from real search results, not model recall. In DRY_RUN \
mode, stub links are acceptable for testing.

Return a JSON object with these fields:
- cheat_sheet_markdown (string)
- links (list of strings — URLs)
"""


def _resource_curator(job_profile: JobProfile) -> ResourceKit:
    """Produce a resource cheat sheet and curated links.

    Note: In production, this should use real web search (e.g. Anthropic's
    server-side web_search tool). For now, in DRY_RUN mode the stub is used.
    For real calls, the LLM is prompted but links should ideally come from
    search — this is a documented known limitation for v1.
    """
    user_prompt = (
        f"Create a learning cheat sheet and resource links for these technologies:\n"
        f"Tech stack: {', '.join(job_profile.tech_stack)}\n"
        f"Key skills: {', '.join(job_profile.hard_skills)}"
    )

    result = call_structured(
        system_prompt=_RESOURCE_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=MODEL_FAST,
        stub=_RESOURCE_STUB,
    )

    return ResourceKit(**result)


# ═══════════════════════════════════════════════════════════════════════════
# Generation Crew — combines resume + project + resources (05, 06, 07)
# ═══════════════════════════════════════════════════════════════════════════


def generation_crew(state: dict) -> dict:
    """Run all three generation sub-agents.

    On re-entry after a failed critic pass, reads state["critic_report"]
    and builds a feedback string for the Resume Architect and Project
    Strategist.
    """
    ledger: CapabilityLedger = state["ledger"]
    job_profile: JobProfile = state["job_profile"]

    # Build feedback string from prior critic report (if any)
    feedback: str | None = None
    critic_report = state.get("critic_report")
    if critic_report and not critic_report.passed:
        feedback_parts = []
        if critic_report.issues:
            feedback_parts.append("Issues: " + "; ".join(critic_report.issues))
        if critic_report.unsupported_claims:
            feedback_parts.append(
                "Unsupported claims: " + "; ".join(critic_report.unsupported_claims)
            )
        if critic_report.feasibility_concerns:
            feedback_parts.append(
                "Feasibility concerns: " + "; ".join(critic_report.feasibility_concerns)
            )
        feedback = "\n".join(feedback_parts) if feedback_parts else None

    # Call all three sub-agents (sequential for simplicity; they could be
    # parallelised since they're independent)
    resume = _resume_architect(ledger, job_profile, feedback)
    project = _project_strategist(ledger, job_profile, feedback)
    resources = _resource_curator(job_profile)

    return {
        "resume": resume,
        "project": project,
        "resources": resources,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Agent: Critic (08)
# ═══════════════════════════════════════════════════════════════════════════

_CRITIC_SYSTEM_PROMPT = """\
You are a QA and feasibility critic. Your job is to DISAGREE with the \
generation crew when warranted. Do not rubber-stamp — a critic that \
always passes defeats the purpose of this architecture.

Perform THREE distinct checks:

1. CLAIM VERIFICATION: For every item in resume.claims, check whether it \
is traceable to the CapabilityLedger. "Traceable" means the Ledger \
actually supports the claim, not that the claim is merely plausible. \
List anything not traceable in unsupported_claims.

2. ATS-PARSEABILITY CHECK: Scan the resume markdown for: tables, \
multi-column hints, embedded images/graphics, unusual characters. \
List any found in issues.

3. FEASIBILITY CHECK: Evaluate the ProjectBlueprint against the Ledger's \
skill level and estimated_weeks. Flag anything unrealistic in \
feasibility_concerns.

Set passed=false if there are ANY unsupported claims or serious \
feasibility concerns. Minor wording issues alone don't need to fail.

Return a JSON object with these fields:
- passed (boolean)
- issues (list of strings)
- unsupported_claims (list of strings)
- feasibility_concerns (list of strings)
"""


def critic_agent(state: dict) -> dict:
    """Run the QA & feasibility critic.

    Returns a CriticReport and increments revision_count on failure.
    The revision_count increment happens inside this agent (not in the
    routing function) — this is deliberate per 08-critic-agent.md.
    """
    ledger: CapabilityLedger = state["ledger"]
    resume: ResumeDraft = state["resume"]
    project: ProjectBlueprint = state["project"]

    user_prompt = (
        f"Capability Ledger (source of truth):\n{ledger.model_dump_json(indent=2)}\n\n"
        f"Resume Draft:\n{resume.model_dump_json(indent=2)}\n\n"
        f"Project Blueprint:\n{project.model_dump_json(indent=2)}"
    )

    result = call_structured(
        system_prompt=_CRITIC_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=MODEL_JUDGE,
        stub=_CRITIC_PASS_STUB,
    )

    # ── Safety net: don't trust the model's `passed` field blindly ──
    # If unsupported_claims is non-empty, force passed=False regardless
    # of what the model set. This guards against the real failure mode where
    # LLMs set passed=true while listing unsupported claims.
    if result.get("unsupported_claims"):
        result["passed"] = False

    report = CriticReport(**result)

    return {
        "critic_report": report,
        "revision_count": state.get("revision_count", 0) + (0 if report.passed else 1),
    }


# ═══════════════════════════════════════════════════════════════════════════
# Agent: Interview Coach (10)
# ═══════════════════════════════════════════════════════════════════════════

_INTERVIEW_SYSTEM_PROMPT = """\
You are an interview preparation coach. Build an interview prep kit from \
the candidate's profile, the target job, and their project.

RULES:
- Generate role-specific technical questions based on the job's hard skills \
and tech stack.
- Generate behavioral questions appropriate to the role and seniority.
- Generate STAR-framed answer outlines for each behavioral question, \
index-aligned (the Nth outline answers the Nth behavioral question).
- STAR outlines must be grounded ONLY in the CapabilityLedger and the \
ProjectBlueprint. NEVER invent achievements.
- If the Ledger doesn't support a strong answer, say so honestly and \
point to the closest real example.
- For candidates with limited experience, lean on academic/project \
experience and the new ProjectBlueprint.

Return a JSON object with these fields:
- technical_questions (list of strings)
- behavioral_questions (list of strings)
- star_answers (list of strings — STAR-framed, index-aligned with behavioral_questions)
"""


def interview_coach_agent(state: dict) -> dict:
    """Generate the interview prep kit."""
    ledger: CapabilityLedger = state["ledger"]
    job_profile: JobProfile = state["job_profile"]
    project: ProjectBlueprint = state["project"]

    user_prompt = (
        f"Capability Ledger:\n{ledger.model_dump_json(indent=2)}\n\n"
        f"Job Profile:\n{job_profile.model_dump_json(indent=2)}\n\n"
        f"Project Blueprint (candidate should be able to discuss this):\n"
        f"{project.model_dump_json(indent=2)}"
    )

    result = call_structured(
        system_prompt=_INTERVIEW_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=MODEL_JUDGE,
        stub=_INTERVIEW_KIT_STUB,
    )

    kit = InterviewKit(**result)

    # Enforce index-alignment invariant — misaligned lists would silently
    # produce a STAR answer that doesn't match its question.
    assert len(kit.behavioral_questions) == len(kit.star_answers), (
        f"InterviewKit invariant violated: {len(kit.behavioral_questions)} "
        f"behavioral questions but {len(kit.star_answers)} STAR answers. "
        f"These must be index-aligned."
    )

    return {"interview_kit": kit}


# ═══════════════════════════════════════════════════════════════════════════
# Human Checkpoint — Tier 1: pass-through (09)
# ═══════════════════════════════════════════════════════════════════════════


def human_checkpoint(state: dict) -> dict:
    """Tier 1 human checkpoint: a no-op pass-through.

    The actual "human review" happens in the CLI (printing draft and
    prompting y/N) or is left to the API caller. This proves the graph
    shape is correct without requiring real pause/resume infrastructure.
    """
    return {}
