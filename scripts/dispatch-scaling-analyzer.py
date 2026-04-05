#!/usr/bin/env python3
"""
Dispatch Scaling Analyzer — ADR-178 experiment infrastructure.

Analyzes results produced by dispatch-scaling-runner.py. Reads agent output
files, deduplicates findings by sentence-level uniqueness, and computes
marginal value and cost-per-finding metrics across agent counts.

Usage:
    python3 scripts/dispatch-scaling-analyzer.py
    python3 scripts/dispatch-scaling-analyzer.py --results /path/to/results.json
    python3 scripts/dispatch-scaling-analyzer.py --json

Exit codes:
    0 = success
    1 = results.json not found or unreadable
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RESULTS = REPO_ROOT / "benchmark" / "dispatch-scaling" / "results" / "results.json"

# Marginal value threshold below which returns are considered diminishing
DIMINISHING_RETURNS_THRESHOLD = 5


# ---------------------------------------------------------------------------
# Text analysis
# ---------------------------------------------------------------------------


def split_sentences(text: str) -> list[str]:
    """Split text into normalized sentences for deduplication.

    Args:
        text: Raw text output from an agent.

    Returns:
        List of stripped, non-empty sentences.
    """
    parts = re.split(r"[.!?\n]+", text)
    return [s.strip().lower() for s in parts if s.strip()]


def compute_unique_findings(outputs: list[str]) -> tuple[int, int]:
    """Count total and unique sentences across all agent outputs.

    A sentence is "unique" if it does not appear in any other agent's output.

    Args:
        outputs: List of raw text strings, one per agent.

    Returns:
        Tuple of (total_findings, unique_findings).
    """
    per_agent: list[list[str]] = [split_sentences(o) for o in outputs]

    total_findings = sum(len(sentences) for sentences in per_agent)

    # Build a frequency map: sentence -> how many agents produced it
    freq: dict[str, int] = {}
    for sentences in per_agent:
        for s in set(sentences):  # deduplicate within a single agent's output
            freq[s] = freq.get(s, 0) + 1

    unique_findings = sum(1 for count in freq.values() if count == 1)
    return total_findings, unique_findings


# ---------------------------------------------------------------------------
# Results loading and metric computation
# ---------------------------------------------------------------------------


def load_results(results_path: Path) -> dict:
    """Load and validate results.json.

    Args:
        results_path: Path to results.json produced by dispatch-scaling-runner.py.

    Returns:
        Parsed results dict.

    Raises:
        SystemExit: If the file is missing or malformed.
    """
    if not results_path.exists():
        print(f"error: results.json not found at {results_path}", file=sys.stderr)
        print("hint: run dispatch-scaling-runner.py first", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(results_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"error: could not read {results_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    return data


def read_agent_outputs(run: dict, results_dir: Path) -> list[str]:
    """Read raw output text for all agents in a run.

    Falls back to empty string if a file is missing or unreadable.

    Args:
        run: A single run entry from results.json.
        results_dir: Directory containing output files.

    Returns:
        List of agent output strings.
    """
    texts: list[str] = []
    for output in run.get("outputs", []):
        file_name = output.get("file", "")
        if not file_name:
            texts.append("")
            continue
        file_path = results_dir / file_name
        try:
            texts.append(file_path.read_text(encoding="utf-8"))
        except OSError:
            texts.append("")
    return texts


def compute_metrics(data: dict, results_dir: Path) -> list[dict]:
    """Compute per-run metrics from results.json and agent output files.

    Args:
        data: Parsed results.json dict.
        results_dir: Directory containing agent output files.

    Returns:
        List of metric dicts sorted by agent_count ascending.
    """
    rows: list[dict] = []

    for run in data.get("runs", []):
        agent_count = run.get("agent_count", 0)
        wall_clock = run.get("wall_clock_seconds", 0.0)

        total_tokens = sum(o.get("token_estimate", 0) for o in run.get("outputs", []))
        agent_texts = read_agent_outputs(run, results_dir)
        total_findings, unique_findings = compute_unique_findings(agent_texts)

        rows.append(
            {
                "agent_count": agent_count,
                "wall_clock_seconds": wall_clock,
                "total_tokens": total_tokens,
                "total_findings": total_findings,
                "unique_findings": unique_findings,
                "cost_per_finding": round(total_tokens / unique_findings, 2) if unique_findings > 0 else 0.0,
            }
        )

    rows.sort(key=lambda r: r["agent_count"])

    # Compute marginal findings relative to the previous agent count
    for i, row in enumerate(rows):
        if i == 0:
            row["marginal_findings"] = row["unique_findings"]
        else:
            row["marginal_findings"] = row["unique_findings"] - rows[i - 1]["unique_findings"]

    return rows


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def _scaling_summary(rows: list[dict]) -> str:
    """Generate the scaling curve summary section.

    Args:
        rows: Sorted list of per-run metric dicts.

    Returns:
        Markdown string for the summary section.
    """
    if not rows:
        return "_No data available._\n"

    # Find first point where marginal value drops below threshold
    diminishing_at: int | None = None
    for row in rows[1:]:  # skip the first — marginal equals unique for N=1
        if row["marginal_findings"] < DIMINISHING_RETURNS_THRESHOLD:
            diminishing_at = row["agent_count"]
            break

    # Optimal: best cost/finding ratio (lowest non-zero cost_per_finding)
    eligible = [r for r in rows if r["cost_per_finding"] > 0]
    optimal = min(eligible, key=lambda r: r["cost_per_finding"]) if eligible else None

    # Maximum useful: last count where marginal findings > 0
    max_useful: int | None = None
    for row in reversed(rows):
        if row["marginal_findings"] > 0:
            max_useful = row["agent_count"]
            break

    lines = ["## Scaling Curve Summary", ""]
    if diminishing_at is not None:
        lines.append(
            f"- Diminishing returns begin at N={diminishing_at} agents "
            f"(marginal value drops below {DIMINISHING_RETURNS_THRESHOLD})"
        )
    else:
        lines.append(
            f"- No clear diminishing returns detected within the tested range "
            f"(threshold: {DIMINISHING_RETURNS_THRESHOLD})"
        )

    if optimal is not None:
        lines.append(f"- Optimal dispatch count: {optimal['agent_count']} (best cost/finding ratio)")
    else:
        lines.append("- Optimal dispatch count: undetermined (no unique findings recorded)")

    if max_useful is not None:
        lines.append(f"- Maximum useful agents: {max_useful} (marginal value approaches zero beyond this)")
    else:
        lines.append("- Maximum useful agents: undetermined")

    return "\n".join(lines) + "\n"


def format_markdown(rows: list[dict], task: str, agent_type: str) -> str:
    """Format analysis as a markdown report.

    Args:
        rows: Sorted list of per-run metric dicts.
        task: Original task prompt from results.json.
        agent_type: Agent type from results.json.

    Returns:
        Full markdown report string.
    """
    lines: list[str] = [
        "# Dispatch Scaling Analysis",
        "",
        f"**Task:** {task}  ",
        f"**Agent type:** {agent_type}",
        "",
        "## Results by Agent Count",
        "",
        "| Agents | Wall Clock (s) | Total Tokens | Unique Findings | Marginal Findings | Cost/Finding |",
        "|--------|---------------|--------------|-----------------|-------------------|--------------|",
    ]

    for row in rows:
        lines.append(
            f"| {row['agent_count']} "
            f"| {row['wall_clock_seconds']:.1f} "
            f"| {row['total_tokens']} "
            f"| {row['unique_findings']} "
            f"| {row['marginal_findings']} "
            f"| {row['cost_per_finding']} |"
        )

    lines.append("")
    lines.append(_scaling_summary(rows))
    return "\n".join(lines)


def format_json(rows: list[dict]) -> str:
    """Format analysis rows as a JSON array.

    Args:
        rows: Sorted list of per-run metric dicts.

    Returns:
        JSON string.
    """
    return json.dumps(rows, indent=2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser."""
    parser = argparse.ArgumentParser(
        prog="dispatch-scaling-analyzer.py",
        description="Analyze dispatch scaling results from dispatch-scaling-runner.py (ADR-178).",
    )
    parser.add_argument(
        "--results",
        default=None,
        metavar="PATH",
        help=f"Path to results.json (default: {DEFAULT_RESULTS}).",
    )
    parser.add_argument(
        "--json",
        dest="output_json",
        action="store_true",
        default=False,
        help="Output as JSON instead of markdown report.",
    )
    return parser


def main() -> int:
    """Entry point — load results, compute metrics, print report."""
    parser = _build_parser()
    args = parser.parse_args()

    results_path = Path(args.results) if args.results else DEFAULT_RESULTS
    data = load_results(results_path)
    results_dir = results_path.parent

    rows = compute_metrics(data, results_dir)

    if args.output_json:
        print(format_json(rows))
    else:
        print(format_markdown(rows, task=data.get("task", ""), agent_type=data.get("agent_type", "")))

    return 0


if __name__ == "__main__":
    sys.exit(main())
