#!/usr/bin/env python3
"""Per-router metrics for /do and /d, from telemetry the hooks already write.

The metrics the "fold subagents into the main loop" article asks for, split by
router so /do and /d compare on the same definitions:

- decisions: routed requests (one `[do-route]` marker each)
- main_share / dispatch_share: where the work ran (`agent=main` vs a worker)
- dispatch_reasons: why a /d route left the main loop (`reason=` token)
- intent_skipped_rate: /d routes that skipped the intent validator (`intent=skipped`)
- verify: verify=required routes followed by a verifier dispatch in the same session
- pipeline_rate: share of decisions that picked a pipeline
- skill_load: did the session call the Skill tool with the routed skill

Sources (read-only, no schema change):
- `<learning dir>/route-events.jsonl` decision events (routing-decision-recorder).
  `router` is written only on /d markers, so an event without it is /do. /d
  markers carried no router token before plans/009 L6, so earlier /d routes
  count as /do: start comparisons at `--since` the install date.
- `<learning dir>/usage.db` `skill_invocations` (usage-tracker, PostToolUse:Skill).

Skill-load observability: a main-loop route's Skill call fires in the session
that recorded the route, so it is observed. A dispatched worker's Skill call
mostly does not land under the parent session (29 of 329 dispatches observed on
2026-11-17), so the dispatch figure is a lower bound and is reported apart.
Comparing a main-heavy router with a dispatch-heavy one on the pooled number
would favour the main-heavy one; compare `skill_load.main` across routers.

Usage:
    python3 scripts/router-metrics.py [--since 2026-11-17] [--json]
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# A Skill call counts for a route when it lands in this window around the
# decision: build-dispatch prints the Skill calls after the marker, so most
# follow it; the small lead absorbs clock and ordering skew.
SKILL_WINDOW_BEFORE_S = 120
SKILL_WINDOW_AFTER_S = 30 * 60


def learning_dir() -> Path:
    env = os.environ.get("CLAUDE_LEARNING_DIR")
    return Path(env) if env else Path.home() / ".claude" / "learning"


def _epoch(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    return None


def load_decisions(events_path: Path, since: float | None = None) -> list[dict]:
    rows: list[dict] = []
    try:
        lines = events_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return rows
    for line in lines:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict) or event.get("type") != "decision":
            continue
        ts = _epoch(event.get("ts"))
        if ts is None or (since is not None and ts < since):
            continue
        rows.append(
            {
                "ts": ts,
                "session": str(event.get("session") or ""),
                "router": str(event.get("router") or "do"),
                "agent": str(event.get("agent") or ""),
                "skill": str(event.get("skill") or ""),
                "pipeline": event.get("pipeline") or None,
                "dispatch_reason": event.get("dispatch_reason") or None,
                "d_flags": [str(f) for f in event.get("d_flags") or []],
            }
        )
    return rows


def load_skill_calls(usage_db: Path, sessions: set[str]) -> dict[str, list[tuple[float, str]]]:
    """session -> [(epoch, skill name)] for the given sessions. {} when the DB is absent."""
    calls: dict[str, list[tuple[float, str]]] = {}
    if not sessions or not usage_db.is_file():
        return calls
    try:
        conn = sqlite3.connect(f"file:{usage_db}?mode=ro", uri=True)
        try:
            for session, ts, name in conn.execute(
                "SELECT session_id, timestamp, skill_name FROM skill_invocations WHERE session_id IS NOT NULL"
            ):
                if session not in sessions:
                    continue
                epoch = _epoch(ts)
                if epoch is not None:
                    calls.setdefault(session, []).append((epoch, str(name or "")))
        finally:
            conn.close()
    except sqlite3.Error:
        return {}
    return calls


def _matches(called: str, routed: str) -> bool:
    called = called.strip().lower()
    return called == routed or called.endswith(":" + routed)


def skill_loaded(decision: dict, calls: dict[str, list[tuple[float, str]]]) -> bool:
    skill = decision["skill"]
    lo, hi = decision["ts"] - SKILL_WINDOW_BEFORE_S, decision["ts"] + SKILL_WINDOW_AFTER_S
    return any(lo <= ts <= hi and _matches(name, skill) for ts, name in calls.get(decision["session"], []))


def _rate(num: int, den: int) -> float | None:
    return round(num / den, 3) if den else None


def summarize(decisions: list[dict], calls: dict[str, list[tuple[float, str]]]) -> dict:
    out: dict[str, dict] = {}
    for router in sorted({d["router"] for d in decisions}):
        rows = [d for d in decisions if d["router"] == router]
        main = [d for d in rows if d["agent"] == "main"]
        dispatched = [d for d in rows if d["agent"] != "main"]
        skill_rows = {
            "main": [d for d in main if d["skill"] and d["skill"] != "-"],
            "dispatch": [d for d in dispatched if d["skill"] and d["skill"] != "-"],
        }
        skill_load = {}
        for kind, subset in skill_rows.items():
            hit = sum(skill_loaded(d, calls) for d in subset)
            skill_load[kind] = {"n": len(subset), "loaded": hit, "rate": _rate(hit, len(subset))}
        skill_load["dispatch"]["note"] = "lower bound: worker Skill calls mostly do not land under the parent session"
        out[router] = {
            "decisions": len(rows),
            "first_ts": datetime.fromtimestamp(min(d["ts"] for d in rows), timezone.utc).isoformat(),
            "last_ts": datetime.fromtimestamp(max(d["ts"] for d in rows), timezone.utc).isoformat(),
            "main_share": _rate(len(main), len(rows)),
            "dispatch_share": _rate(len(dispatched), len(rows)),
            "dispatch_reasons": dict(Counter(d["dispatch_reason"] or "unstated" for d in dispatched)),
            "pipeline_rate": _rate(sum(1 for d in rows if d["pipeline"]), len(rows)),
            "pipelines": dict(Counter(d["pipeline"] for d in rows if d["pipeline"])),
            "skill_load": skill_load,
            "intent_skipped_rate": _rate(sum(1 for d in rows if "intent=skipped" in d.get("d_flags", [])), len(rows)),
            "verify": _verify_followthrough(rows),
        }
    return out


def _verify_followthrough(rows: list[dict]) -> dict:
    """Of the routes marked verify=required, how many saw a verifier dispatch later in the same session."""
    required = [d for d in rows if "verify=required" in d.get("d_flags", [])]
    verifiers = [d for d in rows if d.get("dispatch_reason") == "verifier"]
    hit = sum(1 for r in required if any(v["session"] == r["session"] and v["ts"] >= r["ts"] for v in verifiers))
    return {"required": len(required), "verified": hit, "rate": _rate(hit, len(required))}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Per-router routing metrics for /do and /d (read-only).")
    ap.add_argument("--since", help="ISO date or datetime (UTC); only decisions at or after it")
    ap.add_argument("--events", type=Path, help="route-events.jsonl (default: <learning dir>/route-events.jsonl)")
    ap.add_argument("--usage-db", type=Path, help="usage.db (default: <learning dir>/usage.db)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    since = _epoch(args.since) if args.since else None
    if args.since and since is None:
        print(f"router-metrics: cannot parse --since {args.since!r}", file=sys.stderr)
        return 2
    base = learning_dir()
    decisions = load_decisions(args.events or base / "route-events.jsonl", since)
    calls = load_skill_calls(args.usage_db or base / "usage.db", {d["session"] for d in decisions})
    report = summarize(decisions, calls)
    if args.json:
        print(json.dumps(report, indent=2))
        return 0
    if not report:
        print("No routing decisions recorded in range.")
        return 0
    for router, m in report.items():
        print(f"/{router}: {m['decisions']} decisions ({m['first_ts'][:16]} to {m['last_ts'][:16]} UTC)")
        print(f"  main {m['main_share']} | dispatch {m['dispatch_share']} | reasons {m['dispatch_reasons']}")
        print(f"  pipeline picked {m['pipeline_rate']} {m['pipelines']}")
        v = m["verify"]
        print(
            f"  intent skipped {m['intent_skipped_rate']} | verifier after verify=required {v['verified']}/{v['required']}"
        )
        for kind in ("main", "dispatch"):
            s = m["skill_load"][kind]
            print(f"  skill loaded ({kind}): {s['loaded']}/{s['n']} ({s['rate']})")
    print("Dispatch skill-load is a lower bound; compare main-loop skill-load across routers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
