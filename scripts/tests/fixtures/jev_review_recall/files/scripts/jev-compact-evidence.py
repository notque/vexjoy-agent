#!/usr/bin/env python3
"""Compaction evidence: ingest claims and engine records, then report.

Three sources land in learning.db `compaction_events`:

- `plugin`: what jev-auto-compact says it did (JSONL ring buffer written by
  the function-hook plugin, which has no sqlite).
- `precompact-hook`: what the Python PreCompact hook computed as guidance.
- `transcript`: the engine's own `compact_boundary` rows (preTokens,
  postTokens, durationMs). This is the ground truth: the plugin claims, the
  transcript confirms.

`session_usage` holds the per-turn context-window samples the plugin takes.

Usage:
    python3 scripts/jev-compact-evidence.py            # ingest + report
    python3 scripts/jev-compact-evidence.py --ingest   # ingest only (hooks)
    python3 scripts/jev-compact-evidence.py --report --last 30
    python3 scripts/jev-compact-evidence.py --session <id>
    python3 scripts/jev-compact-evidence.py --transcript <path>   # one file
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

_HOOKS_LIB = Path(__file__).resolve().parents[1] / "hooks" / "lib"
if str(_HOOKS_LIB) not in sys.path:
    sys.path.insert(0, str(_HOOKS_LIB))

import learning_db_v2 as ldb

JSONL_NAME = "compaction-events.jsonl"
# The plugin keeps its evidence in its own $.store: a JSON file the engine
# writes under ~/.claude/plugins. Its exact name is the engine's; find it by
# content (an "events" array of records that carry kind/session_id/ts).
STORE_ROOT = Path.home() / ".claude" / "plugins"
STORE_KEY = "events"
TRANSCRIPT_ROOT = Path.home() / ".claude" / "projects"
TRANSCRIPT_MAX_AGE_DAYS = 3
# A compaction the engine finished this fast had no LLM summarizer in it.
FAST_ENGINE_MS = 5000
# Plugin claim and transcript record of the same compaction land within this window.
MATCH_WINDOW_S = 20.0


def _jsonl_path() -> Path:
    return ldb.get_db_dir() / JSONL_NAME


def _parse_ts(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


# ─── Ingest ───────────────────────────────────────────────────────


def _insert_record(rec: object) -> bool:
    """Insert one plugin record (compaction claim or usage sample). False when skipped."""
    if not isinstance(rec, dict) or not rec.get("session_id") or not rec.get("ts"):
        return False
    kind = rec.get("kind")
    try:
        if kind == "compaction":
            ok = ldb.record_compaction_event(
                session_id=rec["session_id"],
                ts=rec["ts"],
                source=rec.get("source") or "plugin",
                trigger=rec.get("trigger"),
                engine=rec.get("engine"),
                agent_id=rec.get("agent_id"),
                reduction_ratio=rec.get("reduction_ratio"),
                note=rec.get("note"),
                **{k: rec.get(k) for k in ldb._COMPACTION_INT_FIELDS},
            )
        elif kind == "usage":
            ok = ldb.record_session_usage(
                session_id=rec["session_id"],
                ts=rec["ts"],
                phase=rec.get("phase") or "turn_complete",
                turn=rec.get("turn"),
                context_tokens=rec.get("context_tokens"),
                context_window=rec.get("context_window"),
                context_percent=rec.get("context_percent"),
                cost_usd=rec.get("cost_usd"),
            )
        else:
            return False
    except Exception:
        return False
    return bool(ok)


def ingest_jsonl(path: Path | None = None) -> int:
    """Load plugin claims from the legacy JSONL ring buffer. Returns rows newly inserted."""
    path = path or _jsonl_path()
    if not path.exists():
        return 0
    inserted = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        inserted += 1 if _insert_record(rec) else 0
    return inserted


def _store_files(root: Path = STORE_ROOT) -> list[Path]:
    """Plugin store files that hold our evidence array, found by content."""
    hits: list[Path] = []
    if not root.exists():
        return hits
    for path in root.rglob("*.json"):
        if "jev-auto-compact" not in str(path):
            continue
        try:
            if path.stat().st_size > 8_000_000:
                continue
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(data, dict) and isinstance(data.get(STORE_KEY), list):
            hits.append(path)
    return hits


def ingest_store(root: Path = STORE_ROOT) -> int:
    """Load plugin claims and usage samples from the plugin's $.store. Returns rows newly inserted."""
    inserted = 0
    for path in _store_files(root):
        try:
            events = json.loads(path.read_text(encoding="utf-8", errors="replace"))[STORE_KEY]
        except (json.JSONDecodeError, OSError, KeyError, TypeError):
            continue
        for rec in events:
            inserted += 1 if _insert_record(rec) else 0
    return inserted


def ingest_transcript(path: Path) -> int:
    """Load every compact_boundary row of one transcript. Returns rows inserted."""
    if not path.exists():
        return 0
    session_id = path.stem
    inserted = 0
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if '"compact_boundary"' not in line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("subtype") != "compact_boundary":
                continue
            meta = row.get("compactMetadata") or {}
            ts = row.get("timestamp")
            if not ts:
                continue
            duration = meta.get("durationMs")
            try:
                ok = ldb.record_compaction_event(
                    session_id=row.get("sessionId") or session_id,
                    ts=ts,
                    source="transcript",
                    trigger=meta.get("trigger"),
                    tokens_before=meta.get("preTokens"),
                    tokens_after=meta.get("postTokens"),
                    duration_ms=duration,
                    note=f"cumulativeDropped={meta.get('cumulativeDroppedTokens')}"
                    if meta.get("cumulativeDroppedTokens") is not None
                    else None,
                )
            except Exception:
                continue
            inserted += 1 if ok else 0
    return inserted


def ingest_recent_transcripts(max_age_days: float = TRANSCRIPT_MAX_AGE_DAYS) -> int:
    """Load compact_boundary rows from transcripts touched recently."""
    if not TRANSCRIPT_ROOT.exists():
        return 0
    cutoff = time.time() - max_age_days * 86400
    inserted = 0
    for path in TRANSCRIPT_ROOT.glob("*/*.jsonl"):
        try:
            if path.stat().st_mtime < cutoff:
                continue
        except OSError:
            continue
        inserted += ingest_transcript(path)
    return inserted


def ingest_all(transcript: Path | None = None) -> dict[str, int]:
    counts = {"jsonl": ingest_jsonl() + ingest_store()}
    if transcript is not None:
        counts["transcript"] = ingest_transcript(transcript)
    else:
        counts["transcript"] = ingest_recent_transcripts()
    return counts


# ─── Report ───────────────────────────────────────────────────────


_ROWS_ALL = "SELECT * FROM compaction_events ORDER BY ts DESC LIMIT ?"
_ROWS_SESSION = "SELECT * FROM compaction_events WHERE session_id = ? ORDER BY ts DESC LIMIT ?"


_CLAIMS_FOR_SESSIONS = "SELECT * FROM compaction_events WHERE source = 'plugin' AND session_id IN ({}) ORDER BY ts DESC"


def _rows(session: str | None, last: int) -> list[dict]:
    ldb.init_db()
    with ldb.get_connection() as conn:
        if session:
            cur = conn.execute(_ROWS_SESSION, (session, last))
        else:
            cur = conn.execute(_ROWS_ALL, (last,))
        return [dict(r) for r in cur.fetchall()]


def _claims_for_sessions(session_ids: set[str]) -> list[dict]:
    """Every plugin claim for these sessions, with no LIMIT window, so a
    transcript row in the report window matches a claim that fell outside it."""
    ids = sorted(s for s in session_ids if s)
    if not ids:
        return []
    ldb.init_db()
    with ldb.get_connection() as conn:
        cur = conn.execute(_CLAIMS_FOR_SESSIONS.format(",".join("?" * len(ids))), ids)
        return [dict(r) for r in cur.fetchall()]


def _classify_transcript(row: dict, claims: list[dict]) -> str:
    """Name the engine behind a transcript row from the nearest plugin claim."""
    t = _parse_ts(row["ts"])
    if t is None:
        return "?"
    best = None
    for c in claims:
        ct = _parse_ts(c["ts"])
        if ct is None or c["session_id"] != row["session_id"]:
            continue
        gap = abs(ct - t)
        if gap <= MATCH_WINDOW_S and (best is None or gap < best[0]):
            best = (gap, c)
    if best is not None:
        engine = best[1].get("engine") or "?"
        return "jev (confirmed)" if engine == "jev" else engine
    duration = row.get("duration_ms")
    if duration is not None:
        return "jev-fast" if duration < FAST_ENGINE_MS else "builtin-llm"
    return "?"


def _fmt_tokens(before, after) -> str:
    if before is None and after is None:
        return "-"
    if before is not None and after is not None and before > 0:
        delta = (after - before) / before * 100
        return f"{before:,}→{after:,} ({delta:+.0f}%)"
    return f"{before or '?'}→{after or '?'}"


def report(session: str | None, last: int) -> int:
    rows = _rows(session, last)
    if not rows:
        print("No compaction events recorded yet.")
        return 0
    claims = _claims_for_sessions({r["session_id"] for r in rows})

    print(
        f"{'time':<20} {'sid':<8} {'source':<15} {'trig':<7} {'engine':<16} {'msgs':<9} {'tokens':<30} {'ms':<8} note"
    )
    for r in rows:
        engine = r.get("engine") or ("" if r["source"] != "transcript" else _classify_transcript(r, claims))
        if r["source"] == "transcript":
            engine = _classify_transcript(r, claims)
        msgs = "-"
        if r.get("messages_before") is not None:
            msgs = f"{r['messages_before']}→{r.get('messages_after') if r.get('messages_after') is not None else '?'}"
        ms = r.get("duration_ms") if r.get("duration_ms") is not None else r.get("latency_ms")
        note = (r.get("note") or "")[:40]
        print(
            f"{(r['ts'] or '')[:19]:<20} {(r['session_id'] or '')[:8]:<8} {r['source']:<15} "
            f"{(r.get('trigger') or '-'):<7} {engine:<16} {msgs:<9} "
            f"{_fmt_tokens(r.get('tokens_before'), r.get('tokens_after')):<30} {str(ms if ms is not None else '-'):<8} {note}"
        )

    # Summary from the engine's own records.
    engine_rows = [r for r in rows if r["source"] == "transcript" and r.get("duration_ms") is not None]
    fast = [r for r in engine_rows if r["duration_ms"] < FAST_ENGINE_MS]
    slow = [r for r in engine_rows if r["duration_ms"] >= FAST_ENGINE_MS]
    dropped = sum(
        (r["tokens_before"] or 0) - (r["tokens_after"] or 0)
        for r in fast
        if r.get("tokens_before") and r.get("tokens_after") and r["tokens_before"] > r["tokens_after"]
    )
    jev_claims = [r for r in claims if r.get("engine") == "jev"]
    skipped = [r for r in claims if r.get("engine") == "skipped"]
    print()
    print(
        f"engine records: {len(engine_rows)} ({len(fast)} fast/Jev, {len(slow)} built-in LLM) | "
        f"plugin claims: {len(jev_claims)} jev, {len(skipped)} skipped | "
        f"tokens dropped by fast compactions: {dropped:,}"
    )
    if slow:
        avg = sum(r["duration_ms"] for r in slow) / len(slow)
        print(f"built-in LLM compactions averaged {avg / 1000:.0f}s each")
    return 0


# ─── CLI ──────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ingest and report Jev compaction evidence.")
    ap.add_argument("--ingest", action="store_true", help="ingest only, print counts")
    ap.add_argument("--report", action="store_true", help="report only, no ingest")
    ap.add_argument("--session", help="limit the report to one session id")
    ap.add_argument("--last", type=int, default=25, help="rows to show (default 25)")
    ap.add_argument("--transcript", type=Path, help="ingest this transcript instead of recent ones")
    ap.add_argument("--json", action="store_true", help="print ingest counts as JSON")
    args = ap.parse_args(argv)

    if not args.report:
        counts = ingest_all(args.transcript)
        if args.json:
            print(json.dumps(counts))
        elif args.ingest:
            print(f"ingested: {counts['jsonl']} plugin rows, {counts['transcript']} transcript rows")
    if args.ingest:
        return 0
    return report(args.session, args.last)


if __name__ == "__main__":
    sys.exit(main())
