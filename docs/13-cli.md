# Module: `app/main.py` — CLI entrypoint

## Purpose

The simplest, most dependency-free way to run the pipeline — useful as the
first proof that the whole system works, before the API server is built.

## Interface

```
python -m app.main --jd <path> --profile <path> [--out <path>] [--max-revisions <int>]
```

| Flag | Default | Notes |
|---|---|---|
| `--jd` | required | Path to a text file containing the job description |
| `--profile` | required | Path to a text file containing the user's raw background |
| `--out` | `interview_kit.md` | Output file path |
| `--max-revisions` | `2` | Passed through to the graph |

## Behavior

1. Load `.env` (via `python-dotenv`) so `ANTHROPIC_API_KEY` and `DRY_RUN`
   can be set in a local `.env` file instead of exported manually.
2. Read both input files as plain text.
3. Build and invoke the graph with the initial state
   (`jd_text`, `raw_profile_text`, `revision_count=0`, `max_revisions`).
4. Print the draft resume and any unresolved Critic issues to **stderr**
   (not stdout — keep stdout clean in case this is ever piped).
5. If running interactively (`sys.stdin.isatty()`) and not in `DRY_RUN`,
   prompt `"Approve and generate the interview kit? [y/N]: "`. If the answer
   isn't `y`, stop without writing the output file.
6. Render the full kit (resume, project, resources, interview questions,
   and — if the critic never passed — an unresolved-issues section) to
   Markdown and write it to `--out`.

## Why stderr for the interactive prompt/draft output

This keeps `stdout` reserved for actual structured output if this CLI is
ever composed with other tools (e.g. `python -m app.main ... > log.txt`
shouldn't capture the interactive prompt text).

## Rendering function

Implement a `render_kit(state: dict) -> str` function, separate from
`main()`, that takes the final pipeline state and produces the Markdown
output. Keeping this separate makes it independently testable without
running the whole CLI argument-parsing flow.

## Edge cases to handle

| Case | Required behavior |
|---|---|
| `DRY_RUN=true` | Skip the interactive approval prompt entirely (there's nothing meaningful to approve in stub data) and write the output file directly — this is what makes dry-run useful as an automated smoke test. |
| Non-interactive shell (e.g. CI, or piped input) with `DRY_RUN=false` | Don't hang waiting for input that will never come — check `sys.stdin.isatty()` before prompting, and if not interactive, proceed without prompting (document this behavior clearly, since silently skipping human approval in a non-interactive context is a deliberate tradeoff, not an oversight). |
| Critic never passed (max revisions exhausted) | `render_kit` should still produce a complete file, with an additional "QA notes (unresolved after max revisions)" section listing the Critic's outstanding issues — never silently drop this information. |

## Acceptance tests for this module

1. `render_kit` given a fully-populated stub state produces Markdown
   containing all of: resume content, project title, at least one resource
   link, at least one interview question.
2. `render_kit` given a state with a failed `critic_report` includes the
   "QA notes" section with the specific issue text present.
3. Full CLI smoke test: run `DRY_RUN=true python -m app.main --jd
   sample_data/jd.txt --profile sample_data/profile.txt --out
   /tmp/test_kit.md` as a subprocess, assert exit code `0` and that
   `/tmp/test_kit.md` exists and is non-empty.
