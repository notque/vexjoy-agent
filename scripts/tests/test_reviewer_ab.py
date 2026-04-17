#!/usr/bin/env python3
"""
A/B test harness for reviewer-code vs reviewer-code-playbook.

Usage:
    python3 scripts/tests/test_reviewer_ab.py --file hooks/session-context.py

Compares the original reviewer-code agent against the playbook-enhanced variant
on the same file, then prints both outputs side-by-side for manual evaluation.

This is a setup file — actual evaluation requires manual judgment or the
agent-comparison skill.

ADR-160: Playbook-derived prompt architecture patterns applied to reviewer-code:
  a) Constraints at point of failure (not just global)
  b) Numeric anchors replacing vague words
  c) Anti-rationalization at point of use
  d) Explicit output contract
  e) Verifier stance
"""

import argparse
import os
import sys
from pathlib import Path

# Agent file locations (relative to repo root)
AGENT_A = "agents/reviewer-code.md"
AGENT_B = "agents/reviewer-code-playbook.md"

# Also check ~/.claude/agents/ as fallback
HOME_AGENTS = Path.home() / ".claude" / "agents"


def resolve_agent_path(relative: str) -> Path:
    """Resolve agent path, checking repo first then ~/.claude/agents/."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    repo_path = repo_root / relative
    if repo_path.is_file():
        return repo_path

    home_path = HOME_AGENTS / Path(relative).name
    if home_path.is_file():
        return home_path

    return repo_path  # Return repo path even if missing, for error reporting


def main() -> int:
    parser = argparse.ArgumentParser(
        description="A/B test harness for reviewer-code vs reviewer-code-playbook",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--file",
        required=True,
        help="Path to the file to review (relative or absolute)",
    )
    parser.add_argument(
        "--dimension",
        default="code-quality",
        help="Review dimension to test (default: code-quality)",
    )
    args = parser.parse_args()

    target_file = Path(args.file)
    if not target_file.is_file():
        print(f"Error: Target file not found: {args.file}", file=sys.stderr)
        return 1

    agent_a_path = resolve_agent_path(AGENT_A)
    agent_b_path = resolve_agent_path(AGENT_B)

    missing = []
    if not agent_a_path.is_file():
        missing.append(f"  Agent A (control): {agent_a_path}")
    if not agent_b_path.is_file():
        missing.append(f"  Agent B (variant): {agent_b_path}")

    if missing:
        print("Error: Missing agent file(s):", file=sys.stderr)
        for m in missing:
            print(m, file=sys.stderr)
        return 1

    print("=" * 70)
    print("REVIEWER-CODE A/B TEST HARNESS (ADR-160)")
    print("=" * 70)
    print()
    print(f"Target file:  {target_file.resolve()}")
    print(f"Dimension:    {args.dimension}")
    print()
    print(f"Agent A (control): {agent_a_path}")
    print(f"Agent B (variant): {agent_b_path}")
    print()
    print("-" * 70)
    print("CHANGES IN VARIANT (reviewer-code-playbook):")
    print("-" * 70)
    print()
    print("  a) Constraints duplicated at point of failure with 'because' reasons")
    print("  b) Numeric anchors: max 5 findings/dimension, 4-field format required,")
    print("     max 2 sentences context per finding")
    print("  c) Anti-rationalization STOP blocks after read, report, and severity")
    print("  d) Explicit output contract: 7-section format with verdict rules")
    print("  e) Verifier stance: 'find problems, not approve code'")
    print()
    print("-" * 70)
    print("HOW TO RUN THE A/B TEST:")
    print("-" * 70)
    print()
    print("Option 1: Use the agent-comparison skill (recommended)")
    print()
    print("  /agent-comparison")
    print(f"  Compare agents/{Path(AGENT_A).stem} vs agents/{Path(AGENT_B).stem}")
    print(f"  on file: {target_file}")
    print(f"  dimension: {args.dimension}")
    print()
    print("Option 2: Manual side-by-side via subagents")
    print()
    print("  Run each agent in a separate subagent with the same prompt:")
    print(f'  "Review {target_file} for {args.dimension}"')
    print()
    print("  Then compare outputs on these evaluation criteria:")
    print("    1. Did it find real issues? (precision)")
    print("    2. Did it miss known issues? (recall)")
    print("    3. Was the output structured and actionable? (format)")
    print("    4. Did it avoid false positives? (specificity)")
    print("    5. Was severity assignment accurate? (calibration)")
    print()
    print("-" * 70)
    print("EVALUATION CRITERIA:")
    print("-" * 70)
    print()
    print("  Score each agent 1-5 on:")
    print("    - Precision:    Findings that are real issues (not false positives)")
    print("    - Recall:       Known issues that were found")
    print("    - Actionability: Each finding has file:line + fix suggestion")
    print("    - Calibration:  Severity matches actual impact")
    print("    - Format:       Output follows structured contract")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
