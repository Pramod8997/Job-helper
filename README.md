# Career Crew 🎯

A multi-agent AI system that turns a **job description** and a **candidate's real background** into a complete, grounded interview prep kit — without fabricating anything.

## What It Produces

| Output | Description |
|---|---|
| **ATS-Optimized Resume** | Single-column Markdown resume with keyword optimization |
| **Project Recommendation** | One realistically buildable project that closes skill gaps |
| **Resource Cheat Sheet** | CLI commands, config snippets, and curated learning links |
| **Interview Prep Kit** | Technical questions, behavioral questions, and STAR-framed answer outlines |

## Architecture

```
[job description] + [raw profile]
           │
           ▼
  ┌─────────────────┐
  │ Capability Ledger│  ← extracts facts only, no creativity
  └────────┬─────────┘
           ▼
  ┌─────────────────┐
  │ Market & ATS    │  ← extracts keywords, not generation
  │ Profiler        │
  └────────┬─────────┘
           ▼
  ┌─────────────────────────────┐
  │ Generation Crew              │
  │ (resume + project + resources)│
  └────────┬─────────────────────┘
           ▼
  ┌─────────────────┐     fail + retries left
  │ QA & Feasibility│ ─────────────────────┐
  │ Critic          │                       │
  └────────┬─────────┘                     │
           │ pass / retries exhausted       │
           ▼                                │
  ┌─────────────────┐                       │
  │ Human Checkpoint│                       │
  └────────┬─────────┘                     │
           ▼                                │
  ┌─────────────────┐                       │
  │ Interview Coach │                       │
  └────────┬─────────┘                     │
           ▼                                │
     [interview kit]                (back to generation)
```

## Quick Start

```bash
# 1. Clone and set up
git clone https://github.com/Pramod8997/Job-helper.git
cd Job-helper
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Test without an API key (DRY_RUN mode)
DRY_RUN=true python -m app.main \
  --jd sample_data/jd.txt \
  --profile sample_data/profile.txt

# 3. Run with a real API key
cp .env.example .env
# Edit .env → set ANTHROPIC_API_KEY=sk-ant-...
python -m app.main \
  --jd sample_data/jd.txt \
  --profile sample_data/profile.txt

# 4. Start the API server
uvicorn app.server:app --reload
# Visit http://localhost:8000/docs for the interactive API docs
```

## CLI Usage

```
python -m app.main --jd <path> --profile <path> [--out <path>] [--max-revisions <int>]
```

| Flag | Default | Description |
|---|---|---|
| `--jd` | *required* | Path to job description text file |
| `--profile` | *required* | Path to candidate profile text file |
| `--out` | `interview_kit.md` | Output file path |
| `--max-revisions` | `2` | Max critic revision attempts before proceeding |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check → `{"status": "ok"}` |
| `POST` | `/run` | Run the full pipeline, returns resume + project + interview kit |

**POST /run** request body:
```json
{
  "jd_text": "We are looking for a backend engineer...",
  "raw_profile_text": "I am Jane Doe, a CS student...",
  "max_revisions": 2
}
```

## Testing

```bash
# Run all 42 tests (no API key needed)
DRY_RUN=true python -m pytest tests/ -v

# Run specific test modules
DRY_RUN=true python -m pytest tests/test_models.py -v    # Schema tests
DRY_RUN=true python -m pytest tests/test_agents.py -v    # Agent unit tests
DRY_RUN=true python -m pytest tests/test_graph.py -v     # Graph integration tests
DRY_RUN=true python -m pytest tests/test_cli.py -v       # CLI smoke tests
DRY_RUN=true python -m pytest tests/test_server.py -v    # API server tests
```

## Project Structure

```
career-crew/
  app/
    __init__.py       # Package init
    models.py         # Pydantic data contracts (7 models + PipelineState)
    llm.py            # LLM client wrapper with DRY_RUN support
    agents.py         # All agent functions (ledger → critic → interview coach)
    graph.py          # LangGraph StateGraph with revise loop
    server.py         # FastAPI HTTP API
    main.py           # CLI entrypoint
  tests/              # 42 tests, all runnable with DRY_RUN=true
  sample_data/
    jd.txt            # Sample job description
    profile.txt       # Sample candidate profile
  docs/               # Detailed specs (00-overview through 14-testing-strategy)
  requirements.txt
  .env.example
```

## Design Principles

1. **Grounding over generation** — No agent may state anything not traceable to the Capability Ledger
2. **Verification ≠ generation** — The Critic agent is distinct from the generation agents
3. **Bounded revision** — Real graph cycle, capped by `max_revisions` (default 2)
4. **Human approval gate** — Interview kit generation waits for human review
5. **Token-free testing** — Every agent supports `DRY_RUN` mode with deterministic stubs

## Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Orchestration | LangGraph (`StateGraph`) | Supports real cycles for the critic → generation revise loop |
| LLM | Claude via `anthropic` SDK | Direct SDK, no extra abstraction layer |
| API | FastAPI | Auto-documented endpoints with Pydantic models |
| Data contracts | Pydantic | Typed models enable programmatic claim verification |
| State | `TypedDict` wrapping Pydantic | Compatible with LangGraph's state-merge conventions |

## Known Limitations

- **English only** — non-English input is out of scope for v1
- **Resource links** — in `DRY_RUN` mode, links are stubbed; production should use Anthropic's web search tool
- **Human checkpoint** — currently Tier 1 (pass-through); Tier 2 (true interrupt/resume) is spec'd but not implemented

## License

MIT
