#!/usr/bin/env python3
"""
Learning Database CLI — Deterministic operations on the unified knowledge store.

Usage:
    python3 scripts/learning-db.py learn --skill go-testing "insight text"
    python3 scripts/learning-db.py learn --agent golang-general-engineer "insight text"
    python3 scripts/learning-db.py record TOPIC KEY VALUE --category error
    python3 scripts/learning-db.py query --topic debugging --min-confidence 0.6
    python3 scripts/learning-db.py stats
    python3 scripts/learning-db.py purge --topic worktree-branches
    python3 scripts/learning-db.py export --format l1
    python3 scripts/learning-db.py export --format l2 --output-dir /tmp/learnings
    python3 scripts/learning-db.py import --from-retro ~/.claude/retro
    python3 scripts/learning-db.py import --from-patterns ~/.claude/learning/patterns.db
    python3 scripts/learning-db.py graduate TOPIC KEY TARGET
    python3 scripts/learning-db.py boost TOPIC KEY [--delta 0.15]
    python3 scripts/learning-db.py prune --below-confidence 0.3 --older-than 90
    python3 scripts/learning-db.py stale [--min-age-days 30] [--json]
    python3 scripts/learning-db.py stale-prune --dry-run [--min-age-days 30]
    python3 scripts/learning-db.py stale-prune --confirm [--min-age-days 30]
    python3 scripts/learning-db.py migrate
    python3 scripts/learning-db.py record-activation TOPIC KEY --session SESSION_ID --outcome success
    python3 scripts/learning-db.py record-waste --session SESSION_ID --tokens 1500
    python3 scripts/learning-db.py record-session --session SESSION_ID --had-retro --failures 2 --waste-tokens 3000
    python3 scripts/learning-db.py roi [--json]
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Also check ~/.claude/hooks/lib for cross-repo usage (lower priority)
_home_lib = Path.home() / ".claude" / "hooks" / "lib"
if _home_lib.is_dir():
    sys.path.insert(0, str(_home_lib))

# Add repo hooks/lib AFTER home lib so repo copy takes priority (inserted at pos 0)
_repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_repo_root / "hooks" / "lib"))

from learning_db_v2 import (
    boost_confidence,
    decay_confidence,
    export_markdown,
    get_connection,
    get_db_path,
    get_stats,
    import_from_patterns_db,
    import_from_retro,
    init_db,
    mark_graduated,
    prune,
    query_learnings,
    record_learning,
    search_learnings,
)


def cmd_record(args):
    result = record_learning(
        topic=args.topic,
        key=args.key,
        value=args.value,
        category=args.category,
        confidence=args.confidence,
        tags=args.tags.split(",") if args.tags else None,
        source=args.source or "manual:cli",
        source_detail=args.source_detail,
        project_path=args.project_path,
    )
    action = "Updated" if not result["is_new"] else "Recorded"
    print(
        f"{action}: [{result['category']}] {result['topic']}/{result['key']} "
        f"(confidence: {result['confidence']:.2f}, observations: {result['observation_count']})"
    )


def cmd_query(args):
    results = query_learnings(
        topic=args.topic,
        category=args.category,
        tags=args.tags.split(",") if args.tags else None,
        min_confidence=args.min_confidence,
        exclude_graduated=not args.include_graduated,
        order_by=args.order_by,
        limit=args.limit,
    )

    if args.format == "json":
        print(json.dumps(results, indent=2, default=str))
    else:
        if not results:
            print("No learnings found matching criteria.")
            return
        for r in results:
            grad = " [GRADUATED]" if r.get("graduated_to") else ""
            obs = f" [{r['observation_count']}x]" if r["observation_count"] > 1 else ""
            print(f"[{r['category']}] {r['topic']}/{r['key']}{obs}{grad}")
            print(f"  confidence: {r['confidence']:.2f} | source: {r['source']}")
            first_line = r["value"].split("\n")[0][:100]
            print(f"  {first_line}")
            print()


def cmd_search(args):
    results = search_learnings(
        args.query,
        min_confidence=args.min_confidence,
        exclude_graduated=not args.include_graduated,
        limit=args.limit,
    )

    if args.format == "json":
        print(json.dumps(results, indent=2, default=str))
    else:
        if not results:
            print("No learnings found matching query.")
            return
        for r in results:
            grad = " [GRADUATED]" if r.get("graduated_to") else ""
            obs = f" [{r['observation_count']}x]" if r["observation_count"] > 1 else ""
            rank = f" (rank: {r.get('rank', 0):.2f})" if r.get("rank") is not None else ""
            print(f"[{r['category']}] {r['topic']}/{r['key']}{obs}{grad}{rank}")
            print(f"  confidence: {r['confidence']:.2f} | source: {r['source']}")
            first_line = r["value"].split("\n")[0][:100]
            print(f"  {first_line}")
            print()


def cmd_stats(args):
    stats = get_stats()

    if args.format == "json":
        print(json.dumps(stats, indent=2))
        return

    print(f"Learning Database: {get_db_path()}")
    print(f"{'─' * 50}")
    print(f"Total learnings:      {stats['total_learnings']}")
    print(f"High confidence (≥0.7): {stats['high_confidence']}")
    print(f"Graduated:            {stats['graduated']}")
    print(f"Sessions tracked:     {stats['sessions_tracked']}")
    print(f"Learnings/session:    {stats['learnings_per_session']}")
    print()

    if stats["by_category"]:
        print("By Category:")
        for cat, cnt in sorted(stats["by_category"].items(), key=lambda x: -x[1]):
            print(f"  {cat:20s} {cnt}")
        print()

    if stats["by_topic"]:
        print("By Topic (top 20):")
        for topic, cnt in sorted(stats["by_topic"].items(), key=lambda x: -x[1]):
            print(f"  {topic:30s} {cnt}")


def cmd_export(args):
    output = export_markdown(fmt=args.format, output_dir=args.output_dir)
    print(output)


def cmd_import(args):
    if args.from_retro:
        result = import_from_retro(args.from_retro)
        print(f"Imported from retro: {result['imported']} entries, {result['skipped']} skipped")
    elif args.from_patterns:
        result = import_from_patterns_db(args.from_patterns)
        print(f"Imported from patterns.db: {result['imported']} entries, {result['skipped']} skipped")
    else:
        print("Specify --from-retro or --from-patterns")
        sys.exit(1)

    if result.get("errors"):
        print(f"Errors: {len(result['errors'])}")
        for e in result["errors"]:
            print(f"  - {e}")


def cmd_graduate(args):
    mark_graduated(args.topic, args.key, args.target)
    print(f"Graduated: {args.topic}/{args.key} → {args.target}")


def cmd_boost(args):
    new_conf = boost_confidence(args.topic, args.key, args.delta)
    print(f"Boosted: {args.topic}/{args.key} → confidence {new_conf:.2f}")


def cmd_decay(args):
    new_conf = decay_confidence(args.topic, args.key, args.delta)
    print(f"Decayed: {args.topic}/{args.key} → confidence {new_conf:.2f}")


def cmd_prune(args):
    """Remove low-confidence old entries (legacy destructive delete)."""
    count = prune(args.below_confidence, args.older_than)
    print(f"Pruned {count} entries (confidence < {args.below_confidence}, older than {args.older_than} days)")


def _query_stale_entries(conn: sqlite3.Connection, min_age_days: int) -> list[dict]:
    """Query entries matching staleness criteria.

    Staleness criteria:
    - Entry age > min_age_days (based on first_seen)
    - Confidence < 0.5
    - NOT graduated
    """
    cutoff = (datetime.now() - timedelta(days=min_age_days)).isoformat()
    rows = conn.execute(
        """
        SELECT id, topic, key, value, confidence, category,
               first_seen, last_seen, graduated_to
        FROM learnings
        WHERE first_seen < ?
          AND confidence < 0.5
          AND graduated_to IS NULL
        ORDER BY confidence ASC
        """,
        (cutoff,),
    ).fetchall()
    return [dict(row) for row in rows]


def _ensure_archive_table(conn: sqlite3.Connection) -> None:
    """Create the learning_archive table if it doesn't exist."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS learning_archive (
            id INTEGER PRIMARY KEY,
            topic TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            confidence REAL,
            category TEXT,
            created_at TEXT,
            updated_at TEXT,
            archived_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def cmd_stale(args):
    """Show entries that appear stale (old, low-confidence, not graduated)."""
    init_db()
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    entries = _query_stale_entries(conn, args.min_age_days)
    conn.close()

    if args.json:
        print(json.dumps(entries, indent=2, default=str))
        return

    if not entries:
        print(f"No stale entries found (age > {args.min_age_days} days, confidence < 0.5, not graduated).")
        return

    print(f"Stale entries ({len(entries)} found):")
    print(f"{'─' * 90}")
    print(f"{'Topic':<25} {'Key':<20} {'Conf':>6} {'Age':>6} {'Last Updated':<20}")
    print(f"{'─' * 90}")

    now = datetime.now()
    for entry in entries:
        first_seen = datetime.fromisoformat(entry["first_seen"]) if entry["first_seen"] else now
        age_days = (now - first_seen).days
        last_updated = entry["last_seen"] or entry["first_seen"] or "unknown"
        if last_updated != "unknown":
            last_updated = last_updated[:19]  # Trim to datetime precision

        topic_display = entry["topic"][:24]
        key_display = entry["key"][:19]
        print(f"{topic_display:<25} {key_display:<20} {entry['confidence']:>5.2f} {age_days:>5}d {last_updated:<20}")

    print(f"{'─' * 90}")
    print(f"Total: {len(entries)} stale entries")


def cmd_stale_prune(args):
    """Archive stale entries to learning_archive table."""
    init_db()
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    entries = _query_stale_entries(conn, args.min_age_days)

    if not entries:
        print(f"No stale entries to archive (age > {args.min_age_days} days, confidence < 0.5, not graduated).")
        conn.close()
        return

    if args.dry_run:
        print(f"DRY RUN: Would archive {len(entries)} stale entries:")
        print()
        now = datetime.now()
        for entry in entries:
            first_seen = datetime.fromisoformat(entry["first_seen"]) if entry["first_seen"] else now
            age_days = (now - first_seen).days
            print(f"  {entry['topic']}/{entry['key']} (confidence: {entry['confidence']:.2f}, age: {age_days}d)")
        print()
        print(f"Run with --confirm to archive these {len(entries)} entries.")
        conn.close()
        return

    # --confirm: actually archive
    _ensure_archive_table(conn)
    archived_at = datetime.now().isoformat()
    archived_count = 0

    for entry in entries:
        conn.execute(
            """
            INSERT INTO learning_archive (id, topic, key, value, confidence, category, created_at, updated_at, archived_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry["id"],
                entry["topic"],
                entry["key"],
                entry["value"],
                entry["confidence"],
                entry["category"],
                entry["first_seen"],
                entry["last_seen"],
                archived_at,
            ),
        )
        conn.execute("DELETE FROM learnings WHERE id = ?", (entry["id"],))
        archived_count += 1

    conn.commit()
    conn.close()
    print(f"Archived {archived_count} stale entries to learning_archive table.")


def cmd_record_activation(args: argparse.Namespace) -> None:
    """Record that a learning was activated during a session."""
    init_db()
    now = datetime.now().isoformat()
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO activations (topic, key, session_id, timestamp, outcome) VALUES (?, ?, ?, ?, ?)",
                (args.topic, args.key, args.session, now, args.outcome),
            )
            conn.commit()
    except sqlite3.Error as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Recorded activation: {args.topic}/{args.key} (session: {args.session}, outcome: {args.outcome})")


def cmd_record_waste(args: argparse.Namespace) -> None:
    """Record wasted tokens from a failure in a session.

    Increments failure_count by 1 and adds tokens to waste_tokens.
    Creates the session_stats row if it doesn't exist.
    """
    init_db()
    now = datetime.now().isoformat()
    try:
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO session_stats (session_id, failure_count, waste_tokens, created_at, had_retro_knowledge)
                   VALUES (?, 1, ?, ?, 0)
                   ON CONFLICT(session_id) DO UPDATE SET
                       failure_count = failure_count + 1,
                       waste_tokens = waste_tokens + excluded.waste_tokens""",
                (args.session, args.tokens, now),
            )
            conn.commit()
    except sqlite3.Error as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Recorded waste: session={args.session}, tokens={args.tokens}")


def cmd_record_session_stats(args: argparse.Namespace) -> None:
    """Create or update a session_stats entry.

    On conflict (existing session_id), overwrites had_retro_knowledge,
    failure_count, and waste_tokens with the provided values.
    """
    init_db()
    now = datetime.now().isoformat()
    had_retro = 1 if args.had_retro else 0

    try:
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO session_stats (session_id, had_retro_knowledge, failure_count, waste_tokens, created_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(session_id) DO UPDATE SET
                       had_retro_knowledge = excluded.had_retro_knowledge,
                       failure_count = excluded.failure_count,
                       waste_tokens = excluded.waste_tokens""",
                (args.session, had_retro, args.failures, args.waste_tokens, now),
            )
            conn.commit()
    except sqlite3.Error as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    print(
        f"Recorded session: {args.session} (retro={bool(had_retro)}, failures={args.failures}, waste={args.waste_tokens})"
    )


def _compute_roi_data(db_path: Path) -> dict:
    """Compute ROI metrics from the database.

    Returns a dict with all ROI data suitable for both human and JSON output.
    """
    with get_connection() as conn:
        # Session cohort stats
        total_sessions = conn.execute("SELECT COUNT(*) FROM session_stats").fetchone()[0]
        with_retro = conn.execute("SELECT COUNT(*) FROM session_stats WHERE had_retro_knowledge = 1").fetchone()[0]
        without_retro = conn.execute("SELECT COUNT(*) FROM session_stats WHERE had_retro_knowledge = 0").fetchone()[0]

        # Failure totals per cohort
        retro_failures_row = conn.execute(
            "SELECT COALESCE(SUM(failure_count), 0) FROM session_stats WHERE had_retro_knowledge = 1"
        ).fetchone()
        retro_failures = retro_failures_row[0]

        no_retro_failures_row = conn.execute(
            "SELECT COALESCE(SUM(failure_count), 0) FROM session_stats WHERE had_retro_knowledge = 0"
        ).fetchone()
        no_retro_failures = no_retro_failures_row[0]

        # Average waste tokens for non-retro cohort only (counterfactual baseline)
        avg_waste_row = conn.execute(
            "SELECT COALESCE(AVG(waste_tokens), 0) FROM session_stats WHERE had_retro_knowledge = 0"
        ).fetchone()
        avg_waste = avg_waste_row[0]

        # Top activated learnings
        top_activations = []
        for row in conn.execute(
            "SELECT topic, key, COUNT(*) as activation_count FROM activations GROUP BY topic, key ORDER BY activation_count DESC LIMIT 5"
        ).fetchall():
            top_activations.append({"topic": row["topic"], "key": row["key"], "count": row["activation_count"]})

        # Dead weight: learnings with 0 activations (ADR-032 requires 10+ total sessions)
        dead_weight: list[dict] = []
        if total_sessions >= 10:
            for row in conn.execute(
                """SELECT l.topic, l.key, l.first_seen
                   FROM learnings l
                   LEFT JOIN activations a ON l.topic = a.topic AND l.key = a.key
                   WHERE a.id IS NULL
                   ORDER BY l.first_seen ASC
                   LIMIT 10"""
            ).fetchall():
                age_days = -1
                if row["first_seen"]:
                    try:
                        first_seen_dt = datetime.fromisoformat(row["first_seen"])
                        age_days = (datetime.now() - first_seen_dt).days
                    except (ValueError, TypeError) as e:
                        print(f"Warning: cannot parse first_seen for {row['topic']}/{row['key']}: {e}", file=sys.stderr)
                        age_days = -1
                dead_weight.append({"topic": row["topic"], "key": row["key"], "age_days": age_days})

    # Compute rates and improvement
    sufficient_data = with_retro >= 3 and without_retro >= 3
    rate_with_retro = retro_failures / with_retro if with_retro > 0 else 0.0
    rate_without_retro = no_retro_failures / without_retro if without_retro > 0 else 0.0

    if sufficient_data and rate_without_retro > 0:
        improvement_pct = (rate_without_retro - rate_with_retro) / rate_without_retro * 100
        # estimated_savings = improvement_fraction * avg_waste_per_session * sessions_with_retro
        estimated_savings = round(improvement_pct / 100 * avg_waste * with_retro)
    else:
        improvement_pct = None
        estimated_savings = None

    return {
        "total_sessions": total_sessions,
        "with_retro": with_retro,
        "without_retro": without_retro,
        "rate_with_retro": round(rate_with_retro, 2),
        "rate_without_retro": round(rate_without_retro, 2),
        "improvement_pct": round(improvement_pct, 1) if improvement_pct is not None else None,
        "estimated_savings": estimated_savings,
        "sufficient_data": sufficient_data,
        "top_activations": top_activations,
        "dead_weight": dead_weight,
    }


def cmd_roi(args: argparse.Namespace) -> None:
    """Compute and display learning ROI report."""
    init_db()
    db_path = get_db_path()
    data = _compute_roi_data(db_path)

    if args.json:
        print(json.dumps(data, indent=2))
        return

    print("=== Learning ROI Report ===")
    print()
    print(
        f"Sessions: {data['total_sessions']} total ({data['with_retro']} with retro, {data['without_retro']} without)"
    )
    print()

    if not data["sufficient_data"]:
        print("Failure Rates:")
        print("  Insufficient data (need >= 3 sessions per cohort)")
        print()
    else:
        print("Failure Rates:")
        print(f"  With retro knowledge:    {data['rate_with_retro']:.2f} failures/session")
        print(f"  Without retro knowledge: {data['rate_without_retro']:.2f} failures/session")
        if data["improvement_pct"] is not None:
            if data["improvement_pct"] < 0:
                print(f"  WARNING: Retro cohort shows REGRESSION: {data['improvement_pct']:.1f}%")
                print(f"  Estimated waste increase: ~{abs(data['estimated_savings']):,} tokens")
            else:
                print(f"  Improvement:             {data['improvement_pct']:.1f}%")
                print(f"  Estimated Savings:       ~{data['estimated_savings']:,} tokens saved")
        else:
            print("  Improvement:             N/A (no failures in baseline cohort)")
        print()

    if data["top_activations"]:
        print("Top Activated Learnings:")
        for i, act in enumerate(data["top_activations"], 1):
            print(f"  {i}. {act['topic']}/{act['key']}  ({act['count']} activations)")
        print()

    if data["dead_weight"]:
        print("Dead Weight (0 activations):")
        for dw in data["dead_weight"]:
            print(f"  - {dw['topic']}/{dw['key']} (age: {dw['age_days']} days)")
        print()


def cmd_learn(args):
    """Record a skill- or agent-scoped learning with minimal friction."""
    import hashlib

    value = args.value
    # Auto-generate key from value hash
    key = hashlib.sha256(value.encode()).hexdigest()[:12]

    # Determine topic from --skill or --agent
    if args.skill:
        topic = f"skill:{args.skill}"
    elif args.agent:
        topic = f"agent:{args.agent}"
    else:
        topic = args.topic or "general"

    result = record_learning(
        topic=topic,
        key=key,
        value=value,
        category="gotcha",
        confidence=0.7,
        tags=[args.skill or args.agent or "general"],
        source="manual:learn",
        source_detail=None,
        project_path=args.project_path,
    )
    action = "Updated" if not result["is_new"] else "Recorded"
    print(f"{action}: [{topic}] {value[:80]}... (confidence: {result['confidence']:.2f})")


def cmd_purge(args):
    """Delete all entries matching a topic."""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("DELETE FROM learnings WHERE topic = ?", (args.topic,))
    count = cursor.rowcount
    conn.commit()
    conn.close()
    print(f"Purged {count} entries with topic '{args.topic}'")


def cmd_migrate(args):
    """Run all migrations: import from patterns.db and retro markdown."""
    init_db()
    print(f"Database initialized at: {get_db_path()}")

    # Import from patterns.db if it exists
    patterns_path = Path.home() / ".claude" / "learning" / "patterns.db"
    if patterns_path.exists():
        result = import_from_patterns_db(str(patterns_path))
        print(f"patterns.db: {result['imported']} imported, {result['skipped']} skipped")
        if result["errors"]:
            for e in result["errors"]:
                print(f"  error: {e}")
    else:
        print("patterns.db: not found, skipping")

    # Import from retro L2 if it exists
    retro_dir = Path.home() / ".claude" / "retro"
    if (retro_dir / "L2").is_dir():
        result = import_from_retro(str(retro_dir))
        print(f"retro L2: {result['imported']} imported, {result['skipped']} skipped")
        if result["errors"]:
            for e in result["errors"]:
                print(f"  error: {e}")
    else:
        print("retro L2: not found, skipping")

    # Also check repo retro
    repo_retro = _repo_root / "retro"
    if (repo_retro / "L2").is_dir() and repo_retro != retro_dir:
        result = import_from_retro(str(repo_retro))
        print(f"repo retro L2: {result['imported']} imported, {result['skipped']} skipped")
        if result["errors"]:
            for e in result["errors"]:
                print(f"  error: {e}")

    stats = get_stats()
    print(
        f"\nPost-migration: {stats['total_learnings']} total learnings, "
        f"{stats['high_confidence']} high confidence, "
        f"{stats['sessions_tracked']} sessions"
    )


def _non_negative_int(value: str) -> int:
    """Validate that an argparse integer value is non-negative.

    Args:
        value: String value from argparse to convert and validate.

    Returns:
        The parsed non-negative integer.

    Raises:
        argparse.ArgumentTypeError: If the value is negative.
    """
    n = int(value)
    if n < 0:
        raise argparse.ArgumentTypeError(f"Value must be >= 0, got {n}")
    return n


def main():
    parser = argparse.ArgumentParser(description="Learning Database CLI — manage the unified knowledge store")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # record
    p_record = subparsers.add_parser("record", help="Record a learning")
    p_record.add_argument("topic", help="Domain category (e.g., go-patterns, debugging)")
    p_record.add_argument("key", help="Short identifier (e.g., mutex-over-atomics)")
    p_record.add_argument("value", help="Learning content")
    p_record.add_argument(
        "--category",
        default="design",
        choices=["error", "pivot", "review", "design", "debug", "gotcha", "effectiveness"],
        help="Learning category",
    )
    p_record.add_argument("--confidence", type=float, default=None)
    p_record.add_argument("--tags", help="Comma-separated tags")
    p_record.add_argument("--source", help="Source identifier")
    p_record.add_argument("--source-detail", help="Additional source context")
    p_record.add_argument("--project-path", help="Project path")
    p_record.set_defaults(func=cmd_record)

    # query
    p_query = subparsers.add_parser("query", help="Query learnings")
    p_query.add_argument("--topic", help="Filter by topic")
    p_query.add_argument("--category", help="Filter by category")
    p_query.add_argument("--tags", help="Filter by tags (comma-separated, matches ANY)")
    p_query.add_argument("--min-confidence", type=float, default=0.0)
    p_query.add_argument("--include-graduated", action="store_true")
    p_query.add_argument("--order-by", default="confidence DESC")
    p_query.add_argument("--limit", type=int, default=20)
    p_query.add_argument("--format", choices=["human", "json"], default="human")
    p_query.set_defaults(func=cmd_query)

    # search
    p_search = subparsers.add_parser("search", help="Full-text search with BM25 ranking")
    p_search.add_argument("query", help="FTS5 query (e.g. 'circuit breaker retry', 'goroutine OR channel')")
    p_search.add_argument("--min-confidence", type=float, default=0.0)
    p_search.add_argument("--include-graduated", action="store_true")
    p_search.add_argument("--limit", type=int, default=20)
    p_search.add_argument("--format", choices=["human", "json"], default="human")
    p_search.set_defaults(func=cmd_search)

    # stats
    p_stats = subparsers.add_parser("stats", help="Show learning statistics")
    p_stats.add_argument("--format", choices=["human", "json"], default="human")
    p_stats.set_defaults(func=cmd_stats)

    # export
    p_export = subparsers.add_parser("export", help="Export learnings as markdown")
    p_export.add_argument("--format", choices=["l1", "l2", "full"], default="l2")
    p_export.add_argument("--output-dir", help="Directory for L2 files")
    p_export.set_defaults(func=cmd_export)

    # import
    p_import = subparsers.add_parser("import", help="Import from legacy stores")
    p_import.add_argument("--from-retro", help="Path to retro/ directory")
    p_import.add_argument("--from-patterns", help="Path to patterns.db")
    p_import.set_defaults(func=cmd_import)

    # graduate
    p_grad = subparsers.add_parser("graduate", help="Mark entry as graduated")
    p_grad.add_argument("topic")
    p_grad.add_argument("key")
    p_grad.add_argument("target", help="Target (e.g., agent:golang-general-engineer)")
    p_grad.set_defaults(func=cmd_graduate)

    # boost
    p_boost = subparsers.add_parser("boost", help="Boost confidence")
    p_boost.add_argument("topic")
    p_boost.add_argument("key")
    p_boost.add_argument("--delta", type=float, default=0.10)
    p_boost.set_defaults(func=cmd_boost)

    # decay
    p_decay = subparsers.add_parser("decay", help="Decay confidence")
    p_decay.add_argument("topic")
    p_decay.add_argument("key")
    p_decay.add_argument("--delta", type=float, default=0.10)
    p_decay.set_defaults(func=cmd_decay)

    # prune (legacy destructive delete)
    p_prune = subparsers.add_parser("prune", help="Remove low-confidence old entries (destructive delete)")
    p_prune.add_argument("--below-confidence", type=float, default=0.3)
    p_prune.add_argument("--older-than", type=int, default=90, help="Days")
    p_prune.set_defaults(func=cmd_prune)

    # stale (show stale entries)
    p_stale = subparsers.add_parser("stale", help="Show entries that appear stale")
    p_stale.add_argument("--min-age-days", type=int, default=30, help="Minimum age in days (default: 30)")
    p_stale.add_argument("--json", action="store_true", help="Output as JSON")
    p_stale.set_defaults(func=cmd_stale)

    # stale-prune (archive stale entries)
    p_stale_prune = subparsers.add_parser("stale-prune", help="Archive stale entries to learning_archive table")
    p_stale_prune.add_argument("--min-age-days", type=int, default=30, help="Minimum age in days (default: 30)")
    p_stale_prune_group = p_stale_prune.add_mutually_exclusive_group(required=True)
    p_stale_prune_group.add_argument("--dry-run", action="store_true", help="Preview what would be archived")
    p_stale_prune_group.add_argument("--confirm", action="store_true", help="Actually archive stale entries")
    p_stale_prune.set_defaults(func=cmd_stale_prune)

    # learn (low-friction skill-scoped recording)
    p_learn = subparsers.add_parser("learn", help="Record a skill/agent-scoped learning (one-liner)")
    p_learn.add_argument("value", help="The learning content (one sentence)")
    p_learn.add_argument("--skill", help="Skill name (sets topic to skill:{name})")
    p_learn.add_argument("--agent", help="Agent name (sets topic to agent:{name})")
    p_learn.add_argument("--topic", help="Custom topic (fallback if no --skill/--agent)")
    p_learn.add_argument("--project-path", help="Project path")
    p_learn.set_defaults(func=cmd_learn)

    # purge (delete by topic)
    p_purge = subparsers.add_parser("purge", help="Delete all entries matching a topic")
    p_purge.add_argument("--topic", required=True, help="Topic to purge (e.g., worktree-branches)")
    p_purge.set_defaults(func=cmd_purge)

    # migrate
    p_migrate = subparsers.add_parser("migrate", help="Import from all legacy stores")
    p_migrate.set_defaults(func=cmd_migrate)

    # record-activation
    p_rec_act = subparsers.add_parser("record-activation", help="Record a learning activation")
    p_rec_act.add_argument("topic", help="Learning topic")
    p_rec_act.add_argument("key", help="Learning key")
    p_rec_act.add_argument("--session", required=True, help="Session ID")
    p_rec_act.add_argument("--outcome", default="success", help="Outcome (success/failure)")
    p_rec_act.set_defaults(func=cmd_record_activation)

    # record-waste
    p_rec_waste = subparsers.add_parser("record-waste", help="Record wasted tokens from a failure")
    p_rec_waste.add_argument("--session", required=True, help="Session ID")
    p_rec_waste.add_argument("--tokens", type=_non_negative_int, required=True, help="Number of wasted tokens")
    p_rec_waste.set_defaults(func=cmd_record_waste)

    # record-session
    p_rec_sess = subparsers.add_parser("record-session", help="Create or update a session_stats entry")
    p_rec_sess.add_argument("--session", required=True, help="Session ID")
    p_rec_sess.add_argument("--had-retro", action="store_true", help="Session had retro knowledge injected")
    p_rec_sess.add_argument("--failures", type=_non_negative_int, default=0, help="Number of failures")
    p_rec_sess.add_argument("--waste-tokens", type=_non_negative_int, default=0, help="Wasted tokens")
    p_rec_sess.set_defaults(func=cmd_record_session_stats)

    # roi
    p_roi = subparsers.add_parser("roi", help="Compute and display learning ROI report")
    p_roi.add_argument("--json", action="store_true", help="Output as JSON")
    p_roi.set_defaults(func=cmd_roi)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
