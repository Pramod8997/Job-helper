# Module: `app/llm.py` — LLM client wrapper

## Purpose

A single chokepoint for every model call in the system. This is where model
routing, structured-output parsing, and the DRY_RUN test mode all live, so
no agent file needs to know how to talk to the Anthropic API directly.

## Requirements

### Model routing

Define three model constants and use them deliberately — do not call every
agent with the same model:

| Constant | Suggested model | Used by |
|---|---|---|
| `MODEL_FAST` | a small/cheap model (e.g. Haiku tier) | Capability Ledger, Profiler — pure extraction tasks, no creative judgment needed |
| `MODEL_SMART` | a strong general model (e.g. Sonnet tier) | Resume Architect, Project Strategist — generation tasks where quality matters |
| `MODEL_JUDGE` | a strong general model | Critic, Interview Coach — judgment/evaluation tasks |

Resolve actual model name strings via Anthropic's current model documentation
at build time rather than hardcoding from memory — model name strings change.

### `DRY_RUN` mode

Read `os.getenv("DRY_RUN", "false").lower() == "true"` once at module load.

Implement one function, something like:

```
call_structured(system_prompt: str, user_prompt: str, model: str,
                 stub: dict | None, max_tokens: int = 3000) -> dict
```

Behavior:
- If `DRY_RUN` is true: return `stub` immediately. Raise a clear error if
  `stub` is `None` — a missing stub in dry-run mode is a bug in the calling
  agent, not something to silently skip.
- If `DRY_RUN` is false: lazily construct the Anthropic client (don't
  construct it at import time — that would require an API key to even be
  *importable*, which breaks dry-run testing in CI environments with no key
  set at all). Make the actual API call.

### Structured JSON output strategy

The system does not use tool-calling/function-calling for structured output
in this build (keep it simple) — instead:
1. Append an explicit instruction to the user prompt: respond with ONLY a
   single valid JSON object, no markdown fences, no preamble, no explanation.
2. After getting the response text, defensively strip leading/trailing
   backticks and a leading `json` language tag in case the model adds fences
   anyway.
3. Parse with `json.loads`. On `JSONDecodeError`, raise a `RuntimeError` that
   includes the first ~500 characters of the raw model output and the first
   ~80 characters of the prompt that produced it — this is the single most
   useful debugging signal when an agent misbehaves, so don't swallow it.

### Error handling to add beyond the minimum

The original prototype does not retry on a JSON parse failure. For a
production build, add:
- One retry on `JSONDecodeError`: re-call with an appended note like
  "Your previous response was not valid JSON. Return ONLY the JSON object."
  Cap at 1 retry — don't loop indefinitely on a misbehaving model.
- Catch the Anthropic SDK's rate-limit exception specifically and back off
  with a short sleep + one retry before propagating. Look up the current SDK
  exception class name in the `anthropic` package docs rather than guessing.

## What NOT to put in this file

- No agent-specific prompts. Those belong in `app/agents.py`. This file only
  knows how to make a structured call and route to a model tier — it has no
  opinion about resumes or job descriptions.
- No retries-without-limit. Every retry path needs a hard cap.

## Acceptance tests for this module

1. With `DRY_RUN=true` and a stub provided, `call_structured` returns the
   stub exactly, with no network call attempted (assert this by not setting
   `ANTHROPIC_API_KEY` at all in the test environment — if it tries to build
   a real client it should never get there in dry-run mode).
2. With `DRY_RUN=true` and `stub=None`, it raises.
3. (If you implement the API-key-missing check) calling with `DRY_RUN=false`
   and no `ANTHROPIC_API_KEY` set raises a clear, actionable error rather than
   a raw SDK stack trace.
