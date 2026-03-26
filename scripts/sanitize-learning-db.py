#!/usr/bin/env python3
"""
Learning DB Sanitizer — Phase 4 of the security-threat-model skill.

Inspects the learning DB (learning_db_v2.py) for entries that may contain
injected content from external sources. Dry-run by default — use --purge
to actually delete flagged rows.

Flags entries where:
- key or value fields contain instruction-override or role-hijacking phrases
- source is pr_review, url, or external (high-risk origin)
- value contains zero-width Unicode or base64 blobs
- first_seen is older than 90 days and source indicates external origin

Output: security/learning-db-report.json

Usage:
    python3 scripts/sanitize-learning-db.py --output security/learning-db-report.json
    python3 scripts/sanitize-learning-db.py --output security/learning-db-report.json --purge
    python3 scripts/sanitize-learning-db.py --db /path/to/learning.db
    python3 scripts/sanitize-learning-db.py --help
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ─── Detection Patterns ────────────────────────────────────────

# High-risk source values
_HIGH_RISK_SOURCES: frozenset[str] = frozenset(["pr_review", "url", "external"])

# Stale external entry threshold (days)
_STALE_DAYS = 90

# Regex patterns applied to key/value fields
_INJECTION_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    (
        re.compile(r"\bdisregard\s+(all\s+)?(previous|above|prior)\b", re.IGNORECASE),
        "instruction-override",
        "Instruction disregard phrase in DB entry",
    ),
    (
        re.compile(r"\bforget\s+(all\s+)?your\s+instructions\b", re.IGNORECASE),
        "instruction-override",
        "Instruction-clearing phrase in DB entry",
    ),
    (
        re.compile(r"\byou\s+are\s+now\s+a\b", re.IGNORECASE),
        "role-hijacking",
        "Role-reassignment phrase in DB entry",
    ),
    (
        re.compile(r"\b(admin|developer|jailbreak)\s+mode\b", re.IGNORECASE),
        "role-hijacking",
        "Privileged mode phrase in DB entry",
    ),
    (
        re.compile(r"ANTHROPIC_BASE_URL", re.IGNORECASE),
        "base-url-override",
        "ANTHROPIC_BASE_URL found in DB entry",
    ),
]

# Invisible Unicode codepoints
_INVISIBLE_CODEPOINTS: frozenset[int] = frozenset(
    [
        0x200B,
        0x200C,
        0x200D,
        0x200E,
        0x200F,
        0x00AD,
        0x202A,
        0x202B,
        0x202C,
        0x202D,
        0x202E,
        0xFEFF,
        0x2060,
        0x2061,
        0x2062,
        0x2063,
        0x2064,
    ]
)


def _has_invisible_unicode(text: str) -> bool:
    return any(ord(c) in _INVISIBLE_CODEPOINTS for c in text)


def _has_base64_blob(text: str) -> bool:
    """Heuristic: look for base64-encoded blobs longer than 64 chars."""
    # Match patterns like base64, or standalone long base64 strings
    if "base64," in text.lower():
        return True
    # Look for long stretches of base64 chars (80+ chars)
    b64_pattern = re.compile(r"[A-Za-z0-9+/]{80,}={0,2}")
    return bool(b64_pattern.search(text))


def _is_stale_external(source: str, first_seen_str: str) -> bool:
    """Return True if entry is from an external source and older than _STALE_DAYS."""
    if source not in _HIGH_RISK_SOURCES:
        return False
    try:
        first_seen = datetime.fromisoformat(first_seen_str.replace("Z", "+00:00"))
        cutoff = datetime.now(timezone.utc) - timedelta(days=_STALE_DAYS)
        return first_seen < cutoff
    except Exception:
        return False


# ─── Inspection ────────────────────────────────────────────────


def _flag_row(row: sqlite3.Row) -> dict | None:
    """
    Inspect a single learning DB row. Returns a flagged entry dict or None.
    """
    row_id = row["id"]
    topic = row["topic"] or ""
    key = row["key"] or ""
    value = row["value"] or ""
    source = row["source"] or ""
    first_seen = row["first_seen"] or ""

    reasons: list[str] = []
    severity = "INFO"

    # 1. Injection patterns in key or value
    for pattern, category, description in _INJECTION_PATTERNS:
        if pattern.search(key) or pattern.search(value):
            reasons.append(f"[{category}] {description}")
            severity = "CRITICAL"

    # 2. High-risk source
    if source in _HIGH_RISK_SOURCES:
        reasons.append(f"[high-risk-source] source='{source}' is classified as high-risk")
        if severity == "INFO":
            severity = "WARNING"

    # 3. Invisible Unicode in value
    if _has_invisible_unicode(value):
        reasons.append("[invisible-unicode] zero-width or bidi Unicode in value field")
        severity = "CRITICAL"

    # 4. Base64 blob in value
    if _has_base64_blob(value):
        reasons.append("[base64-blob] potential encoded payload in value field")
        if severity == "INFO":
            severity = "WARNING"

    # 5. Stale external entry
    if _is_stale_external(source, first_seen):
        reasons.append(f"[stale-external] entry older than {_STALE_DAYS} days from external source")
        if severity == "INFO":
            severity = "WARNING"

    if not reasons:
        return None

    # Recommended action
    if severity == "CRITICAL":
        action = "purge"
    elif severity == "WARNING":
        action = "review"
    else:
        action = "keep"

    return {
        "id": row_id,
        "topic": topic,
        "key": key[:80],
        "source": source,
        "first_seen": first_seen,
        "severity": severity,
        "reasons": reasons,
        "action": action,
    }


def inspect_db(db_path: Path, verbose: bool) -> tuple[int, list[dict]]:
    """
    Inspect all rows in the learnings table. Returns (total_rows, flagged_entries).
    """
    if not db_path.exists():
        if verbose:
            print(f"  [sanitize] DB not found at {db_path} — returning empty report", file=sys.stderr)
        return 0, []

    try:
        conn = sqlite3.connect(str(db_path), timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.Error as e:
        print(f"[sanitize] ERROR: cannot open DB {db_path}: {e}", file=sys.stderr)
        return 0, []

    flagged: list[dict] = []
    total = 0

    try:
        rows = conn.execute("SELECT id, topic, key, value, source, source_detail, first_seen FROM learnings").fetchall()
        total = len(rows)
        for row in rows:
            entry = _flag_row(row)
            if entry:
                flagged.append(entry)
    except sqlite3.OperationalError as e:
        # Table doesn't exist yet — empty DB
        if verbose:
            print(f"  [sanitize] learnings table not found: {e}", file=sys.stderr)
        return 0, []
    finally:
        conn.close()

    return total, flagged


def purge_flagged(db_path: Path, flagged: list[dict], verbose: bool) -> int:
    """Delete flagged rows with action='purge'. Returns count deleted."""
    if not db_path.exists():
        return 0

    purge_ids = [e["id"] for e in flagged if e["action"] == "purge"]
    if not purge_ids:
        return 0

    try:
        conn = sqlite3.connect(str(db_path), timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executemany("DELETE FROM learnings WHERE id = ?", [(i,) for i in purge_ids])
        conn.commit()
        conn.close()
        if verbose:
            print(f"  [sanitize] Purged {len(purge_ids)} rows", file=sys.stderr)
        return len(purge_ids)
    except sqlite3.Error as e:
        print(f"[sanitize] ERROR during purge: {e}", file=sys.stderr)
        return 0


# ─── Main ──────────────────────────────────────────────────────


def _default_db_path() -> Path:
    env = Path(sys.argv[0]).parent  # just a sentinel
    import os

    env_dir = os.environ.get("CLAUDE_LEARNING_DIR")
    if env_dir:
        return Path(env_dir) / "learning.db"
    return Path.home() / ".claude" / "learning" / "learning.db"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect the learning DB for potentially injected entries.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--output",
        default="security/learning-db-report.json",
        help="Output path for learning-db-report.json (default: security/learning-db-report.json)",
    )
    parser.add_argument(
        "--db",
        default=None,
        help="Path to learning.db (default: ~/.claude/learning/learning.db or $CLAUDE_LEARNING_DIR)",
    )
    parser.add_argument(
        "--purge",
        action="store_true",
        help="Actually delete rows flagged with action=purge (default: dry-run only)",
    )
    parser.add_argument("--verbose", action="store_true", help="Print progress to stderr")
    args = parser.parse_args()

    db_path = Path(args.db) if args.db else _default_db_path()

    if args.verbose:
        print(f"[sanitize] DB path: {db_path}", file=sys.stderr)
        print(f"[sanitize] Purge mode: {args.purge}", file=sys.stderr)

    total, flagged = inspect_db(db_path, args.verbose)

    purged_count = 0
    if args.purge and flagged:
        purged_count = purge_flagged(db_path, flagged, args.verbose)

    critical = [e for e in flagged if e["severity"] == "CRITICAL"]
    warnings = [e for e in flagged if e["severity"] == "WARNING"]

    result = {
        "db_path": str(db_path),
        "db_exists": db_path.exists(),
        "total_entries": total,
        "flagged_count": len(flagged),
        "purged_count": purged_count,
        "dry_run": not args.purge,
        "flagged_entries": flagged,
        "summary": {
            "critical": len(critical),
            "warning": len(warnings),
            "purge_candidates": len([e for e in flagged if e["action"] == "purge"]),
            "review_candidates": len([e for e in flagged if e["action"] == "review"]),
        },
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(
        f"[sanitize] total={total} flagged={len(flagged)} CRITICAL={len(critical)} "
        f"WARNING={len(warnings)} purged={purged_count} dry_run={not args.purge}",
        file=sys.stderr,
    )
    print(f"[sanitize] Written to {output_path}", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as e:
        print(f"[sanitize] FATAL: {e}", file=sys.stderr)
        sys.exit(1)
