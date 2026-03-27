#!/usr/bin/env python3
"""
package_results.py — Consolidate all iteration artifacts into a summary report.

Reads grading.json, benchmark.json, analysis.json, and changes.md from each iteration
directory in the workspace. Produces a single summary report.

Usage:
  python3 package_results.py workspace/ --format markdown
  python3 package_results.py workspace/ --format json
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Consolidate eval iteration artifacts into a summary report",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("workspace", help="Path to skill-workspace/ root directory")
    p.add_argument(
        "--format", choices=["markdown", "json"], default="markdown", help="Output format (default: markdown)"
    )
    p.add_argument("--output", help="Output file path (default: workspace/summary.md or summary.json)")
    return p


def find_iteration_dirs(workspace: Path) -> list[Path]:
    """Find all iteration-N directories in the workspace."""
    iterations = []
    for child in sorted(workspace.iterdir()):
        if child.is_dir() and child.name.startswith("iteration-"):
            try:
                int(child.name.split("-")[1])
                iterations.append(child)
            except (IndexError, ValueError):
                pass
    return sorted(iterations, key=lambda p: int(p.name.split("-")[1]))


def load_json_safe(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def load_text_safe(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        return path.read_text()
    except OSError:
        return None


def collect_iteration_data(iteration_dir: Path) -> dict:
    """Collect all artifacts from a single iteration directory."""
    data = {
        "iteration": iteration_dir.name,
        "benchmark": load_json_safe(iteration_dir / "benchmark.json"),
        "analysis": load_json_safe(iteration_dir / "analysis.json"),
        "changes": load_text_safe(iteration_dir / "changes.md"),
        "evals": [],
    }

    # Collect per-eval data
    for child in sorted(iteration_dir.iterdir()):
        if child.is_dir():
            grading = load_json_safe(child / "grading.json")
            if grading:
                data["evals"].append(
                    {
                        "eval_id": child.name,
                        "grading": grading,
                    }
                )

    return data


def render_markdown(workspace: Path, iterations: list[dict]) -> str:
    lines = [
        "# Skill Eval Summary\n",
        f"**Workspace**: `{workspace}`  \n",
        f"**Generated**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}  \n",
        f"**Iterations**: {len(iterations)}\n\n",
    ]

    # Progress table across iterations
    if any(it["benchmark"] for it in iterations):
        lines.append("## Pass Rate Progression\n\n")
        lines.append("| Iteration | With Skill | Without Skill | Delta |\n")
        lines.append("|-----------|-----------|---------------|-------|\n")

        for it in iterations:
            b = it["benchmark"]
            if b:
                ws = b.get("with_skill", {}).get("pass_rate", {}).get("mean", 0)
                wos = b.get("without_skill", {}).get("pass_rate", {}).get("mean", 0)
                delta = b.get("delta", {}).get("pass_rate")
                delta_str = (
                    f"+{delta:.1%}"
                    if delta is not None and delta > 0
                    else (f"{delta:.1%}" if delta is not None else "N/A")
                )
                lines.append(f"| {it['iteration']} | {ws:.1%} | {wos:.1%} | {delta_str} |\n")
            else:
                lines.append(f"| {it['iteration']} | — | — | — |\n")

        lines.append("\n")

    # Per-iteration sections
    for it in iterations:
        lines.append(f"## {it['iteration'].replace('-', ' ').title()}\n\n")

        # Changes summary
        if it["changes"]:
            lines.append("### Changes Made\n\n")
            # Include first 50 lines of changes.md
            change_lines = it["changes"].split("\n")[:50]
            lines.append("\n".join(change_lines))
            if len(it["changes"].split("\n")) > 50:
                lines.append("\n_(truncated — see changes.md for full content)_")
            lines.append("\n\n")

        # Eval results
        if it["evals"]:
            lines.append("### Eval Results\n\n")
            lines.append("| Eval | Pass Rate | Pass | Fail |\n")
            lines.append("|------|-----------|------|------|\n")
            for ev in it["evals"]:
                g = ev["grading"]
                lines.append(
                    f"| {ev['eval_id']} | {g.get('pass_rate', 0):.1%} | {g.get('pass_count', 0)} | {g.get('fail_count', 0)} |\n"
                )
            lines.append("\n")

        # Top findings from analysis
        if it["analysis"]:
            findings = it["analysis"].get("findings", [])
            high_priority = [f for f in findings if f.get("priority") == "high"]
            if high_priority:
                lines.append("### High-Priority Findings\n\n")
                for f in high_priority[:5]:
                    lines.append(f"- **{f.get('category', 'finding')}**: {f.get('finding', '')}\n")
                    if f.get("actionable_suggestion"):
                        lines.append(f"  - Suggestion: {f['actionable_suggestion']}\n")
                lines.append("\n")

    # Final recommendation
    if iterations:
        last = iterations[-1]
        b = last.get("benchmark")
        if b:
            delta = b.get("delta", {}).get("pass_rate")
            if delta is not None:
                lines.append("## Final Assessment\n\n")
                if delta > 0.05:
                    lines.append(f"The skill demonstrates measurable improvement: pass rate delta = +{delta:.1%}\n")
                elif delta < -0.05:
                    lines.append(f"The skill performs below baseline: pass rate delta = {delta:.1%}\n")
                    lines.append(
                        "Consider reviewing skill instructions — they may be adding noise rather than signal.\n"
                    )
                else:
                    lines.append(f"The skill shows marginal impact: pass rate delta = {delta:.1%}\n")
                    lines.append("Check whether eval assertions are discriminating (test skill-specific behavior).\n")

    return "".join(lines)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    workspace = Path(args.workspace).resolve()

    if not workspace.exists():
        print(f"ERROR: Workspace does not exist: {workspace}", file=sys.stderr)
        return 1

    iteration_dirs = find_iteration_dirs(workspace)
    if not iteration_dirs:
        print(f"WARNING: No iteration directories found in {workspace}", file=sys.stderr)

    iterations = [collect_iteration_data(d) for d in iteration_dirs]

    if args.format == "markdown":
        content = render_markdown(workspace, iterations)
        default_name = "summary.md"
    else:
        content = json.dumps(
            {
                "workspace": str(workspace),
                "generated": datetime.now(timezone.utc).isoformat(),
                "iterations": iterations,
            },
            indent=2,
        )
        default_name = "summary.json"

    output_path = Path(args.output).resolve() if args.output else (workspace / default_name)
    output_path.write_text(content)
    print(f"Written: {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
