"""
HTTP API server for the Career Crew pipeline.

Tier 1: pass-through human checkpoint — runs the full graph in one call.

See: docs/12-api-server.md
"""

from __future__ import annotations

import os
import uuid
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

app = FastAPI(
    title="Career Crew API",
    description="Multi-agent interview prep kit generator",
    version="1.0.0",
)

# CORS — restricted to localhost for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class RunRequest(BaseModel):
    jd_text: str
    raw_profile_text: str
    max_revisions: int = 2


class RunResponse(BaseModel):
    run_id: str
    resume_markdown: str
    project: dict
    critic_report: dict
    interview_kit: dict
    note: str = "Review resume_markdown and project before treating this as final."


# ---------------------------------------------------------------------------
# In-memory state store (Tier 1 — not durable, single-process only)
# ---------------------------------------------------------------------------

# NOTE: This is acceptable for a single-process dev build, explicitly not
# durable. For production, use a real database or the LangGraph checkpointer.
_runs: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
def health():
    """Liveness check."""
    return {"status": "ok"}


@app.post("/run", response_model=RunResponse)
def run_pipeline(request: RunRequest):
    """Run the full Career Crew pipeline.

    Tier 1: runs end-to-end in one call (human checkpoint is a no-op).
    Returns both the draft and the final interview kit.
    """
    try:
        from app.graph import build_graph

        graph = build_graph()
        initial_state = {
            "jd_text": request.jd_text,
            "raw_profile_text": request.raw_profile_text,
            "revision_count": 0,
            "max_revisions": request.max_revisions,
        }

        final_state = graph.invoke(initial_state)

        run_id = str(uuid.uuid4())
        _runs[run_id] = final_state

        resume = final_state.get("resume")
        project = final_state.get("project")
        critic_report = final_state.get("critic_report")
        interview_kit = final_state.get("interview_kit")

        return RunResponse(
            run_id=run_id,
            resume_markdown=resume.markdown if resume else "",
            project=project.model_dump() if project else {},
            critic_report=critic_report.model_dump() if critic_report else {},
            interview_kit=interview_kit.model_dump() if interview_kit else {},
        )

    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
