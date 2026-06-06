#!/usr/bin/env python3
"""Render the skill-eval-coverage PR comment from detect-skill-changes JSON.

ADR: skill-eval-pr-ablation (Decision 2). Reads the detector's JSON report
(path arg, default stdin) and writes the sticky-comment markdown to stdout.

Body (per the ADR):
  - leading marker `<!-- skill-eval-coverage -->` so CI can edit-in-place;
  - per mapped skill: "<skill> -> eval <eval_dir>. Run locally:
    make skill-eval-ablation BASE=<base> HEAD=<head> SKILL=<skill>";
  - per uncovered skill: "no eval coverage for changed skill(s): <skill>" --
    a gap to consider, not a failure.

Report-only. Always exits 0; a malformed report yields a minimal comment.
"""

from __future__ import annotations

import json
import sys

MARKER = "<!-- skill-eval-coverage -->"


def render(report: dict) -> str:
    """Build the comment markdown from a detector report object."""
    base = str(report.get("base", ""))[:12]
    head = str(report.get("head", ""))[:12]
    mapped = report.get("mapped", []) or []
    uncovered = report.get("uncovered", []) or []
    changed = report.get("changed_skills", []) or []

    lines: list[str] = [MARKER, "## Skill-eval coverage", ""]
    lines.append(f"Changed skills in this PR: {len(changed)} (`{base}..{head}`).")
    lines.append("")
    lines.append(
        "_Report only. CI cannot run evals (the runner needs the `claude` CLI). "
        "Run the ablation locally to get the base->head delta._"
    )
    lines.append("")

    if mapped:
        lines.append("### Mapped")
        for m in mapped:
            skill = m.get("skill", "")
            eval_dir = m.get("eval_dir", "")
            lines.append(
                f"- `{skill}` -> eval `{eval_dir}`. "
                f"Run locally: `make skill-eval-ablation BASE={base} HEAD={head} SKILL={skill}`"
            )
        lines.append("")

    if uncovered:
        lines.append("### Uncovered")
        joined = ", ".join(f"`{s}`" for s in uncovered)
        lines.append(f"no eval coverage for changed skill(s): {joined}")
        lines.append("_A gap to consider, not a failure._")
        lines.append("")

    if not mapped and not uncovered:
        lines.append("_No changed skills mapped or uncovered._")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    try:
        if len(sys.argv) > 1:
            with open(sys.argv[1], encoding="utf-8") as fh:
                report = json.load(fh)
        else:
            report = json.load(sys.stdin)
    except (OSError, json.JSONDecodeError):
        report = {}
    sys.stdout.write(render(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
