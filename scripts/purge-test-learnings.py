#!/usr/bin/env python3
"""One-shot script to remove test-source entries from the production learning DB.

Dry-run by default: lists affected rows without deleting. Pass --commit to delete.

Usage:
    python3 scripts/purge-test-learnings.py
    python3 scripts/purge-test-learnings.py --commit
    python3 scripts/purge-test-learnings.py --db /path/to/learning.db
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path


def _default_db_path() -> Path:
    """Return the default production DB path, respecting CLAUDE_LEARNING_DIR."""
    import os

    env_dir = os.environ.get("CLAUDE_LEARNING_DIR")
    if env_dir:
        return Path(env_dir) / "learning.db"
    return Path.home() / ".claude" / "learning" / "learning.db"


def _query_test_rows(conn: sqlite3.Connection) -> list[dict]:
    """Return all rows whose source starts with 'test'."""
    cursor = conn.execute(
        """
        SELECT id, topic, key, source, category, confidence, first_seen
        FROM learnings
        WHERE source LIKE 'test%'
        ORDER BY source, topic, key
        """,
    )
    col_names = [col[0] for col in cursor.description]
    return [dict(zip(col_names, row)) for row in cursor.fetchall()]


def _print_summary(rows: list[dict]) -> None:
    """Print a human-readable table of rows that would be deleted."""
    if not rows:
        print("No test-source rows found.")
        return

    print(f"Test-source rows ({len(rows)} total):")
    print(f"{'Source':<20} {'Topic':<35} {'Key':<14} {'Category':<14} {'Conf':>5}")
    print("-" * 92)
    for r in rows:
        print(
            f"{r['source']:<20} {r['topic'][:34]:<35} {r['key'][:13]:<14} {r['category']:<14} {r['confidence']:>5.2f}"
        )
    print("-" * 92)

    by_source: dict[str, int] = {}
    for r in rows:
        by_source[r["source"]] = by_source.get(r["source"], 0) + 1
    print("By source:")
    for src, cnt in sorted(by_source.items(), key=lambda x: -x[1]):
        print(f"  {src}: {cnt}")


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Remove test-source entries from the learning DB (dry-run by default)."
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Actually delete the rows. Without this flag the script is read-only.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Path to learning.db (default: ~/.claude/learning/learning.db or $CLAUDE_LEARNING_DIR)",
    )
    args = parser.parse_args()

    db_path = args.db or _default_db_path()
    if not db_path.exists():
        print(f"Database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    rows = _query_test_rows(conn)
    _print_summary(rows)

    if not rows:
        conn.close()
        return

    if not args.commit:
        print()
        print("DRY RUN — no rows deleted.")
        print(f"Run with --commit to delete these {len(rows)} rows from {db_path}")
        conn.close()
        return

    # --commit: delete and report
    print()
    cursor = conn.execute("DELETE FROM learnings WHERE source LIKE 'test%'")
    deleted = cursor.rowcount
    conn.commit()
    conn.close()

    print(f"Deleted {deleted} test-source rows from {db_path}")


if __name__ == "__main__":
    main()
