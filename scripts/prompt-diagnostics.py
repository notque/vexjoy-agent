#!/usr/bin/env python3
"""Read-only closed-loop prompt diagnostics from learning.db.

Summarizes intent drift by (runtime, model, effort), top alignment issues and
signals, handoff spec health, and deterministic recommendations. Never writes
to the database and exits 0 even when the database is missing or empty.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

HOOKS_LIB = Path(__file__).resolve().parent.parent / "hooks" / "lib"
if str(HOOKS_LIB) not in sys.path:
    sys.path.insert(0, str(HOOKS_LIB))

try:
    from learning_db_v2 import get_db_dir as _get_db_dir
except Exception:  # pragma: no cover - fallback when hooks/lib is absent
    _get_db_dir = None

EXPECTED_RUNTIMES = ("claude", "codex", "antigravity")
MIN_COHORT_MEASURED = 5
MIN_CLARIFICATION_JUDGMENTS = 5
CLARIFICATION_RATE_THRESHOLD = 0.25
LOW_SPEC_SCORE_THRESHOLD = 5
TOP_ISSUES_LIMIT = 10
TOP_MISSING_LIMIT = 10


def default_db_path() -> Path:
    """Return the default learning.db path without creating directories or files."""
    if _get_db_dir is not None:
        return Path(_get_db_dir()) / "learning.db"
    env_dir = os.environ.get("CLAUDE_LEARNING_DIR")
    base = Path(env_dir) if env_dir else Path.home() / ".claude" / "learning"
    return base / "learning.db"


def _connect_readonly(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True, timeout=5.0)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _window_modifier(days: float) -> str:
    clamped = max(0.0, float(days))
    return f"-{int(clamped * 86400)} seconds"


def _query_alignment_data(conn: sqlite3.Connection, window: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    empty_summary: dict[str, Any] = {
        "total_judgments": 0,
        "measured_judgments": 0,
        "signals": {
            "materially_differs": 0,
            "route_mismatch": 0,
            "clarification_needed": 0,
            "clarification_rate": None,
        },
        "alignment_statuses": {},
        "top_issues": [],
    }
    if not _table_exists(conn, "jev_intent_alignments"):
        return [], empty_summary

    cohort_rows = conn.execute(
        "SELECT agent_runtime, agent_model, agent_effort, "
        "COUNT(*) AS judgments, "
        "COUNT(materially_differs) AS measured, "
        "SUM(CASE WHEN materially_differs = 1 THEN 1 ELSE 0 END) AS material_differences, "
        "SUM(CASE WHEN alignment = 'review' THEN 1 ELSE 0 END) AS reviews, "
        "SUM(CASE WHEN route_mismatch = 1 THEN 1 ELSE 0 END) AS route_mismatches, "
        "SUM(CASE WHEN clarification_needed = 1 THEN 1 ELSE 0 END) AS clarifications "
        "FROM jev_intent_alignments "
        "WHERE phase = 'proposed' AND julianday(ts) >= julianday('now', ?) "
        "GROUP BY agent_runtime, agent_model, agent_effort "
        "ORDER BY judgments DESC, agent_runtime, agent_model, agent_effort",
        (window,),
    ).fetchall()

    cohorts: list[dict[str, Any]] = []
    for row in cohort_rows:
        measured = int(row["measured"] or 0)
        diffs = int(row["material_differences"] or 0)
        drift_rate = diffs / measured if measured > 0 else None
        cohorts.append(
            {
                "runtime": row["agent_runtime"],
                "agent_model": row["agent_model"],
                "agent_effort": row["agent_effort"],
                "judgments": int(row["judgments"] or 0),
                "measured": measured,
                "material_differences": diffs,
                "drift_rate": round(drift_rate, 4) if drift_rate is not None else None,
                "reviews": int(row["reviews"] or 0),
                "route_mismatches": int(row["route_mismatches"] or 0),
                "clarifications": int(row["clarifications"] or 0),
            }
        )

    detail_rows = conn.execute(
        "SELECT alignment, materially_differs, route_mismatch, clarification_needed, issues_json "
        "FROM jev_intent_alignments "
        "WHERE phase = 'proposed' AND julianday(ts) >= julianday('now', ?)",
        (window,),
    ).fetchall()

    total_judgments = len(detail_rows)
    measured_judgments = 0
    materially_differs_count = 0
    route_mismatch_count = 0
    clarification_count = 0
    status_counter: Counter[str] = Counter()
    issue_counter: Counter[str] = Counter()

    for row in detail_rows:
        status = str(row["alignment"] or "unknown")
        status_counter[status] += 1
        if row["materially_differs"] is not None:
            measured_judgments += 1
            if int(row["materially_differs"]) == 1:
                materially_differs_count += 1
        if row["route_mismatch"] == 1:
            route_mismatch_count += 1
        if row["clarification_needed"] == 1:
            clarification_count += 1
        raw_issues = row["issues_json"]
        if isinstance(raw_issues, str) and raw_issues.strip():
            try:
                parsed = json.loads(raw_issues)
            except json.JSONDecodeError:
                parsed = []
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, str) and item.strip():
                        issue_counter[item.strip()] += 1

    clarification_rate = round(clarification_count / total_judgments, 4) if total_judgments > 0 else None
    alignment_statuses = dict(sorted(status_counter.items(), key=lambda kv: (-kv[1], kv[0])))
    top_issues = [
        {"issue": issue, "count": count}
        for issue, count in sorted(issue_counter.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_ISSUES_LIMIT]
    ]

    summary = {
        "total_judgments": total_judgments,
        "measured_judgments": measured_judgments,
        "signals": {
            "materially_differs": materially_differs_count,
            "route_mismatch": route_mismatch_count,
            "clarification_needed": clarification_count,
            "clarification_rate": clarification_rate,
        },
        "alignment_statuses": alignment_statuses,
        "top_issues": top_issues,
    }
    return cohorts, summary


def _query_handoff_health(conn: sqlite3.Connection, window: str) -> dict[str, Any]:
    empty: dict[str, Any] = {
        "scored_dispatches": 0,
        "low_spec_count": 0,
        "low_spec_rate": None,
        "top_missing_labels": [],
        "outcome_basis_counts": {},
    }
    if not _table_exists(conn, "evidence_route_decisions"):
        return empty

    columns = {row["name"] for row in conn.execute("PRAGMA table_info(evidence_route_decisions)").fetchall()}
    has_spec = {"spec_score", "spec_missing", "created_at", "agent"}.issubset(columns)
    has_outcome_basis = {"outcome_basis", "created_at"}.issubset(columns)

    scored_dispatches = 0
    low_spec_count = 0
    missing_label_counter: Counter[str] = Counter()

    if has_spec:
        spec_rows = conn.execute(
            "SELECT spec_score, spec_missing "
            "FROM evidence_route_decisions "
            "WHERE spec_score IS NOT NULL AND agent != 'main' AND julianday(created_at) >= julianday('now', ?)",
            (window,),
        ).fetchall()
        scored_dispatches = len(spec_rows)
        for row in spec_rows:
            score = int(row["spec_score"])
            if score < LOW_SPEC_SCORE_THRESHOLD:
                low_spec_count += 1
            raw_missing = row["spec_missing"]
            if isinstance(raw_missing, str) and raw_missing.strip():
                for part in raw_missing.split(","):
                    label = part.strip()
                    if label:
                        missing_label_counter[label] += 1

    outcome_basis_counts: dict[str, int] = {}
    if has_outcome_basis:
        basis_rows = conn.execute(
            "SELECT outcome_basis, COUNT(*) AS cnt "
            "FROM evidence_route_decisions "
            "WHERE outcome_basis IS NOT NULL AND outcome_basis != '' AND julianday(created_at) >= julianday('now', ?) "
            "GROUP BY outcome_basis "
            "ORDER BY cnt DESC, outcome_basis",
            (window,),
        ).fetchall()
        outcome_basis_counts = {str(row["outcome_basis"]): int(row["cnt"]) for row in basis_rows}

    low_spec_rate = round(low_spec_count / scored_dispatches, 4) if scored_dispatches > 0 else None
    top_missing_labels = [
        {"label": label, "count": count}
        for label, count in sorted(missing_label_counter.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_MISSING_LIMIT]
    ]

    return {
        "scored_dispatches": scored_dispatches,
        "low_spec_count": low_spec_count,
        "low_spec_rate": low_spec_rate,
        "top_missing_labels": top_missing_labels,
        "outcome_basis_counts": outcome_basis_counts,
    }


def build_recommendations(
    cohorts: list[dict[str, Any]],
    alignment_summary: dict[str, Any],
    handoff_health: dict[str, Any],
    *,
    drift_threshold: float,
) -> list[dict[str, str]]:
    """Produce deterministic recommendations from aggregated diagnostics."""
    recs: list[dict[str, str]] = []

    for cohort in cohorts:
        measured = cohort["measured"]
        drift_rate = cohort["drift_rate"]
        if measured >= MIN_COHORT_MEASURED and drift_rate is not None and drift_rate >= drift_threshold:
            rt = cohort["runtime"] or "unknown"
            model = cohort["agent_model"] or "unknown"
            effort = cohort["agent_effort"] or "default"
            recs.append(
                {
                    "code": "high_drift_cohort",
                    "severity": "high",
                    "message": (
                        f"High intent drift on ({rt}, {model}, {effort}): "
                        f"{drift_rate:.1%} ({cohort['material_differences']}/{measured} measured >= {drift_threshold:.0%}). "
                        "Use /d or --strict-scope, or raise effort."
                    ),
                }
            )

    total_judgments = alignment_summary["total_judgments"]
    if total_judgments > 0:
        seen_runtimes = {
            (cohort["runtime"] or "").strip().lower()
            for cohort in cohorts
            if cohort["judgments"] > 0 and cohort["runtime"]
        }
        missing_runtimes = [rt for rt in EXPECTED_RUNTIMES if rt not in seen_runtimes]
        if missing_runtimes:
            joined = ", ".join(missing_runtimes)
            recs.append(
                {
                    "code": "missing_runtime_coverage",
                    "severity": "info",
                    "message": (
                        f"Missing runtime telemetry coverage for: {joined} (0 judgments in window). "
                        "Verify runtime attribution in jev_intent_align.py."
                    ),
                }
            )

    signals = alignment_summary["signals"]
    clarification_rate = signals["clarification_rate"]
    if (
        total_judgments >= MIN_CLARIFICATION_JUDGMENTS
        and clarification_rate is not None
        and clarification_rate >= CLARIFICATION_RATE_THRESHOLD
    ):
        recs.append(
            {
                "code": "high_clarification_rate",
                "severity": "medium",
                "message": (
                    f"High clarification rate: {clarification_rate:.1%} "
                    f"({signals['clarification_needed']}/{total_judgments} judgments >= {CLARIFICATION_RATE_THRESHOLD:.0%}). "
                    "Run /prompt one-turn compiler before dispatch."
                ),
            }
        )

    scored = handoff_health["scored_dispatches"]
    low_spec = handoff_health["low_spec_count"]
    if scored > 0 and low_spec > 0:
        top_labels = ", ".join(item["label"] for item in handoff_health["top_missing_labels"][:3])
        missing_note = f" Top missing: {top_labels}." if top_labels else ""
        recs.append(
            {
                "code": "low_handoff_spec",
                "severity": "medium",
                "message": (
                    f"{low_spec}/{scored} dispatches scored below {LOW_SPEC_SCORE_THRESHOLD}/7 on handoff spec."
                    f"{missing_note} Enforce pretool-dispatch-spec-gate and paste scripts/build-dispatch.py output verbatim."
                ),
            }
        )

    return recs


def collect_diagnostics(db_path: Path, *, days: float = 30.0, drift_threshold: float = 0.20) -> dict[str, Any]:
    """Read telemetry from db_path (read-only) and return the diagnostics payload."""
    empty_alignment: dict[str, Any] = {
        "total_judgments": 0,
        "measured_judgments": 0,
        "signals": {
            "materially_differs": 0,
            "route_mismatch": 0,
            "clarification_needed": 0,
            "clarification_rate": None,
        },
        "alignment_statuses": {},
        "top_issues": [],
    }
    empty_handoff: dict[str, Any] = {
        "scored_dispatches": 0,
        "low_spec_count": 0,
        "low_spec_rate": None,
        "top_missing_labels": [],
        "outcome_basis_counts": {},
    }

    if not db_path.is_file():
        return {
            "db_path": str(db_path),
            "db_exists": False,
            "window_days": days,
            "drift_threshold": drift_threshold,
            "cohorts": [],
            "alignment_summary": empty_alignment,
            "handoff_health": empty_handoff,
            "recommendations": [],
        }

    window = _window_modifier(days)
    try:
        conn = _connect_readonly(db_path)
    except sqlite3.Error:
        return {
            "db_path": str(db_path),
            "db_exists": False,
            "window_days": days,
            "drift_threshold": drift_threshold,
            "cohorts": [],
            "alignment_summary": empty_alignment,
            "handoff_health": empty_handoff,
            "recommendations": [],
        }

    try:
        cohorts, alignment_summary = _query_alignment_data(conn, window)
        handoff_health = _query_handoff_health(conn, window)
    finally:
        conn.close()

    recommendations = build_recommendations(
        cohorts,
        alignment_summary,
        handoff_health,
        drift_threshold=drift_threshold,
    )

    return {
        "db_path": str(db_path),
        "db_exists": True,
        "window_days": days,
        "drift_threshold": drift_threshold,
        "cohorts": cohorts,
        "alignment_summary": alignment_summary,
        "handoff_health": handoff_health,
        "recommendations": recommendations,
    }


def _pct(value: float | None) -> str:
    return "-" if value is None else f"{value:.1%}"


def format_report(report: dict[str, Any]) -> str:
    """Render a concise Dense-Complete human report."""
    if not report["db_exists"]:
        return f"No learning database found at {report['db_path']}; nothing to diagnose."

    alignment = report["alignment_summary"]
    handoff = report["handoff_health"]
    if alignment["total_judgments"] == 0 and handoff["scored_dispatches"] == 0:
        return f"No prompt alignment or handoff telemetry recorded in the last {report['window_days']:g} day(s)."

    lines: list[str] = [
        f"Prompt diagnostics (window={report['window_days']:g}d, drift_threshold={report['drift_threshold']:.0%})",
        "",
        "## Drift by (runtime, model, effort)",
    ]
    cohorts = report["cohorts"]
    if not cohorts:
        lines.append("  (no proposed-intent judgments in window)")
    else:
        lines.append("  runtime\tmodel\teffort\tjudgments\tmeasured\tdrift\trate\treviews\troute_mis\tclarify")
        for row in cohorts:
            lines.append(
                f"  {row['runtime'] or '-'}\t{row['agent_model'] or '-'}\t{row['agent_effort'] or '-'}\t"
                f"{row['judgments']}\t{row['measured']}\t{row['material_differences']}\t"
                f"{_pct(row['drift_rate'])}\t{row['reviews']}\t{row['route_mismatches']}\t{row['clarifications']}"
            )

    sig = alignment["signals"]
    lines.extend(
        [
            "",
            "## Alignment signals & top issues",
            (
                f"  judgments={alignment['total_judgments']} measured={alignment['measured_judgments']} "
                f"materially_differs={sig['materially_differs']} route_mismatch={sig['route_mismatch']} "
                f"clarification_needed={sig['clarification_needed']} ({_pct(sig['clarification_rate'])})"
            ),
        ]
    )
    if alignment["alignment_statuses"]:
        statuses = ", ".join(f"{k}={v}" for k, v in alignment["alignment_statuses"].items())
        lines.append(f"  statuses: {statuses}")
    if alignment["top_issues"]:
        lines.append("  top issues:")
        for item in alignment["top_issues"]:
            lines.append(f"    {item['count']:>4}  {item['issue']}")

    lines.extend(["", "## Handoff spec health"])
    if handoff["scored_dispatches"] == 0:
        lines.append("  (no scored handoff dispatches in window)")
    else:
        lines.append(
            f"  scored={handoff['scored_dispatches']} "
            f"low_spec(<{LOW_SPEC_SCORE_THRESHOLD})={handoff['low_spec_count']} ({_pct(handoff['low_spec_rate'])})"
        )
        if handoff["top_missing_labels"]:
            lines.append("  top missing labels:")
            for item in handoff["top_missing_labels"]:
                lines.append(f"    {item['count']:>4}  {item['label']}")
    if handoff["outcome_basis_counts"]:
        bases = ", ".join(f"{k}={v}" for k, v in handoff["outcome_basis_counts"].items())
        lines.append(f"  outcome_basis: {bases}")

    lines.extend(["", "## Recommendations"])
    recs = report["recommendations"]
    if not recs:
        lines.append("  None.")
    else:
        for rec in recs:
            lines.append(f"  - [{rec['severity']}] {rec['message']}")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only closed-loop prompt diagnostics from learning.db.")
    parser.add_argument("--days", type=float, default=30.0, help="Lookback window in days (default: 30.0)")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Emit machine-readable JSON")
    parser.add_argument("--db", type=Path, default=None, help="Path to SQLite learning.db (read-only)")
    parser.add_argument(
        "--drift-threshold",
        type=float,
        default=0.20,
        help="Drift rate threshold for flagging cohorts (default: 0.20)",
    )
    args = parser.parse_args(argv)

    db_path = args.db if args.db is not None else default_db_path()
    report = collect_diagnostics(db_path, days=args.days, drift_threshold=args.drift_threshold)
    if args.as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(format_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
