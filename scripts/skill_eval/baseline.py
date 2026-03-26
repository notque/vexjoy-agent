#!/usr/bin/env python3
"""Baseline management for pass@k regression tracking.

Reads a run_eval.py JSON output (or aggregate_benchmark.py benchmark.json)
and writes/diffs against .claude/evals/baseline.json.

Usage:
    # Write a new baseline from run_eval output
    python baseline.py write --input grading.json --skill my-skill

    # Diff current run against stored baseline
    python baseline.py diff --input grading.json --skill my-skill

    # Diff with custom threshold (default: 5pp = 0.05)
    python baseline.py diff --input grading.json --skill my-skill --threshold 0.10

Exit codes:
    0  No regressions (diff) or baseline written successfully (write)
    1  One or more regressions detected (diff only)
    2  Usage / file error
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def find_project_root() -> Path:
    """Walk up from cwd looking for .claude/ directory."""
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / ".claude").is_dir():
            return parent
    return current


def _default_baseline_path() -> Path:
    return find_project_root() / ".claude" / "evals" / "baseline.json"


def _passk_from_input(data: dict) -> dict[str, float]:
    """Extract pass@k and pass^k from run_eval.py JSON output.

    Supports both:
    - Direct run_eval.py output with a top-level "results" list
    - benchmark.json with "run_summary" (aggregate_benchmark.py output)
    """
    # run_eval.py output: {"skill_name": ..., "results": [...]}
    if "results" in data and isinstance(data["results"], list):
        run_vectors = []
        for r in data["results"]:
            rv = r.get("run_vector")
            if rv is not None:
                run_vectors.append(rv)
            else:
                # Backward compat: treat triggered bool as single-element vector
                triggered = r.get("triggers", 0) > 0
                run_vectors.append([triggered])

        if not run_vectors:
            return {"pass_at_k": 0.0, "pass_all_k": 0.0, "k": 0}

        k = max(len(v) for v in run_vectors)
        n = len(run_vectors)
        pass_at_count = sum(1 for v in run_vectors if any(v))
        pass_all_count = sum(1 for v in run_vectors if all(v))
        return {
            "pass_at_k": round(pass_at_count / n, 4),
            "pass_all_k": round(pass_all_count / n, 4),
            "k": k,
        }

    # aggregate_benchmark.py output: {"run_summary": {...}}
    if "run_summary" in data:
        summary = data["run_summary"]
        # Use the first non-delta config
        for config_name, config_data in summary.items():
            if config_name == "delta":
                continue
            return {
                "pass_at_k": config_data.get("pass_at_k", 0.0),
                "pass_all_k": config_data.get("pass_all_k", 0.0),
                "k": config_data.get("k", 0),
            }

    return {"pass_at_k": 0.0, "pass_all_k": 0.0, "k": 0}


def load_baseline(baseline_path: Path) -> dict:
    """Load existing baseline.json, returning empty dict if not found."""
    if not baseline_path.exists():
        return {}
    try:
        return json.loads(baseline_path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        print(f"Warning: could not read baseline at {baseline_path}: {e}", file=sys.stderr)
        return {}


def write_baseline(
    skill_name: str,
    metrics: dict,
    input_path: Path,
    baseline_path: Path,
) -> None:
    """Write or update baseline.json with metrics for the given skill."""
    baseline = load_baseline(baseline_path)

    baseline[skill_name] = {
        "pass_at_k": metrics["pass_at_k"],
        "pass_all_k": metrics["pass_all_k"],
        "k": metrics["k"],
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": str(input_path),
    }

    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text(json.dumps(baseline, indent=2) + "\n")
    print(f"Baseline written: {baseline_path}")
    print(
        f"  {skill_name}: pass@{metrics['k']}={metrics['pass_at_k']:.4f}"
        f"  pass^{metrics['k']}={metrics['pass_all_k']:.4f}"
    )


def diff_baseline(
    skill_name: str,
    current: dict,
    baseline_path: Path,
    threshold: float,
) -> bool:
    """Diff current metrics against stored baseline.

    Returns True if any regressions were found (pass@k decreased > threshold).
    """
    baseline = load_baseline(baseline_path)

    if not baseline:
        print(f"No baseline found at {baseline_path}. Run 'write' first.", file=sys.stderr)
        return False

    if skill_name not in baseline:
        print(f"Skill '{skill_name}' not in baseline. Run 'write' first.", file=sys.stderr)
        return False

    stored = baseline[skill_name]
    regressions = []

    for metric in ("pass_at_k", "pass_all_k"):
        stored_val = stored.get(metric, 0.0)
        current_val = current.get(metric, 0.0)
        drop = stored_val - current_val
        if drop > threshold:
            regressions.append(
                {
                    "metric": metric,
                    "baseline": stored_val,
                    "current": current_val,
                    "drop": drop,
                }
            )

    k = current.get("k", stored.get("k", 0))

    if regressions:
        print(f"REGRESSION detected for '{skill_name}' (threshold={threshold:.0%}):")
        for r in regressions:
            print(
                f"  {r['metric']}: {r['baseline']:.4f} -> {r['current']:.4f}  (drop={r['drop']:.4f}, >{threshold:.0%})"
            )
        return True

    # No regression
    pat = current.get("pass_at_k", 0.0)
    pak = current.get("pass_all_k", 0.0)
    print(f"OK '{skill_name}': pass@{k}={pat:.4f}  pass^{k}={pak:.4f}  (no regression)")
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Write or diff pass@k baselines for skill evals")
    sub = parser.add_subparsers(dest="command", required=True)

    # write subcommand
    write_p = sub.add_parser("write", help="Write current metrics to baseline.json")
    write_p.add_argument("--input", required=True, type=Path, help="Path to run_eval.py JSON output or benchmark.json")
    write_p.add_argument("--skill", required=True, help="Skill name to record in baseline")
    write_p.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help="Path to baseline.json (default: .claude/evals/baseline.json)",
    )

    # diff subcommand
    diff_p = sub.add_parser("diff", help="Diff current metrics against stored baseline")
    diff_p.add_argument("--input", required=True, type=Path, help="Path to run_eval.py JSON output or benchmark.json")
    diff_p.add_argument("--skill", required=True, help="Skill name to compare")
    diff_p.add_argument(
        "--threshold",
        type=float,
        default=0.05,
        help="Regression threshold as a fraction (default: 0.05 = 5pp)",
    )
    diff_p.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help="Path to baseline.json (default: .claude/evals/baseline.json)",
    )

    args = parser.parse_args()

    # Resolve baseline path
    baseline_path = args.baseline or _default_baseline_path()

    # Load input
    if not args.input.exists():
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        sys.exit(2)

    try:
        data = json.loads(args.input.read_text())
    except (json.JSONDecodeError, OSError) as e:
        print(f"Error: could not read {args.input}: {e}", file=sys.stderr)
        sys.exit(2)

    metrics = _passk_from_input(data)

    if args.command == "write":
        write_baseline(args.skill, metrics, args.input, baseline_path)
        sys.exit(0)

    elif args.command == "diff":
        regressed = diff_baseline(args.skill, metrics, baseline_path, args.threshold)
        sys.exit(1 if regressed else 0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(0)  # fail open
