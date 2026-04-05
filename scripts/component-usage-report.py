#!/usr/bin/env python3
"""
Component Usage Report — ADR-174 experiment infrastructure.

Queries usage.db for skill and agent invocation counts, cross-references
against agents/INDEX.json and skills/INDEX.json, and outputs a ranked table
of all components by usage.

Usage:
    python3 scripts/component-usage-report.py
    python3 scripts/component-usage-report.py --top 10
    python3 scripts/component-usage-report.py --dead-only
    python3 scripts/component-usage-report.py --json
    python3 scripts/component-usage-report.py --usage-db /path/to/usage.db

Exit codes:
    0 = success
    1 = usage.db not found or other fatal error
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_USAGE_DB = Path.home() / ".claude" / "usage.db"
REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_index_components(index_path: Path, key: str) -> list[str]:
    """Load component names from an INDEX.json file.

    Args:
        index_path: Path to the INDEX.json file.
        key: Top-level dict key containing the component map (e.g. 'agents' or 'skills').

    Returns:
        Sorted list of component names.
    """
    if not index_path.exists():
        return []
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
        return sorted(data.get(key, {}).keys())
    except (json.JSONDecodeError, AttributeError):
        return []


def query_usage(db_path: Path) -> tuple[dict[str, int], dict[str, str], dict[str, int], dict[str, str]]:
    """Query usage.db for skill and agent invocation counts and last-used timestamps.

    Returns four dicts:
        skill_counts:      {skill_name: count}
        skill_last_used:   {skill_name: timestamp}
        agent_counts:      {agent_name: count}
        agent_last_used:   {agent_name: timestamp}

    If a table doesn't exist, returns empty dicts for that component type.
    """
    skill_counts: dict[str, int] = {}
    skill_last_used: dict[str, str] = {}
    agent_counts: dict[str, int] = {}
    agent_last_used: dict[str, str] = {}

    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()

        # Check which tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in cursor.fetchall()}

        if "skill_invocations" in existing_tables:
            cursor.execute(
                "SELECT skill_name, COUNT(*) as cnt, MAX(timestamp) as last_ts "
                "FROM skill_invocations GROUP BY skill_name"
            )
            for row in cursor.fetchall():
                name, count, last_ts = row
                skill_counts[name] = count
                skill_last_used[name] = last_ts or ""

        if "agent_invocations" in existing_tables:
            cursor.execute(
                "SELECT agent_name, COUNT(*) as cnt, MAX(timestamp) as last_ts "
                "FROM agent_invocations GROUP BY agent_name"
            )
            for row in cursor.fetchall():
                name, count, last_ts = row
                agent_counts[name] = count
                agent_last_used[name] = last_ts or ""

    finally:
        conn.close()

    return skill_counts, skill_last_used, agent_counts, agent_last_used


# ---------------------------------------------------------------------------
# Report building
# ---------------------------------------------------------------------------


def build_report(
    db_path: Path,
    top_n: Optional[int],
    dead_only: bool,
) -> list[dict]:
    """Build a sorted list of component usage records.

    Args:
        db_path: Path to usage.db.
        top_n: If set, limit output to top N components.
        dead_only: If True, include only components with 0 invocations.

    Returns:
        List of dicts with keys: name, component_type, invocation_count, last_used.
    """
    agents = load_index_components(REPO_ROOT / "agents" / "INDEX.json", "agents")
    skills = load_index_components(REPO_ROOT / "skills" / "INDEX.json", "skills")

    skill_counts, skill_last_used, agent_counts, agent_last_used = query_usage(db_path)

    rows: list[dict] = []

    for name in skills:
        rows.append(
            {
                "name": name,
                "component_type": "skill",
                "invocation_count": skill_counts.get(name, 0),
                "last_used": skill_last_used.get(name, ""),
            }
        )

    for name in agents:
        rows.append(
            {
                "name": name,
                "component_type": "agent",
                "invocation_count": agent_counts.get(name, 0),
                "last_used": agent_last_used.get(name, ""),
            }
        )

    # Sort by invocation_count descending, then name ascending for stable order
    rows.sort(key=lambda r: (-r["invocation_count"], r["name"]))

    if dead_only:
        rows = [r for r in rows if r["invocation_count"] == 0]

    if top_n is not None:
        rows = rows[:top_n]

    return rows


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def format_markdown(rows: list[dict]) -> str:
    """Format rows as a markdown table.

    Args:
        rows: List of component usage records.

    Returns:
        Markdown table string.
    """
    if not rows:
        return "_No components found._\n"

    lines = [
        "| # | Name | Type | Invocations | Last Used |",
        "|---|------|------|-------------|-----------|",
    ]
    for rank, row in enumerate(rows, start=1):
        last_used = row["last_used"] or "never"
        lines.append(f"| {rank} | {row['name']} | {row['component_type']} | {row['invocation_count']} | {last_used} |")
    return "\n".join(lines) + "\n"


def format_json(rows: list[dict]) -> str:
    """Format rows as a JSON array.

    Args:
        rows: List of component usage records.

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
        prog="component-usage-report.py",
        description="Rank all toolkit components by invocation count from usage.db.",
    )
    parser.add_argument(
        "--top",
        metavar="N",
        type=int,
        default=None,
        help="Show only top-N components by invocation count.",
    )
    parser.add_argument(
        "--json",
        dest="output_json",
        action="store_true",
        default=False,
        help="Output as JSON instead of markdown table.",
    )
    parser.add_argument(
        "--dead-only",
        action="store_true",
        default=False,
        help="Show only components with 0 invocations (archive candidates).",
    )
    parser.add_argument(
        "--usage-db",
        metavar="PATH",
        default=None,
        help=f"Override default usage.db path (default: {DEFAULT_USAGE_DB}).",
    )
    return parser


def main() -> int:
    """Entry point — parse args, query DB, and print report."""
    parser = _build_parser()
    args = parser.parse_args()

    db_path = Path(args.usage_db) if args.usage_db else DEFAULT_USAGE_DB

    if not db_path.exists():
        print(f"error: usage.db not found at {db_path}", file=sys.stderr)
        print("hint: specify an alternate path with --usage-db PATH", file=sys.stderr)
        return 1

    rows = build_report(db_path, top_n=args.top, dead_only=args.dead_only)

    if args.output_json:
        print(format_json(rows))
    else:
        print(format_markdown(rows))

    return 0


if __name__ == "__main__":
    sys.exit(main())
