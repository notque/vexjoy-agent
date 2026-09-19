#!/usr/bin/env python3
"""
aggregate_benchmark.py — Compute statistics across eval runs in an iteration workspace.

Reads grading.json from each eval directory. Computes mean, standard deviation, and
delta (with_skill minus without_skill) for pass_rate, time_seconds, and tokens.

Produces:
  {workspace}/benchmark.json   Machine-readable statistics
  {workspace}/benchmark.md     Human-readable summary
"""

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Aggregate benchmark statistics from eval grading results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("workspace", help="Path to iteration workspace directory (e.g. skill-workspace/iteration-1)")
    p.add_argument("--skill-name", required=True, help="Name of the skill being benchmarked")
    return p


def find_eval_dirs(workspace: Path) -> list[Path]:
    """Find all eval directories that contain grading.json."""
    eval_dirs = []
    for child in sorted(workspace.iterdir()):
        if child.is_dir() and (child / "grading.json").exists():
            eval_dirs.append(child)
    return eval_dirs


def load_grading(eval_dir: Path) -> dict | None:
    """Load grading.json from an eval directory."""
    grading_path = eval_dir / "grading.json"
    try:
        return json.loads(grading_path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        print(f"WARNING: Could not load {grading_path}: {e}", file=sys.stderr)
        return None


def load_timing(eval_dir: Path, configuration: str) -> dict:
    """Load timing.json for a given configuration (with_skill or without_skill)."""
    timing_path = eval_dir / configuration / "timing.json"
    try:
        return json.loads(timing_path.read_text())
    except (json.JSONDecodeError, OSError):
        return {"duration_seconds": 0.0, "tokens_total": 0}


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = mean(values)
    variance = sum((v - m) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)


def aggregate(workspace: Path, skill_name: str) -> dict:
    eval_dirs = find_eval_dirs(workspace)
    if not eval_dirs:
        print(f"ERROR: No eval directories with grading.json found in {workspace}", file=sys.stderr)
        sys.exit(1)

    with_skill_pass_rates = []
    without_skill_pass_rates = []
    with_skill_tokens = []
    without_skill_tokens = []
    with_skill_durations = []
    without_skill_durations = []

    eval_results = []

    for eval_dir in eval_dirs:
        grading = load_grading(eval_dir)
        if grading is None:
            continue

        config = grading.get("configuration")
        if config not in ("with_skill", "without_skill"):
            print(f"WARNING: {eval_dir.name}/grading.json missing 'configuration' field, skipping", file=sys.stderr)
            continue
        pass_rate = float(grading.get("pass_rate", 0.0))

        with_timing = load_timing(eval_dir, "with_skill")
        without_timing = load_timing(eval_dir, "without_skill")

        if config == "with_skill":
            with_skill_pass_rates.append(pass_rate)
            with_skill_tokens.append(float(with_timing.get("tokens_total", 0)))
            with_skill_durations.append(float(with_timing.get("duration_seconds", 0)))
        else:
            without_skill_pass_rates.append(pass_rate)
            without_skill_tokens.append(float(without_timing.get("tokens_total", 0)))
            without_skill_durations.append(float(without_timing.get("duration_seconds", 0)))

        # Try to load the paired configuration if this is with_skill grading
        # (eval dirs may contain only one grading.json; paired data comes from timing files)
        without_pass_rate = None
        paired_grading_path = eval_dir / "grading_without.json"
        if paired_grading_path.exists():
            try:
                paired = json.loads(paired_grading_path.read_text())
                without_pass_rate = float(paired.get("pass_rate", 0.0))
            except (json.JSONDecodeError, OSError):
                pass

        eval_results.append(
            {
                "eval_id": eval_dir.name,
                "configuration": config,
                "pass_rate": pass_rate,
                "pass_count": grading.get("pass_count", 0),
                "fail_count": grading.get("fail_count", 0),
                "without_skill_pass_rate": without_pass_rate,
                "with_skill_tokens": with_timing.get("tokens_total", 0),
                "with_skill_duration": with_timing.get("duration_seconds", 0),
                "without_skill_tokens": without_timing.get("tokens_total", 0),
                "without_skill_duration": without_timing.get("duration_seconds", 0),
            }
        )

    # Compute aggregates
    ws_mean = mean(with_skill_pass_rates)
    wos_mean = mean(without_skill_pass_rates)
    delta = ws_mean - wos_mean if with_skill_pass_rates and without_skill_pass_rates else None

    benchmark = {
        "skill_name": skill_name,
        "workspace": str(workspace),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "eval_count": len(eval_results),
        "with_skill": {
            "pass_rate": {
                "mean": round(ws_mean, 4),
                "stddev": round(stddev(with_skill_pass_rates), 4),
                "min": round(min(with_skill_pass_rates), 4) if with_skill_pass_rates else 0.0,
                "max": round(max(with_skill_pass_rates), 4) if with_skill_pass_rates else 0.0,
            },
            "tokens": {
                "mean": round(mean(with_skill_tokens), 1),
                "stddev": round(stddev(with_skill_tokens), 1),
            },
            "time_seconds": {
                "mean": round(mean(with_skill_durations), 2),
                "stddev": round(stddev(with_skill_durations), 2),
            },
        },
        "without_skill": {
            "pass_rate": {
                "mean": round(wos_mean, 4),
                "stddev": round(stddev(without_skill_pass_rates), 4),
                "min": round(min(without_skill_pass_rates), 4) if without_skill_pass_rates else 0.0,
                "max": round(max(without_skill_pass_rates), 4) if without_skill_pass_rates else 0.0,
            },
            "tokens": {
                "mean": round(mean(without_skill_tokens), 1),
                "stddev": round(stddev(without_skill_tokens), 1),
            },
            "time_seconds": {
                "mean": round(mean(without_skill_durations), 2),
                "stddev": round(stddev(without_skill_durations), 2),
            },
        },
        "delta": {
            "pass_rate": round(delta, 4) if delta is not None else None,
            "description": "with_skill minus without_skill; positive means skill helps",
        },
        "eval_results": eval_results,
    }

    return benchmark


def render_markdown(benchmark: dict) -> str:
    ws = benchmark["with_skill"]
    wos = benchmark["without_skill"]
    delta = benchmark["delta"]["pass_rate"]
    delta_str = f"+{delta:.1%}" if delta is not None and delta > 0 else (f"{delta:.1%}" if delta is not None else "N/A")

    lines = [
        f"# Benchmark: {benchmark['skill_name']}\n",
        f"**Generated**: {benchmark['timestamp']}  \n",
        f"**Evals**: {benchmark['eval_count']}\n\n",
        "## Pass Rate\n\n",
        "| Configuration | Mean | StdDev | Min | Max |\n",
        "|--------------|------|--------|-----|-----|\n",
        f"| with_skill   | {ws['pass_rate']['mean']:.1%} | {ws['pass_rate']['stddev']:.1%} | {ws['pass_rate']['min']:.1%} | {ws['pass_rate']['max']:.1%} |\n",
        f"| without_skill | {wos['pass_rate']['mean']:.1%} | {wos['pass_rate']['stddev']:.1%} | {wos['pass_rate']['min']:.1%} | {wos['pass_rate']['max']:.1%} |\n",
        f"| **delta** | **{delta_str}** | — | — | — |\n\n",
        "## Token Usage\n\n",
        "| Configuration | Mean Tokens | StdDev |\n",
        "|--------------|-------------|--------|\n",
        f"| with_skill   | {ws['tokens']['mean']:.0f} | {ws['tokens']['stddev']:.0f} |\n",
        f"| without_skill | {wos['tokens']['mean']:.0f} | {wos['tokens']['stddev']:.0f} |\n\n",
        "## Duration (seconds)\n\n",
        "| Configuration | Mean | StdDev |\n",
        "|--------------|------|--------|\n",
        f"| with_skill   | {ws['time_seconds']['mean']:.1f}s | {ws['time_seconds']['stddev']:.1f}s |\n",
        f"| without_skill | {wos['time_seconds']['mean']:.1f}s | {wos['time_seconds']['stddev']:.1f}s |\n\n",
        "## Per-Eval Results\n\n",
        "| Eval | Config | Pass Rate | Pass | Fail |\n",
        "|------|--------|-----------|------|------|\n",
    ]

    for er in benchmark["eval_results"]:
        lines.append(
            f"| {er['eval_id']} | {er['configuration']} | {er['pass_rate']:.1%} | {er['pass_count']} | {er['fail_count']} |\n"
        )

    return "".join(lines)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    workspace = Path(args.workspace).resolve()

    if not workspace.exists():
        print(f"ERROR: Workspace directory does not exist: {workspace}", file=sys.stderr)
        return 1

    benchmark = aggregate(workspace, args.skill_name)

    benchmark_json = workspace / "benchmark.json"
    benchmark_json.write_text(json.dumps(benchmark, indent=2))
    print(f"Written: {benchmark_json}", file=sys.stderr)

    benchmark_md = workspace / "benchmark.md"
    benchmark_md.write_text(render_markdown(benchmark))
    print(f"Written: {benchmark_md}", file=sys.stderr)

    delta = benchmark["delta"]["pass_rate"]
    if delta is not None:
        sign = "+" if delta > 0 else ""
        print(f"Pass rate delta: {sign}{delta:.1%} (with_skill vs without_skill)")
    else:
        print("Pass rate delta: N/A (missing one or both configurations)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
