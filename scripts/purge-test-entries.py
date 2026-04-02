#!/usr/bin/env python3
"""Purge test harness noise from the learning database.

Removes entries that are test scaffolding leftovers, not real learnings:
  - source = 'test'
  - topic IN ('test-confidence', 'test-bounds')
  - topic = 'unknown' AND value LIKE 'Test error for lookup%'

Real entries with topic='unknown' and non-test sources are preserved.

Usage:
    python3 scripts/purge-test-entries.py
    python3 scripts/purge-test-entries.py --db /path/to/learning.db
    python3 scripts/purge-test-entries.py --dry-run
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

_DELETE_SQL = """
    DELETE FROM learnings
    WHERE
        source = 'test'
        OR topic IN ('test-confidence', 'test-bounds')
        OR (topic = 'unknown' AND value LIKE 'Test error for lookup%')
"""

_COUNT_SQL = """
    SELECT COUNT(*) FROM learnings
    WHERE
        source = 'test'
        OR topic IN ('test-confidence', 'test-bounds')
        OR (topic = 'unknown' AND value LIKE 'Test error for lookup%')
"""

_TOTAL_SQL = "SELECT COUNT(*) FROM learnings"


def _default_db_path() -> Path:
    """Resolve learning.db from env or default location."""
    import os

    env_dir = os.environ.get("CLAUDE_LEARNING_DIR")
    if env_dir:
        return Path(env_dir) / "learning.db"
    return Path.home() / ".claude" / "learning" / "learning.db"


def purge_test_entries(db_path: Path, dry_run: bool) -> None:
    """Count and optionally delete test harness entries from learning.db.

    Args:
        db_path: Path to the SQLite learning database.
        dry_run: When True, reports counts without deleting.
    """
    if not db_path.exists():
        print(f"ERROR: database not found at {db_path}", file=sys.stderr)
        sys.exit(1)

    try:
        conn = sqlite3.connect(str(db_path), timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.Error as e:
        print(f"ERROR: cannot open database: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        total_before = conn.execute(_TOTAL_SQL).fetchone()[0]
        noise_count = conn.execute(_COUNT_SQL).fetchone()[0]

        if dry_run:
            print(f"[dry-run] Would purge {noise_count} of {total_before} entries.")
            print(f"[dry-run] Remaining after purge: {total_before - noise_count}")
            return

        conn.execute(_DELETE_SQL)
        conn.commit()

        total_after = conn.execute(_TOTAL_SQL).fetchone()[0]
        purged = total_before - total_after

        print(f"Purged {purged} of {total_before} entries. Remaining: {total_after}")

    except sqlite3.Error as e:
        print(f"ERROR: database operation failed: {e}", file=sys.stderr)
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Purge test harness noise from the learning database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--db",
        default=None,
        help="Path to learning.db (default: ~/.claude/learning/learning.db)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report counts without deleting anything.",
    )
    args = parser.parse_args()

    db_path = Path(args.db) if args.db else _default_db_path()
    purge_test_entries(db_path, dry_run=args.dry_run)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
