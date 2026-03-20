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
    python3 scripts/learning-db.py migrate
"""

import argparse
import json
import sys
from pathlib import Path

# Add hooks/lib to path for learning_db_v2
_repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_repo_root / "hooks" / "lib"))

# Also check ~/.claude/hooks/lib for cross-repo usage
_home_lib = Path.home() / ".claude" / "hooks" / "lib"
if _home_lib.is_dir():
    sys.path.insert(0, str(_home_lib))

from learning_db_v2 import (
    boost_confidence,
    decay_confidence,
    export_markdown,
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
    count = prune(args.below_confidence, args.older_than)
    print(f"Pruned {count} entries (confidence < {args.below_confidence}, older than {args.older_than} days)")


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
        category="learned",
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
    import sqlite3

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

    # prune
    p_prune = subparsers.add_parser("prune", help="Remove low-confidence old entries")
    p_prune.add_argument("--below-confidence", type=float, default=0.3)
    p_prune.add_argument("--older-than", type=int, default=90, help="Days")
    p_prune.set_defaults(func=cmd_prune)

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

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
