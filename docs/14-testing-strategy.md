# Testing strategy

## Philosophy

Every agent and every graph path must be testable with `DRY_RUN=true` and
**zero API key required**. This is not optional polish — it's how you catch
wiring bugs (a missing edge, a broken conditional, a feedback string that
never gets passed) before spending a single real token. Real-model tests
are a separate, smaller, explicitly-opt-in layer on top.

## Test layers, in build order

### 1. Schema tests (`01-data-models.md`)

Construct one valid instance of every Pydantic model, round-trip through
JSON, assert no errors. Run this before writing any agent code.

### 2. LLM client tests (`02-llm-client.md`)

- `call_structured` in `DRY_RUN` mode returns the stub with no network call.
- `call_structured` in `DRY_RUN` mode with `stub=None` raises.
- Missing `ANTHROPIC_API_KEY` with `DRY_RUN=false` raises a clear error, not
  a raw SDK exception.

### 3. Per-agent unit tests (`03` through `08`, `10`)

For each agent: call it in `DRY_RUN` mode with a minimal valid state slice,
assert the returned state update has the expected key and the value is the
correct Pydantic type. Each agent's own spec file lists the specific
assertions worth adding beyond this baseline (e.g. the index-alignment
check for `InterviewKit`, the `unsupported_claims` safety-net check for
`CriticReport`).

### 4. Graph integration tests (`11-orchestration-graph.md`) — highest priority

This is where most of the real risk lives. At minimum:

- **Happy path**: critic passes immediately, graph reaches `END` with a
  populated `interview_kit`.
- **Revise loop**: mock the critic node to fail N times then pass, assert
  it's called more than once and the graph still terminates correctly.
- **Bounded loop**: mock the critic to never pass, assert the graph
  terminates at `max_revisions` rather than running forever.
- **Feedback propagation**: assert that when `generation_crew` is re-entered
  after a failure, the Critic's issues actually reach the generation
  sub-agent calls (inspect call arguments in the test, don't just check the
  node executed).

### 5. CLI smoke test (`13-cli.md`)

Run the CLI as a subprocess with `DRY_RUN=true` and the sample data, assert
exit code 0 and a non-empty output file.

### 6. API tests (`12-api-server.md`)

Use FastAPI's `TestClient` with `DRY_RUN=true`. Cover the happy path and at
least one validation-error path (`422`) and one not-found path (`404`, once
Tier 2 endpoints exist).

### 7. Opt-in real-model tests (NOT part of the default test suite)

These cost real API calls and should be excluded from CI-by-default (e.g.
behind a pytest marker like `@pytest.mark.live`, run manually or in a
separate nightly job):

- End-to-end run against `sample_data/jd.txt` and `sample_data/profile.txt`
  with a real API key, manually inspect the output kit for quality —
  specifically check that the resume's claims field doesn't contain
  anything not in the input profile text (the core integrity guarantee of
  the whole system).
- A deliberately adversarial profile (very sparse, or containing a stretch
  claim like "expert in everything") to manually verify the Critic actually
  catches over-claiming rather than passing it through.

## Definition of done for the build

Before considering the implementation complete, all of the following must
be true:

- [ ] Every file listed in `00-overview.md`'s directory structure exists.
- [ ] `DRY_RUN=true python -m app.main --jd sample_data/jd.txt --profile
      sample_data/profile.txt` runs to completion and produces a non-empty
      output file, with zero `ANTHROPIC_API_KEY` set anywhere in the
      environment.
- [ ] The revise-loop integration test (mocked critic failing then passing)
      passes.
- [ ] The bounded-loop integration test (mocked critic never passing)
      terminates rather than hanging or raising a recursion/timeout error.
- [ ] `uvicorn app.server:app` starts without error and `GET /health`
      returns `200`.
- [ ] At least one real-model smoke test has been run manually (not
      necessarily automated) and the resulting resume was manually checked
      against the input profile for fabricated claims.
