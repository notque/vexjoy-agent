#!/usr/bin/env python3
"""
Retro-knowledge impact analysis for ADR-176.

Queries learning.db session_stats table to compare error rates between
sessions that received retro-knowledge injection (had_retro_knowledge=1)
and those that did not (had_retro_knowledge=0).

Outputs a markdown table and a significance verdict.

Usage:
    python3 scripts/retro-impact-analysis.py
    python3 scripts/retro-impact-analysis.py --min-sessions 30
    python3 scripts/retro-impact-analysis.py --db /path/to/learning.db
    python3 scripts/retro-impact-analysis.py --json
"""

import argparse
import json
import math
import sqlite3
import sys
from pathlib import Path


def _default_db_path() -> Path:
    """Return default path to learning.db.

    Returns:
        Path to ~/.claude/learning.db.
    """
    return Path.home() / ".claude" / "learning.db"


def _compute_ci(p1: float, n1: int, p2: float, n2: int) -> tuple[float, float, float]:
    """Compute 95% confidence interval for difference in proportions (p1 - p2).

    Args:
        p1: Proportion for group 1.
        n1: Sample size for group 1.
        p2: Proportion for group 2.
        n2: Sample size for group 2.

    Returns:
        Tuple of (diff, lower_bound, upper_bound).
    """
    diff = p1 - p2
    se = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    margin = 1.96 * se
    return diff, diff - margin, diff + margin


def _query_cohorts(conn: sqlite3.Connection) -> dict:
    """Query session_stats table and return per-cohort aggregates.

    Args:
        conn: Open SQLite connection.

    Returns:
        Dict mapping had_retro_knowledge (0 or 1) to cohort stats dict.
    """
    cursor = conn.execute(
        """
        SELECT
            had_retro_knowledge,
            COUNT(*) AS session_count,
            AVG(errors_encountered) AS avg_errors_encountered,
            AVG(errors_resolved) AS avg_errors_resolved,
            SUM(errors_encountered) AS total_errors
        FROM session_stats
        GROUP BY had_retro_knowledge
        """
    )
    rows = cursor.fetchall()
    result = {}
    for row in rows:
        key = int(row[0])
        result[key] = {
            "session_count": int(row[1]),
            "avg_errors_encountered": float(row[2]) if row[2] is not None else 0.0,
            "avg_errors_resolved": float(row[3]) if row[3] is not None else 0.0,
            "total_errors": int(row[4]) if row[4] is not None else 0,
        }
    return result


def _build_report(cohorts: dict, min_sessions: int) -> dict:
    """Build the analysis report from cohort data.

    Args:
        cohorts: Dict from _query_cohorts.
        min_sessions: Minimum sessions per cohort for significance testing.

    Returns:
        Report dict with verdict, cohort stats, and confidence interval.
    """
    retro = cohorts.get(1, {"session_count": 0, "avg_errors_encountered": 0.0, "avg_errors_resolved": 0.0})
    control = cohorts.get(0, {"session_count": 0, "avg_errors_encountered": 0.0, "avg_errors_resolved": 0.0})

    n_retro = retro["session_count"]
    n_control = control["session_count"]

    if n_retro < min_sessions or n_control < min_sessions:
        verdict = "INSUFFICIENT DATA"
        ci_lower = ci_upper = diff = None
    else:
        # Error rate = avg errors per session (used as proportion proxy)
        p_retro = retro["avg_errors_encountered"]
        p_control = control["avg_errors_encountered"]

        # Clamp to [0, 1] for CI calculation (rates can exceed 1 in theory,
        # but the CI formula assumes proportions; we use it as an approximation)
        p_retro_clamped = min(max(p_retro, 0.0), 1.0)
        p_control_clamped = min(max(p_control, 0.0), 1.0)

        # Avoid division by zero with degenerate proportions
        if p_retro_clamped in (0.0, 1.0) and p_control_clamped in (0.0, 1.0):
            diff, ci_lower, ci_upper = p_retro - p_control, 0.0, 0.0
        else:
            diff, ci_lower, ci_upper = _compute_ci(p_retro_clamped, n_retro, p_control_clamped, n_control)

        # CI excludes 0 → significant
        if ci_lower > 0 or ci_upper < 0:
            direction = "retro higher" if diff > 0 else "retro lower"
            verdict = f"SIGNIFICANT ({direction})"
        else:
            verdict = "NOT SIGNIFICANT"

    return {
        "verdict": verdict,
        "retro": {
            "sessions": n_retro,
            "avg_errors_encountered": round(retro["avg_errors_encountered"], 4),
            "avg_errors_resolved": round(retro["avg_errors_resolved"], 4),
        },
        "control": {
            "sessions": n_control,
            "avg_errors_encountered": round(control["avg_errors_encountered"], 4),
            "avg_errors_resolved": round(control["avg_errors_resolved"], 4),
        },
        "diff": round(diff, 4) if diff is not None else None,
        "ci_95_lower": round(ci_lower, 4) if ci_lower is not None else None,
        "ci_95_upper": round(ci_upper, 4) if ci_upper is not None else None,
    }


def _print_markdown(report: dict) -> None:
    """Print analysis as a markdown table + verdict line.

    Args:
        report: Report dict from _build_report.
    """
    retro = report["retro"]
    control = report["control"]

    print("## Retro-Knowledge Impact Analysis\n")
    print("| Cohort | Sessions | Avg Errors Encountered | Avg Errors Resolved |")
    print("|--------|----------|----------------------|---------------------|")
    print(
        f"| Retro (treatment) | {retro['sessions']} "
        f"| {retro['avg_errors_encountered']} "
        f"| {retro['avg_errors_resolved']} |"
    )
    print(
        f"| Control | {control['sessions']} | {control['avg_errors_encountered']} | {control['avg_errors_resolved']} |"
    )

    if report["diff"] is not None:
        print(f"\nDiff (retro - control): {report['diff']}")
        print(f"95% CI: [{report['ci_95_lower']}, {report['ci_95_upper']}]")

    print(f"\n**Verdict: {report['verdict']}**")


def main(argv: list[str] | None = None) -> int:
    """Run the retro impact analysis CLI.

    Args:
        argv: Command-line arguments (defaults to sys.argv).

    Returns:
        Exit code (0 = success, 1 = error).
    """
    parser = argparse.ArgumentParser(description="Analyse retro-knowledge injection impact from learning.db.")
    parser.add_argument(
        "--min-sessions",
        type=int,
        default=20,
        metavar="N",
        help="Minimum sessions per cohort before reporting significance (default: 20).",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        metavar="PATH",
        help="Path to learning.db (default: ~/.claude/learning.db).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Output results as JSON.",
    )
    args = parser.parse_args(argv)

    db_path: Path = args.db if args.db is not None else _default_db_path()

    if not db_path.exists():
        print(f"Error: database not found at {db_path}", file=sys.stderr)
        return 1

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
    except sqlite3.Error as exc:
        print(f"Error: could not open database: {exc}", file=sys.stderr)
        return 1

    try:
        # Check table exists
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='session_stats'")
        if cursor.fetchone() is None:
            print("Error: session_stats table not found in database", file=sys.stderr)
            return 1

        cohorts = _query_cohorts(conn)
        report = _build_report(cohorts, args.min_sessions)
    except sqlite3.Error as exc:
        print(f"Error querying database: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()

    if args.as_json:
        print(json.dumps(report, indent=2))
    else:
        _print_markdown(report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
