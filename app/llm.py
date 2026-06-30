"""
LLM client wrapper — single chokepoint for every model call.

Handles model routing, structured-output parsing, DRY_RUN test mode,
and error handling (JSON parse retry, rate-limit backoff).

No agent-specific prompts live here — only the mechanics of making
a structured call and routing to a model tier.

See: docs/02-llm-client.md
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Optional

# ---------------------------------------------------------------------------
# Model routing constants
# ---------------------------------------------------------------------------
# Resolved from Anthropic's current model documentation (mid-2026).
# These are pinned snapshots, not evergreen aliases.

MODEL_FAST = "claude-haiku-4-5"        # Extraction tasks (Ledger, Profiler)
MODEL_SMART = "claude-sonnet-4-6"      # Generation tasks (Resume, Project)
MODEL_JUDGE = "claude-sonnet-4-6"      # Judgment tasks (Critic, Interview Coach)

# ---------------------------------------------------------------------------
# DRY_RUN flag — read once at module load
# ---------------------------------------------------------------------------

DRY_RUN: bool = os.getenv("DRY_RUN", "false").lower() == "true"

# ---------------------------------------------------------------------------
# Lazy Anthropic client — NOT constructed at import time so that:
#   1. Importing this module doesn't require an API key (enables DRY_RUN CI).
#   2. The client is only created when a real API call is needed.
# ---------------------------------------------------------------------------

_client = None


def _get_client():
    """Lazily construct and return the Anthropic client."""
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Either set it in your environment "
                "or .env file, or use DRY_RUN=true for testing without an API key."
            )
        import anthropic
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


# ---------------------------------------------------------------------------
# JSON extraction helpers
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?\s*```$", re.DOTALL)


def _strip_fences(text: str) -> str:
    """Defensively strip markdown code fences the model sometimes adds."""
    text = text.strip()
    m = _FENCE_RE.match(text)
    if m:
        return m.group(1).strip()
    # Also handle cases where there are just leading/trailing backticks
    if text.startswith("```"):
        text = text.lstrip("`").lstrip()
        if text.lower().startswith("json"):
            text = text[4:].lstrip()
    if text.endswith("```"):
        text = text[: -3].rstrip()
    return text.strip()


# ---------------------------------------------------------------------------
# Core function: call_structured
# ---------------------------------------------------------------------------

_JSON_INSTRUCTION = (
    "\n\nRespond with ONLY a single valid JSON object. "
    "No markdown fences, no preamble, no explanation."
)


def call_structured(
    system_prompt: str,
    user_prompt: str,
    model: str,
    stub: Optional[dict] = None,
    max_tokens: int = 3000,
) -> dict:
    """Make a structured (JSON) call to the LLM, or return a stub in DRY_RUN mode.

    Args:
        system_prompt: The system prompt for the model.
        user_prompt: The user prompt (will have JSON instruction appended).
        model: One of MODEL_FAST, MODEL_SMART, MODEL_JUDGE.
        stub: Deterministic stub data for DRY_RUN mode. Must not be None
              in DRY_RUN mode — a missing stub is a bug in the calling agent.
        max_tokens: Maximum tokens for the response.

    Returns:
        Parsed JSON dict from the model response, or the stub in DRY_RUN mode.

    Raises:
        RuntimeError: If DRY_RUN is true and stub is None; if ANTHROPIC_API_KEY
            is missing in non-DRY_RUN mode; or if JSON parsing fails after retry.
    """
    # ---- DRY_RUN path ----
    if DRY_RUN:
        if stub is None:
            raise RuntimeError(
                "DRY_RUN is enabled but no stub was provided. "
                "Every agent must supply a stub dict for DRY_RUN testing. "
                f"Prompt snippet: {user_prompt[:80]!r}"
            )
        return stub

    # ---- Real API call path ----
    client = _get_client()
    full_user_prompt = user_prompt + _JSON_INSTRUCTION

    raw_text = _call_with_rate_limit_retry(
        client, system_prompt, full_user_prompt, model, max_tokens
    )

    # Try to parse JSON, with one retry on failure
    try:
        return json.loads(_strip_fences(raw_text))
    except json.JSONDecodeError:
        # One retry: re-call with a corrective note
        retry_prompt = (
            full_user_prompt
            + "\n\nYour previous response was not valid JSON. "
            "Return ONLY the JSON object."
        )
        raw_text = _call_with_rate_limit_retry(
            client, system_prompt, retry_prompt, model, max_tokens
        )
        try:
            return json.loads(_strip_fences(raw_text))
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"LLM returned invalid JSON after retry. "
                f"JSONDecodeError: {e}\n"
                f"Raw output (first 500 chars): {raw_text[:500]!r}\n"
                f"Prompt (first 80 chars): {user_prompt[:80]!r}"
            ) from e


def _call_with_rate_limit_retry(
    client, system_prompt: str, user_prompt: str, model: str, max_tokens: int
) -> str:
    """Make an API call with one rate-limit retry + backoff."""
    import anthropic

    for attempt in range(2):  # at most 2 attempts
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            # Extract the text content from the response
            return response.content[0].text
        except anthropic.RateLimitError:
            if attempt == 0:
                time.sleep(5)  # short backoff before one retry
                continue
            raise  # propagate on second failure

    # Should not reach here, but just in case
    raise RuntimeError("Unexpected: exhausted rate-limit retries without result")
