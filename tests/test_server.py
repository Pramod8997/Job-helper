"""
Tests for app/server.py — FastAPI HTTP API.

Per docs/12-api-server.md:
  1. POST /run with valid input returns 200 with correct shape.
  2. POST /run with missing fields returns 422.
  3. GET /health returns 200.

All run with DRY_RUN=true via TestClient.
"""

import os
from unittest import mock

import pytest

_DRY_ENV = {**os.environ, "DRY_RUN": "true"}
_DRY_ENV.pop("ANTHROPIC_API_KEY", None)


@pytest.fixture(autouse=True)
def dry_run_env():
    with mock.patch.dict(os.environ, _DRY_ENV, clear=False):
        # Reload modules to pick up DRY_RUN
        import importlib
        import app.llm
        importlib.reload(app.llm)
        import app.agents
        importlib.reload(app.agents)
        import app.graph
        importlib.reload(app.graph)
        import app.server
        importlib.reload(app.server)
        yield


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.server import app
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestRunEndpoint:
    def test_valid_run_returns_200(self, client):
        response = client.post("/run", json={
            "jd_text": "We need a Python backend engineer.",
            "raw_profile_text": "I am Jane, I know Python and SQL.",
            "max_revisions": 2,
        })
        assert response.status_code == 200
        data = response.json()
        assert "run_id" in data
        assert "resume_markdown" in data
        assert "project" in data
        assert "critic_report" in data
        assert "interview_kit" in data
        assert "note" in data

    def test_missing_fields_returns_422(self, client):
        """FastAPI should reject requests missing required fields."""
        response = client.post("/run", json={
            "jd_text": "Some job description",
            # missing raw_profile_text
        })
        assert response.status_code == 422
