# Module: `app/server.py` — HTTP API

## Purpose

Exposes the pipeline over HTTP so a frontend (or any non-CLI client) can
drive it. Build this last, after the graph is tested in isolation.

## Framework

FastAPI. Use Pydantic request/response models so the API is
self-documenting via `/docs`.

## Endpoints — Tier 1 (matches the pass-through human checkpoint)

### `POST /run`

Request body:
```
{
  "jd_text": str,
  "raw_profile_text": str,
  "max_revisions": int = 2
}
```

Behavior: runs the full graph end to end in one call (since the Tier 1
human checkpoint is a no-op). Response includes both the draft and the
final kit, with an explicit note that the draft should be reviewed first:

```
{
  "run_id": str,
  "resume_markdown": str,
  "project": {...ProjectBlueprint fields...},
  "critic_report": {...CriticReport fields...},
  "interview_kit": {...InterviewKit fields...},
  "note": "Review resume_markdown and project before treating this as final."
}
```

Store the full state in an in-memory dict keyed by `run_id` for this tier —
acceptable for a single-process dev build, explicitly not durable, and
should be called out as such in a comment.

### `GET /health`

Returns `{"status": "ok"}`. No logic, just a liveness check.

## Endpoints — Tier 2 (once the real interrupt/resume checkpoint is built — see `09-human-checkpoint.md`)

### `POST /run` (revised)

Same request shape. Now actually stops at the interrupt — response contains
the draft fields only, no `interview_kit`:

```
{
  "run_id": str,
  "resume_markdown": str,
  "project": {...},
  "critic_report": {...}
}
```

### `POST /approve/{run_id}`

No body required (or optionally an empty body / confirmation flag). Resumes
the graph from the checkpoint identified by `run_id`. Response:

```
{
  "run_id": str,
  "interview_kit": {...}
}
```

Errors:
- `404` if `run_id` is unknown.
- `409` if `run_id` has already been approved/completed.

### `POST /reject/{run_id}`

Body: `{"feedback": str}`. Re-enters `generation_crew` with the human's
feedback merged into the same feedback mechanism the Critic uses. Response
shape matches `/run`'s response (a new draft to review).

## Error handling

Wrap the graph invocation in a try/except that catches `RuntimeError`
(raised by `app/llm.py` on JSON parse failure after retry, or on missing
API key) and returns a `502` with the error message — don't let a raw
Python traceback leak to the client as a `500`.

## CORS

If a frontend will call this from a browser on a different origin, add
FastAPI's `CORSMiddleware` with an explicit allowed-origins list — do not
default to `allow_origins=["*"]` for anything beyond local development.

## Acceptance tests for this module

- `POST /run` with valid input returns `200` and a response matching the
  shape above (use `TestClient`, with `DRY_RUN=true` so the test suite
  doesn't require an API key).
- `POST /run` with missing required fields returns `422` (FastAPI's default
  validation behavior — just confirm it isn't being swallowed by a broad
  except clause somewhere).
- (Tier 2) `POST /approve/{run_id}` with a bogus `run_id` returns `404`.
