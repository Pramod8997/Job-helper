"""
Tests for app/llm.py — LLM client wrapper.

Per docs/02-llm-client.md:
  1. DRY_RUN=true + stub provided → returns stub, no network call.
  2. DRY_RUN=true + stub=None → raises RuntimeError.
  3. DRY_RUN=false + no ANTHROPIC_API_KEY → raises clear error.
"""

import os
from unittest import mock

import pytest


class TestCallStructuredDryRun:
    """Tests with DRY_RUN=true — no API key needed."""

    def test_returns_stub_when_provided(self):
        """DRY_RUN + stub → returns stub exactly, no network call."""
        # Ensure no API key is set (proves no real client is constructed)
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        env["DRY_RUN"] = "true"

        with mock.patch.dict(os.environ, env, clear=True):
            # Re-import to pick up the new DRY_RUN value
            import importlib
            import app.llm as llm_mod
            importlib.reload(llm_mod)

            stub = {"name": "Test", "skills": ["Python"]}
            result = llm_mod.call_structured(
                system_prompt="You are a test.",
                user_prompt="Extract profile.",
                model=llm_mod.MODEL_FAST,
                stub=stub,
            )
            assert result is stub  # exact same object, not a copy

    def test_raises_when_stub_is_none(self):
        """DRY_RUN + stub=None → RuntimeError (missing stub is a bug)."""
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        env["DRY_RUN"] = "true"

        with mock.patch.dict(os.environ, env, clear=True):
            import importlib
            import app.llm as llm_mod
            importlib.reload(llm_mod)

            with pytest.raises(RuntimeError, match="no stub was provided"):
                llm_mod.call_structured(
                    system_prompt="You are a test.",
                    user_prompt="Extract profile.",
                    model=llm_mod.MODEL_FAST,
                    stub=None,
                )


class TestCallStructuredNoKey:
    """Tests with DRY_RUN=false and no API key."""

    def test_raises_clear_error_without_api_key(self):
        """Missing ANTHROPIC_API_KEY with DRY_RUN=false → actionable error."""
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        env["DRY_RUN"] = "false"

        with mock.patch.dict(os.environ, env, clear=True):
            import importlib
            import app.llm as llm_mod
            importlib.reload(llm_mod)
            # Reset the cached client so it tries to construct a new one
            llm_mod._client = None

            with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
                llm_mod.call_structured(
                    system_prompt="You are a test.",
                    user_prompt="Extract profile.",
                    model=llm_mod.MODEL_FAST,
                    stub={"dummy": True},
                )


class TestStripFences:
    """Test the JSON fence-stripping helper."""

    def test_strips_json_fences(self):
        import app.llm as llm_mod
        raw = '```json\n{"key": "value"}\n```'
        assert llm_mod._strip_fences(raw) == '{"key": "value"}'

    def test_strips_plain_fences(self):
        import app.llm as llm_mod
        raw = '```\n{"key": "value"}\n```'
        assert llm_mod._strip_fences(raw) == '{"key": "value"}'

    def test_passes_through_clean_json(self):
        import app.llm as llm_mod
        raw = '{"key": "value"}'
        assert llm_mod._strip_fences(raw) == '{"key": "value"}'
