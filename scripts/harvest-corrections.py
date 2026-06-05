#!/usr/bin/env python3
"""Harvest user corrections from learning.db into a review digest.

ADR: correction-harvesting. Capture already exists
(`hooks/user-correction-capture.py` writes `topic="user-correction"` rows on
every UserPromptSubmit). Nothing read them back. This script closes the loop:
read correction rows + routing rows, cluster corrections by the domain inferred
from the routing row sharing the correction's session, and print a digest with
a suggested doc target and a one-line fix hint per cluster.

Report-only. It opens no PR and writes no DB column — the operator reads the
digest and applies the one-liner by hand (human-owns-definitions). Exit 0 when
the DB is readable; an empty digest is a valid result, not an error.

Cadence: run on demand, weekly by habit. To automate, point `/schedule` at:
    python3 scripts/harvest-corrections.py
with prompt "summarize clusters, suggest one-liners".

Usage:
    python3 scripts/harvest-corrections.py [--since-hours N] [--min-confidence C]
        [--format human|json] [--limit-examples K] [--db PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Insert repo hooks/lib so learning_db_v2 imports (sibling pattern,
# learning-db.py:42-51). Home lib first (lower priority), repo lib at pos 0.
_HOME_LIB = Path.home() / ".claude" / "hooks" / "lib"
if _HOME_LIB.is_dir():
    sys.path.insert(0, str(_HOME_LIB))
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "hooks" / "lib"))

from learning_db_v2 import get_db_path, query_learnings

UNATTRIBUTED = "unattributed"

# Fixed one-line fix hints per target type (not LLM-generated — the human writes
# the actual edit; this only points the way).
_FIX_HINT_SKILL = "tighten not_for / description so routing stops misfiring"
_FIX_HINT_AGENT = "tighten the agent scope boundary so routing stops misfiring"
_FIX_HINT_NONE = "no doc target — review manually"


def _parse_last_seen(value: str | None) -> datetime | None:
    """Parse a `last_seen` string (datetime('now') format) to a datetime."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _skill_file_from_index(skill: str, repo_root: Path) -> str | None:
    """Resolve a skill's doc path via skills/INDEX.json `file` field.

    Returns the INDEX `file` (normalized to forward slashes) or None when the
    INDEX is absent/unparseable or the skill has no entry. Caller falls back to
    a literal path when this returns None.
    """
    index = repo_root / "skills" / "INDEX.json"
    try:
        data = json.loads(index.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    entry = data.get("skills", {}).get(skill)
    if not isinstance(entry, dict):
        return None
    file_field = entry.get("file")
    if not file_field:
        return None
    return str(file_field).replace("\\", "/")


def _suggested(domain: str, repo_root: Path) -> tuple[str | None, str]:
    """Map a domain to (suggested_target, fix_hint).

    domain is "skill:<name>", "agent:<name>", or "unattributed".
    """
    if domain == UNATTRIBUTED:
        return None, _FIX_HINT_NONE
    kind, _, name = domain.partition(":")
    if kind == "skill" and name:
        target = _skill_file_from_index(name, repo_root) or f"skills/**/{name}/SKILL.md"
        return target, _FIX_HINT_SKILL
    if kind == "agent" and name:
        return f"agents/{name}.md", _FIX_HINT_AGENT
    return None, _FIX_HINT_NONE


def _domain_for_route(key: str) -> str:
    """Map a routing key 'agent:skill' to a digest domain.

    Skill present -> 'skill:<skill>' (the doc most likely to need the fix).
    Skill empty (agent-only route) -> 'agent:<agent>'.
    """
    agent, _, skill = key.partition(":")
    skill = skill.strip()
    if skill and skill != "-":
        return f"skill:{skill}"
    return f"agent:{agent}"


def build_digest(
    *,
    since_hours: int = 168,
    min_confidence: float = 0.65,
    limit_examples: int = 3,
    repo_root: Path | None = None,
) -> dict:
    """Read corrections + routes, cluster by session-joined domain, return digest.

    Pure read. Returns a dict with `generated`, `window_hours`, `min_confidence`,
    `total_corrections`, and `clusters` (sorted by count desc). Each cluster:
    `domain`, `count`, `suggested_target`, `suggested_fix`, `examples` (latest K
    correction snippets, newest first).
    """
    repo_root = repo_root or _REPO_ROOT
    cutoff = datetime.now() - timedelta(hours=since_hours)

    corrections = query_learnings(
        topic="user-correction",
        category="correction",
        min_confidence=min_confidence,
        limit=10000,
        exclude_graduated=False,
        exclude_test_sources=True,
    )
    routes = query_learnings(
        topic="routing",
        category="effectiveness",
        limit=10000,
        exclude_graduated=False,
        exclude_test_sources=True,
    )

    # Window filter on last_seen (in Python — the read API has no time filter).
    in_window = []
    for c in corrections:
        ts = _parse_last_seen(c.get("last_seen"))
        if ts is None or ts >= cutoff:
            in_window.append(c)

    # Latest route per session by last_seen.
    session_to_domain: dict[str, str] = {}
    session_route_ts: dict[str, datetime] = {}
    for r in routes:
        sid = r.get("session_id")
        if not sid:
            continue
        ts = _parse_last_seen(r.get("last_seen")) or datetime.min
        if sid not in session_route_ts or ts >= session_route_ts[sid]:
            session_route_ts[sid] = ts
            session_to_domain[sid] = _domain_for_route(r["key"])

    # Group corrections by inferred domain.
    grouped: dict[str, list[dict]] = {}
    for c in in_window:
        domain = session_to_domain.get(c.get("session_id"), UNATTRIBUTED)
        grouped.setdefault(domain, []).append(c)

    clusters = []
    for domain, rows in grouped.items():
        rows_sorted = sorted(
            rows,
            key=lambda r: _parse_last_seen(r.get("last_seen")) or datetime.min,
            reverse=True,
        )
        examples = [r["value"] for r in rows_sorted[:limit_examples]]
        target, fix_hint = _suggested(domain, repo_root)
        clusters.append(
            {
                "domain": domain,
                "count": len(rows),
                "suggested_target": target,
                "suggested_fix": fix_hint,
                "examples": examples,
            }
        )

    # Sort by count desc, then domain for stable ordering.
    clusters.sort(key=lambda c: (-c["count"], c["domain"]))

    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "window_hours": since_hours,
        "min_confidence": min_confidence,
        "total_corrections": len(in_window),
        "clusters": clusters,
    }


def _print_human(digest: dict) -> None:
    """Print the digest as a human-readable report."""
    if digest["total_corrections"] == 0:
        print(f"No corrections in window (last {digest['window_hours']}h).")
        return

    print(
        f"Correction digest — {digest['total_corrections']} corrections, "
        f"last {digest['window_hours']}h, {digest['generated']}"
    )
    print("-" * 60)
    for c in digest["clusters"]:
        kind, _, name = c["domain"].partition(":")
        label = f"{kind} {name}" if name else c["domain"]
        target = c["suggested_target"] or "(no doc target — review manually)"
        print(f"{label} drew {c['count']} correction(s) — target: {target}")
        print(f"  suggested fix: {c['suggested_fix']}")
        if c["examples"]:
            print("  latest:")
            for ex in c["examples"]:
                print(f'    - "{ex}"')
    print("-" * 60)
    print("These are clusters, not patches. Review each, then apply the one-liner by hand.")


def main(argv: list[str] | None = None) -> int:
    """CLI entry. Returns an exit code (0 always when the DB is readable)."""
    parser = argparse.ArgumentParser(description="Harvest user corrections into a review digest.")
    parser.add_argument("--since-hours", type=int, default=168, help="Window in hours (default 168 = 7d).")
    parser.add_argument("--min-confidence", type=float, default=0.65, help="Minimum correction confidence.")
    parser.add_argument("--format", choices=["human", "json"], default="human", help="Output format.")
    parser.add_argument("--limit-examples", type=int, default=3, help="Example snippets per cluster.")
    parser.add_argument("--db", default=None, help="learning.db path (default ~/.claude/learning/learning.db).")
    args = parser.parse_args(argv)

    if args.db:
        # Route the read API at an explicit DB by pointing its dir env at it.
        import os

        os.environ["CLAUDE_LEARNING_DIR"] = str(Path(args.db).expanduser().resolve().parent)
    else:
        # Touch get_db_path() so a missing dir surfaces here, not deep in a query.
        try:
            get_db_path()
        except OSError as exc:
            print(f"ERROR: cannot open learning.db: {exc}", file=sys.stderr)
            return 1

    try:
        digest = build_digest(
            since_hours=args.since_hours,
            min_confidence=args.min_confidence,
            limit_examples=args.limit_examples,
        )
    except Exception as exc:  # unreadable DB / bad args -> exit 1 per ADR
        print(f"ERROR: harvest failed: {exc}", file=sys.stderr)
        return 1

    if args.format == "json":
        print(json.dumps(digest, indent=2, default=str))
    else:
        _print_human(digest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
