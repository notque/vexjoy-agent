#!/usr/bin/env python3
"""Jev cost and efficiency report.

Reads jev_calls from learning.db and reports:
  - Total cost by script
  - Failed/wasted calls
  - Duplicate payload hashes (cache misses)
  - Per-session spend
  - Hourly call volume

Usage:
    python3 scripts/jev-cost-report.py [--since 24h] [--json]
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

COST_PER_MTOK = 0.042  # $/MTok input; output is free

try:
    import learning_db_v2 as _ldb

    DB = Path(_ldb.get_db_dir()) / "learning.db"
except Exception:
    DB = Path.home() / ".claude" / "learning" / "learning.db"


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(DB))
    c.row_factory = sqlite3.Row
    return c


def _since(val: str) -> str:
    """Parse '15m', '24h', '7d', or an ISO date into an ISO timestamp."""
    val = val.strip()
    units = {"m": "minutes", "h": "hours", "d": "days"}
    if val[-1:] in units and val[:-1].isdigit():
        dt = datetime.now(timezone.utc) - timedelta(**{units[val[-1]]: int(val[:-1])})
    else:
        try:
            dt = datetime.fromisoformat(val)
        except ValueError:
            raise SystemExit(f"--since: expected 15m, 24h, 7d, or an ISO date, got {val!r}") from None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def report(since: str) -> dict:
    c = _conn()
    ts = _since(since)

    # Totals
    row = c.execute(
        "SELECT count(*) as calls, sum(ok) as ok, "
        "sum(input_tokens) as in_tok, sum(output_tokens) as out_tok "
        "FROM jev_calls WHERE ts >= ?",
        (ts,),
    ).fetchone()
    totals = dict(row)
    totals["cost_usd"] = round((totals["in_tok"] or 0) / 1e6 * COST_PER_MTOK, 4)
    totals["failed"] = (totals["calls"] or 0) - (totals["ok"] or 0)

    # Per script
    scripts = []
    for r in c.execute(
        "SELECT script, count(*) as calls, sum(ok) as ok, "
        "sum(input_tokens) as in_tok, "
        "round(avg(CASE WHEN ok=1 THEN latency_ms END)) as avg_ms, "
        "round(avg(n_questions),1) as avg_q, "
        "sum(CASE WHEN cached=1 THEN 1 ELSE 0 END) as cache_hits, "
        "min(CASE WHEN cached != 1 THEN input_tokens END) as min_input_tokens, "
        "sum(CASE WHEN cached != 1 THEN 1 ELSE 0 END) as non_cached_calls "
        "FROM jev_calls WHERE ts >= ? GROUP BY script ORDER BY in_tok DESC",
        (ts,),
    ):
        d = dict(r)
        d["cost_usd"] = round((d["in_tok"] or 0) / 1e6 * COST_PER_MTOK, 4)
        d["failed"] = (d["calls"] or 0) - (d["ok"] or 0)
        scripts.append(d)

    # Fixed overhead: per script, min input_tok floor x non-cached count / total
    fixed_overhead = []
    for s in scripts:
        min_tok = s.get("min_input_tokens") or 0
        non_cached = s.get("non_cached_calls") or 0
        total_tok = s.get("in_tok") or 0
        if total_tok > 0 and min_tok > 0:
            overhead_tok = min_tok * non_cached
            ratio = overhead_tok / total_tok
            fixed_overhead.append(
                {
                    "script": s["script"],
                    "min_input_tok": min_tok,
                    "non_cached_calls": non_cached,
                    "overhead_tok": overhead_tok,
                    "total_tok": total_tok,
                    "overhead_pct": round(ratio * 100, 1),
                }
            )

    # Waste: failed by error
    errors = []
    for r in c.execute(
        "SELECT error, count(*) as n FROM jev_calls WHERE ok=0 AND ts >= ? GROUP BY error ORDER BY n DESC LIMIT 10",
        (ts,),
    ):
        errors.append(dict(r))

    # Duplicates: payload hashes seen more than once
    dupes = []
    for r in c.execute(
        "SELECT payload_hash, count(*) as times, script "
        "FROM jev_calls WHERE payload_hash IS NOT NULL AND ts >= ? "
        "GROUP BY payload_hash HAVING count(*) > 1 "
        "ORDER BY times DESC LIMIT 15",
        (ts,),
    ):
        dupes.append(dict(r))

    # Per session (all sessions)
    sessions = []
    for r in c.execute(
        "SELECT session_id, count(*) as calls, sum(ok) as ok, "
        "sum(input_tokens) as in_tok, "
        "count(distinct script) as scripts "
        "FROM jev_calls WHERE ts >= ? AND session_id IS NOT NULL "
        "GROUP BY session_id ORDER BY in_tok DESC",
        (ts,),
    ):
        d = dict(r)
        d["cost_usd"] = round((d["in_tok"] or 0) / 1e6 * COST_PER_MTOK, 4)
        d["failed"] = (d["calls"] or 0) - (d["ok"] or 0)
        sessions.append(d)

    # Hourly volume
    hourly = []
    for r in c.execute(
        "SELECT substr(ts,1,13) as hour, count(*) as calls, sum(ok) as ok "
        "FROM jev_calls WHERE ts >= ? GROUP BY hour ORDER BY hour",
        (ts,),
    ):
        hourly.append(dict(r))

    c.close()
    return {
        "since": ts,
        "totals": totals,
        "per_script": scripts,
        "fixed_overhead": fixed_overhead,
        "errors": errors,
        "duplicates": dupes,
        "per_session": sessions,
        "hourly": hourly,
    }


def print_report(data: dict) -> None:
    t = data["totals"]
    print(f"Since: {data['since']}")
    print(f"Calls: {t['calls']}  OK: {t['ok']}  Failed: {t['failed']}  Cost: ${t['cost_usd']}")
    print()
    print(f"{'Script':<40} {'Calls':>6} {'OK':>6} {'Fail':>5} {'Cost':>8} {'Avg ms':>7} {'Q/call':>6} {'Cache':>5}")
    print("-" * 90)
    for s in data["per_script"]:
        print(
            f"{s['script']:<40} {s['calls']:>6} {s['ok'] or 0:>6} {s['failed']:>5} "
            f"${s['cost_usd']:>7} {s['avg_ms'] or 0:>7.0f} {s['avg_q'] or 0:>6.1f} {s['cache_hits'] or 0:>5}"
        )
    if data["errors"]:
        print(f"\nErrors:")
        for e in data["errors"]:
            print(f"  {e['error']}: {e['n']} calls")
    if data.get("fixed_overhead"):
        print("\nFixed Overhead (upper bound on question-text cost):")
        print(f"  {'Script':<40} {'Min Tok':>8} {'Non-cached':>10} {'Overhead':>10} {'Total':>10} {'Pct':>6}")
        print(f"  {'-' * 88}")
        for o in data["fixed_overhead"]:
            print(
                f"  {o['script']:<40} {o['min_input_tok']:>8} {o['non_cached_calls']:>10} "
                f"{o['overhead_tok']:>10} {o['total_tok']:>10} {o['overhead_pct']:>5.1f}%"
            )
    if data["duplicates"]:
        print("\nTop duplicates (same payload hash):")
        for d in data["duplicates"]:
            print(f"  {d['payload_hash']} x{d['times']} ({d['script']})")
    if data.get("per_session"):
        print("\nPer Session:")
        print(f"  {'Session':<16} {'Calls':>6} {'OK':>6} {'Failed':>6} {'Scripts':>7} {'Cost':>8}")
        print(f"  {'-' * 54}")
        for s in data["per_session"]:
            sid = (s["session_id"] or "?")[:14]
            print(
                f"  {sid:<16} {s['calls']:>6} {s['ok'] or 0:>6} {s['failed']:>6} {s['scripts']:>7} ${s['cost_usd']:>7}"
            )


def ingest_plugin_calls() -> None:
    """Load the compaction plugin's Jev requests into ``jev_calls`` first.

    The plugin runs in a sandbox that cannot write the database, so it records
    each request in its own store. Best-effort: a failure leaves the report to
    run on what the database already holds.
    """
    script = Path(__file__).resolve().parent / "jev-compact-evidence.py"
    try:
        subprocess.run([sys.executable, str(script), "--ingest"], capture_output=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        pass


def main() -> int:
    ap = argparse.ArgumentParser(description="Jev cost and efficiency report")
    ap.add_argument("--since", default="24h", help="Time window: 24h, 7d, 30d, or ISO date")
    ap.add_argument("--json", action="store_true", help="JSON output")
    args = ap.parse_args()
    ingest_plugin_calls()
    data = report(args.since)
    if args.json:
        print(json.dumps(data, indent=2, default=str))
    else:
        print_report(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
