"""
CLI entrypoint for the Career Crew pipeline.

Usage:
  python -m app.main --jd <path> --profile <path> [--out <path>] [--max-revisions <int>]

See: docs/13-cli.md
"""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv


def render_kit(state: dict) -> str:
    """Render the final pipeline state into a Markdown interview kit.

    This is separate from main() so it can be tested independently.

    Args:
        state: The final pipeline state dict.

    Returns:
        A Markdown string containing the full interview prep kit.
    """
    sections = []

    # --- Resume ---
    resume = state.get("resume")
    if resume:
        sections.append("# Resume\n")
        sections.append(resume.markdown)
        sections.append("")

    # --- Project Recommendation ---
    project = state.get("project")
    if project:
        sections.append("# Project Recommendation\n")
        sections.append(f"## {project.title}\n")
        sections.append(project.description)
        sections.append(f"\n**Architecture:** {project.architecture}\n")
        sections.append(f"**Tech Stack:** {', '.join(project.tech_stack)}\n")
        sections.append(f"**Estimated Weeks:** {project.estimated_weeks}\n")
        sections.append("### Milestones\n")
        for i, m in enumerate(project.milestones, 1):
            sections.append(f"{i}. {m}")
        sections.append("")

    # --- Resources ---
    resources = state.get("resources")
    if resources:
        sections.append("# Resources\n")
        sections.append(resources.cheat_sheet_markdown)
        sections.append("\n## Links\n")
        for link in resources.links:
            sections.append(f"- {link}")
        sections.append("")

    # --- Interview Prep ---
    interview_kit = state.get("interview_kit")
    if interview_kit:
        sections.append("# Interview Prep\n")

        sections.append("## Technical Questions\n")
        for q in interview_kit.technical_questions:
            sections.append(f"- {q}")

        sections.append("\n## Behavioral Questions & STAR Answers\n")
        for i, (q, a) in enumerate(
            zip(interview_kit.behavioral_questions, interview_kit.star_answers), 1
        ):
            sections.append(f"### Q{i}: {q}\n")
            sections.append(f"**STAR Answer Outline:** {a}\n")

    # --- QA Notes (if critic never passed) ---
    critic_report = state.get("critic_report")
    if critic_report and not critic_report.passed:
        sections.append("# ⚠️ QA Notes (unresolved after max revisions)\n")
        if critic_report.issues:
            sections.append("## Issues\n")
            for issue in critic_report.issues:
                sections.append(f"- {issue}")
        if critic_report.unsupported_claims:
            sections.append("\n## Unsupported Claims\n")
            for claim in critic_report.unsupported_claims:
                sections.append(f"- {claim}")
        if critic_report.feasibility_concerns:
            sections.append("\n## Feasibility Concerns\n")
            for concern in critic_report.feasibility_concerns:
                sections.append(f"- {concern}")
        sections.append("")

    return "\n".join(sections)


def main():
    """CLI entrypoint."""
    # Load .env so ANTHROPIC_API_KEY and DRY_RUN can be set there
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Career Crew — multi-agent interview prep kit generator"
    )
    parser.add_argument(
        "--jd", required=True, help="Path to job description text file"
    )
    parser.add_argument(
        "--profile", required=True, help="Path to candidate profile text file"
    )
    parser.add_argument(
        "--out", default="interview_kit.md", help="Output file path (default: interview_kit.md)"
    )
    parser.add_argument(
        "--max-revisions", type=int, default=2,
        help="Max critic revision attempts (default: 2)"
    )

    args = parser.parse_args()

    # Read input files
    with open(args.jd, "r") as f:
        jd_text = f.read().strip()
    with open(args.profile, "r") as f:
        raw_profile_text = f.read().strip()

    # Build and invoke the graph
    from app.graph import build_graph

    graph = build_graph()
    initial_state = {
        "jd_text": jd_text,
        "raw_profile_text": raw_profile_text,
        "revision_count": 0,
        "max_revisions": args.max_revisions,
    }

    final_state = graph.invoke(initial_state)

    # Print draft resume and critic issues to stderr (keep stdout clean)
    resume = final_state.get("resume")
    if resume:
        print("═══ DRAFT RESUME ═══", file=sys.stderr)
        print(resume.markdown, file=sys.stderr)

    critic_report = final_state.get("critic_report")
    if critic_report and not critic_report.passed:
        print("\n⚠️  UNRESOLVED CRITIC ISSUES:", file=sys.stderr)
        for issue in critic_report.issues:
            print(f"  - {issue}", file=sys.stderr)
        for claim in critic_report.unsupported_claims:
            print(f"  - Unsupported claim: {claim}", file=sys.stderr)
        for concern in critic_report.feasibility_concerns:
            print(f"  - Feasibility: {concern}", file=sys.stderr)

    # DRY_RUN mode: skip interactive prompt, write directly
    dry_run = os.getenv("DRY_RUN", "false").lower() == "true"

    if not dry_run and sys.stdin.isatty():
        print(
            "\nApprove and generate the interview kit? [y/N]: ",
            end="",
            file=sys.stderr,
        )
        answer = input().strip().lower()
        if answer != "y":
            print("Aborted.", file=sys.stderr)
            sys.exit(0)

    # Render and write output
    output = render_kit(final_state)
    with open(args.out, "w") as f:
        f.write(output)

    print(f"\n✅ Interview kit written to: {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
