#!/usr/bin/env python3
"""
Learning Database CLI — Deterministic operations on the unified knowledge store.

Usage:
    python3 scripts/learning-db.py learn --skill go-patterns "insight text"
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
    python3 scripts/learning-db.py route-stats --by agent|skill|force-route|errors|override|week|day [--json]
    python3 scripts/learning-db.py review-roi [--json]
    python3 scripts/learning-db.py route-delta --from REF --to REF [--key AGENT:SKILL] [--metric error|tokens] [--json]
    python3 scripts/learning-db.py record-routing-outcome AGENT_SKILL --success
    python3 scripts/learning-db.py record-routing-outcome AGENT_SKILL --failure --reason "user re-routed"
    python3 scripts/learning-db.py backfill-routing-outcomes
    python3 scripts/learning-db.py route-health [--json]
    python3 scripts/learning-db.py skip-rate [--json] [--include-test]
"""

import argparse
import json
import re
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
    query_instruction_skip_rate,
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
        print(f"Imported from retro: {result['imported']} entries, {result['skipped']} skipped")  # security-review: ignore (print, not SQL; pre-existing)  # fmt: skip
    elif args.from_patterns:
        result = import_from_patterns_db(args.from_patterns)
        print(f"Imported from patterns.db: {result['imported']} entries, {result['skipped']} skipped")  # security-review: ignore (print, not SQL; pre-existing)  # fmt: skip
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
    with get_connection() as conn:
        entries = _query_stale_entries(conn, args.min_age_days)

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
    with get_connection() as conn:
        entries = _query_stale_entries(conn, args.min_age_days)

        if not entries:
            print(f"No stale entries to archive (age > {args.min_age_days} days, confidence < 0.5, not graduated).")
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


def cmd_route_stats(args: argparse.Namespace) -> None:
    """Display routing decision statistics."""
    init_db()

    # Time-series dimensions (ADR: learning-telemetry-envelope) read the
    # append-only telemetry_runs table, not the aggregated learnings value string.
    if args.by in ("week", "day"):
        _route_stats_time_series(args)
        return

    results = query_learnings(topic="routing", category="effectiveness", limit=10000, exclude_graduated=False)

    if not results:
        print("No routing data found. Run sessions with /do to capture routing decisions.")
        return

    # Parse pipe-delimited values into dicts
    records: list[dict[str, str | int]] = []
    for r in results:
        parsed: dict[str, str | int] = {"key": r["key"], "observation_count": r.get("observation_count", 1)}
        for pair in r["value"].split(" | "):
            if ": " in pair:
                k, v = pair.split(": ", 1)
                parsed[k.strip()] = v.strip()
        records.append(parsed)

    dimension = args.by

    if dimension == "agent":
        _print_freq_table(
            records, "Agent", lambda r: str(r["key"]).split(":")[0] if ":" in str(r["key"]) else str(r["key"])
        )
    elif dimension == "skill":
        _print_freq_table(
            records, "Skill", lambda r: str(r["key"]).split(":")[-1] if ":" in str(r["key"]) else str(r["key"])
        )
    elif dimension == "force-route":
        total = len(records)
        force = sum(1 for r in records if r.get("force_used") == "1" or "force-route" in str(r.get("key", "")))
        print(f"Force-Route Stats ({total} total routes)")
        print(f"{'─' * 40}")
        if total:
            print(f"  Force-routed:  {force:>4} ({force / total * 100:.0f}%)")
            print(f"  Scored:        {total - force:>4} ({(total - force) / total * 100:.0f}%)")
        else:
            print("  No data")
    elif dimension == "errors":
        errored = [r for r in records if r.get("tool_errors") == "1"]
        print(f"Routes with Tool Errors ({len(errored)} of {len(records)})")
        print(f"{'─' * 50}")
        for r in errored:
            req = str(r.get("request", ""))[:60]
            print(f"  {str(r['key']):40s} | {req}")
        if not errored:
            print("  No tool errors recorded.")
    elif dimension == "override":
        total = len(records)
        overrides = sum(1 for r in records if r.get("llm_override") == "1")
        print(f"LLM Override Stats ({total} total routes)")
        print(f"{'─' * 40}")
        if total:
            print(f"  LLM overrode Phase 0: {overrides:>4} ({overrides / total * 100:.0f}%)")
            print(f"  Used Phase 0 as-is:   {total - overrides:>4} ({(total - overrides) / total * 100:.0f}%)")
        else:
            print("  No data")

    if args.json:
        import json as json_mod

        print(json_mod.dumps(records, indent=2, default=str))


# Default minimum cohort size below which route-delta prints a low-sample WARNING.
# Report-only — it never blocks; the numbers still print (ADR: learning-telemetry-envelope).
MIN_N = 5


def _route_stats_time_series(args: argparse.Namespace) -> None:
    """route-stats --by week|day: per-period run/error counts from telemetry_runs."""
    # strftime period format: ISO-ish week ('%Y-W%W') or calendar day ('%Y-%m-%d').
    period_fmt = "%Y-W%W" if args.by == "week" else "%Y-%m-%d"
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT strftime(?, recorded_at) AS period, "
            "COUNT(*) AS runs, "
            "COALESCE(SUM(tool_errors), 0) AS errors, "
            "ROUND(100.0 * SUM(tool_errors) / COUNT(*), 1) AS error_pct "
            "FROM telemetry_runs WHERE topic = 'routing' "
            "GROUP BY period ORDER BY period",
            (period_fmt,),
        ).fetchall()

    data = [
        {"period": r["period"], "runs": r["runs"], "errors": r["errors"], "error_pct": r["error_pct"]} for r in rows
    ]

    if args.json:
        print(json.dumps(data, indent=2, default=str))
        return

    if not data:
        print("No telemetry runs yet. Telemetry captures from the next /do dispatch after merge+sync.")
        return

    label = "Week" if args.by == "week" else "Day"
    max_runs = max(row["runs"] for row in data) or 1
    print(f"Routing telemetry by {label.lower()} ({sum(row['runs'] for row in data)} runs)")
    print("-" * 56)
    print(f"{label:<11} {'runs':>5} {'errors':>7} {'err%':>6}  bar")
    for row in data:
        bar = "#" * max(1, round(20 * row["runs"] / max_runs))
        pct = row["error_pct"] if row["error_pct"] is not None else 0.0
        print(f"{row['period']:<11} {row['runs']:>5} {row['errors']:>7} {pct:>5.1f}%  {bar}")


def _resolve_cohort(conn, ref: str, key: str | None) -> str:
    """Build the WHERE clause for one cohort ref (git-SHA prefix or date), with params.

    A `ref` that is all hex and >=4 chars is treated as a git-SHA prefix matched
    against telemetry_runs.git_sha; otherwise it is matched as a date prefix on
    recorded_at. --key further scopes to one route. Returns (where_sql, params).
    """
    clauses = ["topic = 'routing'"]
    params: list[str] = []
    is_sha = len(ref) >= 4 and all(c in "0123456789abcdefABCDEF" for c in ref)
    if is_sha:
        clauses.append("git_sha LIKE ?")
        params.append(ref + "%")
    else:
        clauses.append("recorded_at LIKE ?")
        params.append(ref + "%")
    if key:
        clauses.append("key = ?")
        params.append(key)
    return " AND ".join(clauses), params


def _cohort_error(conn, where: str, params: list[str]) -> dict:
    """Error-rate stats for one cohort."""
    # `where` is built only from fixed clauses; all user values are bound as ? params.
    row = conn.execute(
        f"SELECT COUNT(*) AS runs, COALESCE(SUM(tool_errors), 0) AS errors FROM telemetry_runs WHERE {where}",  # security-review: ignore (fixed clauses; user values bound as ?)
        params,
    ).fetchone()
    runs = row["runs"]
    errors = row["errors"]
    pct = round(100.0 * errors / runs, 1) if runs else None
    return {"runs": runs, "errors": errors, "error_pct": pct}


def _cohort_tokens(conn, where: str, params: list[str]) -> dict:
    """Token stats for one cohort. n counts NON-NULL token rows only; NULL never
    counts as 0 (ADR NULL-tolerance)."""
    # `where` is built only from fixed clauses; all user values are bound as ? params.
    row = conn.execute(
        f"SELECT COUNT(token_count) AS n, AVG(token_count) AS avg_tokens, COUNT(*) AS runs FROM telemetry_runs WHERE {where}",  # security-review: ignore (fixed clauses; user values bound as ?)
        params,
    ).fetchone()
    n = row["n"]
    avg = round(row["avg_tokens"], 1) if row["avg_tokens"] is not None else None
    return {"runs": row["runs"], "n": n, "avg_tokens": avg}


# Below this many findings-bearing reviews the ROI table refuses to assert a
# "best" tier — a humility gate, not a merge gate (ADR: review-tier-roi).
ROI_MIN_REVIEWS = 20

# Severity fields whose per-tier average is always reported.
_ROI_FINDINGS_FIELDS = ("findings_critical", "findings_high", "findings_medium")
# Cost fields that are nullable: a "-" value is skipped, never counted as 0.
_ROI_COST_FIELDS = ("tokens", "wall_clock_s")
_RIGHTSIZING_KEY_RE = re.compile(r"^rightsizing:tier(\d+)$")


def _parse_pipe_value(value: str) -> dict[str, str]:
    """Parse a pipe-delimited `k: v | k: v` value into a dict (route-stats format)."""
    parsed: dict[str, str] = {}
    for pair in value.split(" | "):
        if ": " in pair:
            k, v = pair.split(": ", 1)
            parsed[k.strip()] = v.strip()
    return parsed


def _avg(total: float, count: int) -> float | None:
    """Average, or None when there is no contributing row (n/a, not 0)."""
    return round(total / count, 2) if count else None


def _compute_review_roi() -> list[dict]:
    """Aggregate rightsizing:tier{N} rows into per-tier ROI dicts, tier ascending.

    reviews = observation_count (reviews recorded at that tier). Findings are
    averaged over reviews. Cost fields average only over rows with a numeric
    value; an all-"-" tier reports null (n/a). Tiers with zero findings-bearing
    reviews are excluded (a composition-only banner carries no findings)."""
    rows = query_learnings(
        topic="routing",
        category="effectiveness",
        limit=10000,
        exclude_graduated=False,
        exclude_test_sources=False,
    )
    # Per tier: review count + running sums for findings (per-review) and cost.
    agg: dict[int, dict] = {}
    for r in rows:
        m = _RIGHTSIZING_KEY_RE.match(r["key"])
        if not m:
            continue
        fields = _parse_pipe_value(r["value"])
        # A findings-bearing review has numeric severity counts (not "-").
        if any(fields.get(f, "-") == "-" for f in _ROI_FINDINGS_FIELDS):
            continue
        tier = int(m.group(1))
        reviews = int(r.get("observation_count", 1) or 1)
        a = agg.setdefault(
            tier,
            {
                "reviews": 0,
                "findings": dict.fromkeys(_ROI_FINDINGS_FIELDS, 0.0),
                "cost": {c: [0.0, 0] for c in _ROI_COST_FIELDS},
            },
        )
        a["reviews"] += reviews
        for f in _ROI_FINDINGS_FIELDS:
            a["findings"][f] += float(fields[f]) * reviews
        for c in _ROI_COST_FIELDS:
            raw = fields.get(c, "-")
            if raw != "-":
                a["cost"][c][0] += float(raw) * reviews
                a["cost"][c][1] += reviews

    total_reviews = sum(a["reviews"] for a in agg.values())
    insufficient = total_reviews < ROI_MIN_REVIEWS
    out = []
    for tier in sorted(agg):
        a = agg[tier]
        n = a["reviews"]
        out.append(
            {
                "tier": tier,
                "reviews": n,
                "avg_critical": _avg(a["findings"]["findings_critical"], n),
                "avg_high": _avg(a["findings"]["findings_high"], n),
                "avg_medium": _avg(a["findings"]["findings_medium"], n),
                "avg_tokens": _avg(*a["cost"]["tokens"]),
                "avg_wall_clock_s": _avg(*a["cost"]["wall_clock_s"]),
                "insufficient_data": insufficient,
            }
        )
    return out


def cmd_review_roi(args: argparse.Namespace) -> None:
    """review-roi: per-tier review cost/findings ROI (report-only, never blocks)."""
    init_db()
    data = _compute_review_roi()
    total_reviews = sum(r["reviews"] for r in data)

    if args.json:
        print(json.dumps(data, indent=2, default=str))
        return

    if not data:
        print("No review-ROI data. Run reviews that emit findings= in the rightsizing banner.")
        return

    def _cell(v: float | None) -> str:
        return "n/a" if v is None else f"{v:g}"

    print(f"Review-Tier ROI  ({total_reviews} reviews)")
    print(
        f"{'Tier':<5} {'Reviews':>8} {'Avg Crit':>9} {'Avg High':>9} {'Avg Med':>8} {'Avg Tokens':>11} {'Avg Wall(s)':>12}"
    )
    for r in data:
        print(
            f"{r['tier']:<5} {r['reviews']:>8} {_cell(r['avg_critical']):>9} {_cell(r['avg_high']):>9} "
            f"{_cell(r['avg_medium']):>8} {_cell(r['avg_tokens']):>11} {_cell(r['avg_wall_clock_s']):>12}"
        )
    if data and data[0]["insufficient_data"]:
        print(
            f"INSUFFICIENT DATA: {total_reviews} reviews (<{ROI_MIN_REVIEWS}). "
            "Numbers shown for inspection; do not act on them."
        )


def cmd_route_delta(args: argparse.Namespace) -> None:
    """route-delta --from REF --to REF: 'did that change help?' cohort comparison.

    Report-only — a low sample prints a WARNING but never blocks (exit 0).
    """
    init_db()
    metric = args.metric
    with get_connection() as conn:
        where_a, params_a = _resolve_cohort(conn, args.from_ref, args.key)
        where_b, params_b = _resolve_cohort(conn, args.to_ref, args.key)
        if metric == "tokens":
            cohort_a = _cohort_tokens(conn, where_a, params_a)
            cohort_b = _cohort_tokens(conn, where_b, params_b)
        else:
            cohort_a = _cohort_error(conn, where_a, params_a)
            cohort_b = _cohort_error(conn, where_b, params_b)

    if metric == "tokens":
        a_val = cohort_a["avg_tokens"]
        b_val = cohort_b["avg_tokens"]
        delta = round(b_val - a_val, 1) if (a_val is not None and b_val is not None) else None
        result = {"metric": "tokens", "from": cohort_a, "to": cohort_b, "delta_tokens": delta}
    else:
        a_pct = cohort_a["error_pct"]
        b_pct = cohort_b["error_pct"]
        delta = round(b_pct - a_pct, 1) if (a_pct is not None and b_pct is not None) else None
        result = {"metric": "error", "from": cohort_a, "to": cohort_b, "delta_pts": delta}

    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return

    scope = f"  key={args.key}" if args.key else ""
    print(f"route-delta  metric={metric}  from={args.from_ref}  to={args.to_ref}{scope}")  # security-review: ignore (print, not SQL)  # fmt: skip
    print("-" * 56)
    if metric == "tokens":
        a_disp = f"{cohort_a['avg_tokens']}" if cohort_a["avg_tokens"] is not None else "n/a"
        b_disp = f"{cohort_b['avg_tokens']}" if cohort_b["avg_tokens"] is not None else "n/a"
        print(f"Cohort A ({args.from_ref}): {cohort_a['runs']:>4} runs, avg tokens {a_disp} (n={cohort_a['n']})")
        print(f"Cohort B ({args.to_ref}): {cohort_b['runs']:>4} runs, avg tokens {b_disp} (n={cohort_b['n']})")
        if delta is not None:
            direction = "fewer" if delta < 0 else "more"
            print(f"Delta: {delta:+} tokens ({direction})   n_A={cohort_a['n']} n_B={cohort_b['n']}")
        else:
            print("Delta: n/a (a cohort has no non-NULL token_count)")
    else:
        a_pct = f"{cohort_a['error_pct']:.1f}%" if cohort_a["error_pct"] is not None else "n/a"
        b_pct = f"{cohort_b['error_pct']:.1f}%" if cohort_b["error_pct"] is not None else "n/a"
        print(f"Cohort A ({args.from_ref}): {cohort_a['runs']:>4} runs, {cohort_a['errors']:>3} errors ({a_pct})")
        print(f"Cohort B ({args.to_ref}): {cohort_b['runs']:>4} runs, {cohort_b['errors']:>3} errors ({b_pct})")
        if delta is not None:
            direction = "improved" if delta < 0 else ("worse" if delta > 0 else "flat")
            print(f"Delta: {delta:+} pts error rate  ({direction})   n_A={cohort_a['runs']} n_B={cohort_b['runs']}")
        else:
            print("Delta: n/a (a cohort has no runs)")

    # Low-sample advisory — report-only, never blocks.
    for label, n in (("A", cohort_a["runs"]), ("B", cohort_b["runs"])):
        if n < MIN_N:
            print(f"WARNING: cohort {label} has only {n} run(s) (< MIN_N={MIN_N}); treat the delta as low-confidence.")


def cmd_record_routing_outcome(args: argparse.Namespace) -> None:
    """Record whether a routing decision succeeded or failed."""
    init_db()
    key = args.agent_skill

    # Verify the routing entry exists
    results = query_learnings(
        topic="routing",
        category="effectiveness",
        limit=10000,
        exclude_graduated=False,
        exclude_test_sources=False,
    )
    entry = next((r for r in results if r["key"] == key), None)
    if entry is None:
        print(f"WARNING: No routing entry found for key '{key}' — route was never recorded.", file=sys.stderr)
        sys.exit(1)

    if args.success:
        new_conf = boost_confidence("routing", key, delta=0.05)
    else:
        new_conf = decay_confidence("routing", key, delta=0.08)

    # Append reason to value if provided
    if args.reason:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT value FROM learnings WHERE topic = ? AND key = ?",
                ("routing", key),
            ).fetchone()
            if row:
                new_value = f"{row['value']} | outcome_reason: {args.reason}"
                conn.execute(
                    "UPDATE learnings SET value = ? WHERE topic = ? AND key = ?",
                    (new_value, "routing", key),
                )
                conn.commit()

    outcome = "success" if args.success else "failure"
    print(f"Recorded {outcome} for routing/{key} — confidence: {new_conf:.4f}")


def cmd_backfill_routing_outcomes(args: argparse.Namespace) -> None:
    """Backfill routing outcomes from existing entry data."""
    init_db()
    results = query_learnings(
        topic="routing",
        category="effectiveness",
        limit=10000,
        exclude_graduated=False,
        exclude_test_sources=False,
    )

    boosted = 0
    decayed_count = 0
    skipped = 0
    unchanged = 0

    for r in results:
        # Idempotency: skip entries already scored
        if (r["success_count"] or 0) + (r["failure_count"] or 0) > 0:
            skipped += 1
            continue

        value = r["value"]
        if "tool_errors=1" in value or "user_rerouted=1" in value:
            decay_confidence("routing", r["key"], delta=0.08)
            decayed_count += 1
        elif "outcome=committed_and_pushed" in value or "outcome=success" in value:
            boost_confidence("routing", r["key"], delta=0.05)
            boosted += 1
        else:
            unchanged += 1

    total = boosted + decayed_count + unchanged + skipped
    print(f"Backfill complete: {total} entries processed")
    print(f"  Boosted:   {boosted}")
    print(f"  Decayed:   {decayed_count}")
    print(f"  Skipped:   {skipped}")
    print(f"  Unchanged: {unchanged}")


def cmd_skip_rate(args: argparse.Namespace) -> None:
    """Display instruction skip-rate report from the instruction_compliance table.

    Queries the dedicated instruction_compliance table for per-observation
    data and computes skip rate per instruction. Flags instructions with
    >20% skip rate over 30+ observations for conversion to programmatic gates.
    """
    init_db()

    # Instruction ID -> human-readable name mapping
    instr_names: dict[str, str] = {
        "M01": "Phase Banners",
        "M03": "Routing Decision",
        "M04": "Reference Loading",
        "M05": "Completeness",
        "M06": "Density Standard",
    }

    results = query_instruction_skip_rate(days=30)

    if not results:
        print("No instruction compliance data found. Run sessions to collect data.")
        return

    if args.json:
        report = []
        for r in results:
            instr_id = r["instruction_id"]
            report.append(
                {
                    "id": instr_id,
                    "name": instr_names.get(instr_id, instr_id),
                    "observations": r["observations"],
                    "non_compliant": r["non_compliant"],
                    "skip_rate": r["skip_rate"],
                    "status": "CONVERT_TO_GATE" if r["skip_rate"] > 20 and r["observations"] >= 30 else "OK",
                }
            )
        print(json.dumps(report, indent=2))
        return

    # Human-readable output
    print("Instruction Skip Rate Report")
    print("=" * 72)
    print(f"{'ID':<6}{'Instruction':<22}{'Observations':>14}{'Skip Rate':>12}{'Status':>18}")
    print("-" * 72)

    for r in results:
        instr_id = r["instruction_id"]
        name = instr_names.get(instr_id, instr_id)
        skip_rate = r["skip_rate"]

        if skip_rate > 20 and r["observations"] >= 30:
            status = "CONVERT TO GATE"
        else:
            status = "OK"

        print(f"{instr_id:<6}{name:<22}{r['observations']:>14}{skip_rate:>11.1f}%{status:>17}")

    print("-" * 72)
    flagged = sum(1 for r in results if r["skip_rate"] > 20 and r["observations"] >= 30)
    if flagged:
        print(f"{flagged} instruction(s) flagged for conversion to programmatic gates (>20% skip, 30+ obs)")
    else:
        print("No instructions flagged. Threshold: >20% skip rate over 30+ observations.")


_BASIS_LABELS = ("rejection_detected", "tool_errors_only", "default_no_complaint")


def _read_basis_counts() -> dict[str, int]:
    """Sum routing_outcome_basis counts per label. Best-effort: {} on any error.

    All three labels are always present (0 when unseen) so callers never
    KeyError. Table absent / unreadable (pre-v6 DB) => all zeros.
    """
    counts = {label: 0 for label in _BASIS_LABELS}
    try:
        with get_connection() as conn:
            rows = conn.execute("SELECT basis, SUM(count) AS n FROM routing_outcome_basis GROUP BY basis").fetchall()
        for row in rows:
            if row["basis"] in counts:
                counts[row["basis"]] = int(row["n"] or 0)
    except Exception:
        pass
    return counts


def cmd_route_health(args: argparse.Namespace) -> None:
    """Display a quick health summary of routing entries."""
    init_db()
    as_json = getattr(args, "json", False)
    results = query_learnings(
        topic="routing",
        category="effectiveness",
        min_confidence=0.0,
        limit=10000,
        exclude_graduated=False,
        exclude_test_sources=False,
    )

    total = len(results)
    if total == 0:
        if as_json:
            print(json.dumps({"total": 0, "entries_with_outcomes": 0}, indent=2))
        else:
            print("No routing entries found.")
        return

    baseline = sum(1 for r in results if r["success_count"] == 0 and r["failure_count"] == 0)
    boosted = sum(1 for r in results if r["success_count"] > 0)
    decayed_count = sum(1 for r in results if r["failure_count"] > 0)
    has_outcome = total - baseline
    pct = has_outcome / total * 100
    status = "CLOSED" if pct >= 50 else "OPEN"
    no_outcome_pct = baseline / total * 100

    # Outcome-basis split (ADR: silent-failure-outcome-quality). strong-feedback
    # = an observed signal scored the outcome; default-success = success on
    # silence (upper bound on silent success, NOT confirmed silent failures).
    basis = _read_basis_counts()
    strong = basis["rejection_detected"] + basis["tool_errors_only"]
    default_success = basis["default_no_complaint"]
    basis_total = strong + default_success
    silent_share = (default_success / basis_total) if basis_total else None

    if as_json:
        print(
            json.dumps(
                {
                    "total": total,
                    "entries_with_outcomes": has_outcome,
                    "outcome_pct": round(pct, 1),
                    "baseline": baseline,
                    "boosted": boosted,
                    "decayed": decayed_count,
                    "feedback_loop": status,
                    "basis": basis,
                    "strong_feedback": strong,
                    "default_success": default_success,
                    "silent_success_share": silent_share,
                    "governed_path_coverage": round(pct, 1),
                },
                indent=2,
            )
        )
        return

    print(f"Route Health: {has_outcome}/{total} entries have outcomes ({pct:.0f}%)")
    print(f"Confidence: {baseline} at baseline | {boosted} boosted | {decayed_count} decayed")
    print(f"Feedback loop: {status} ({no_outcome_pct:.0f}% entries have no outcome data)")

    if basis_total == 0:
        print("Outcome basis: no basis data yet")
    else:
        print(f"Outcome basis: {strong} strong-feedback vs {default_success} default-success")
        print(f"  rejection_detected   {basis['rejection_detected']}")
        print(f"  tool_errors_only     {basis['tool_errors_only']}")
        print(f"  default_no_complaint {basis['default_no_complaint']}")
        print(f"Silent-success share: {silent_share * 100:.0f}% of scored outcomes ({default_success}/{basis_total})")
    print(f"Governed-path coverage: {has_outcome}/{total} routing rows carry a finalized outcome ({pct:.0f}%)")


def _print_freq_table(records: list[dict[str, str | int]], label: str, key_fn: object) -> None:
    """Print a frequency table sorted by count descending."""
    from collections import Counter

    counts = Counter(key_fn(r) for r in records)  # type: ignore[operator]
    total = sum(counts.values())
    print(f"{label} Frequency ({total} total routes)")
    print(f"{'─' * 50}")
    for name, count in counts.most_common(20):
        bar = "█" * min(count, 30)
        print(f"  {name:35s} {count:>4} {bar}")


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
    init_db()
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM learnings WHERE topic = ?", (args.topic,))
        count = cursor.rowcount
        conn.commit()
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
        choices=["error", "pivot", "review", "design", "debug", "gotcha", "effectiveness", "misroute"],
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

    # route-stats
    p_route_stats = subparsers.add_parser("route-stats", help="Show routing decision statistics")
    p_route_stats.add_argument(
        "--by",
        required=True,
        choices=["agent", "skill", "force-route", "errors", "override", "week", "day"],
        help="Dimension to aggregate by (week|day read telemetry_runs time-series)",
    )
    p_route_stats.add_argument("--json", action="store_true", help="Also output raw JSON")
    p_route_stats.set_defaults(func=cmd_route_stats)

    # review-roi — per-tier review cost/findings ROI (report-only).
    p_review_roi = subparsers.add_parser("review-roi", help="Per-tier review cost/findings ROI")
    p_review_roi.add_argument("--json", action="store_true", help="Output as JSON")
    p_review_roi.set_defaults(func=cmd_review_roi)

    # route-delta — "did that change help?" cohort comparison over telemetry_runs.
    p_route_delta = subparsers.add_parser("route-delta", help="Compare two cohorts (git-SHA or date) of telemetry runs")
    p_route_delta.add_argument("--from", dest="from_ref", required=True, help="Cohort A: git-SHA prefix or date prefix")
    p_route_delta.add_argument("--to", dest="to_ref", required=True, help="Cohort B: git-SHA prefix or date prefix")
    p_route_delta.add_argument("--key", help="Scope to one route key (agent:skill)")
    p_route_delta.add_argument(
        "--metric", choices=["error", "tokens"], default="error", help="error rate (default) or avg tokens"
    )
    p_route_delta.add_argument("--json", action="store_true", help="Output as JSON")
    p_route_delta.set_defaults(func=cmd_route_delta)

    # record-routing-outcome
    p_rro = subparsers.add_parser("record-routing-outcome", help="Record routing decision outcome")
    p_rro.add_argument("agent_skill", help="Routing key (e.g., golang-general-engineer:go-patterns)")
    p_rro_group = p_rro.add_mutually_exclusive_group(required=True)
    p_rro_group.add_argument("--success", action="store_true", help="Route succeeded")
    p_rro_group.add_argument("--failure", action="store_true", help="Route failed")
    p_rro.add_argument("--reason", help="Reason for outcome (appended to value)")
    p_rro.set_defaults(func=cmd_record_routing_outcome)

    # backfill-routing-outcomes
    p_backfill = subparsers.add_parser(
        "backfill-routing-outcomes", help="Retroactively score routing entries from existing data"
    )
    p_backfill.set_defaults(func=cmd_backfill_routing_outcomes)

    # skip-rate
    p_skip_rate = subparsers.add_parser("skip-rate", help="Show instruction skip-rate report")
    p_skip_rate.add_argument("--json", action="store_true", help="Output as JSON")
    p_skip_rate.add_argument("--include-test", action="store_true", help="Ignored (kept for backward compat)")
    p_skip_rate.set_defaults(func=cmd_skip_rate)

    # route-health
    p_route_health = subparsers.add_parser("route-health", help="Quick routing feedback loop health check")
    p_route_health.add_argument("--json", action="store_true", help="Output as JSON")
    p_route_health.set_defaults(func=cmd_route_health)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
