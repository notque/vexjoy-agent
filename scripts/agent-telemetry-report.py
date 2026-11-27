#!/usr/bin/env python3
"""Multi-provider agent telemetry warehouse and diagnostic report.

Ingests session logs from Claude Code/Desktop (top-level + subagents), Codex
(state_5.sqlite + rollout JSONLs), Antigravity (brain transcripts), and local
VexJoy governance/error stores into an incremental SQLite warehouse, then runs
deterministic structural diagnostics and prints a provider/model scorecard.

Stdlib only. Read-only on all provider session files; writes only to the
warehouse SQLite database (default: ~/.claude/learning/agent_telemetry.db).

Usage:
    python3 scripts/agent-telemetry-report.py --days 7 --all-providers
    python3 scripts/agent-telemetry-report.py --days 40 --all-providers --json
    python3 scripts/agent-telemetry-report.py --days 7 --provider claude --md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# API-equivalent USD per 1M tokens: (input, output, cache_read, cache_5m, cache_1h)
_PRICING_PER_M: dict[str, tuple[float, float, float, float, float]] = {
    "opus": (5.0, 25.0, 0.5, 6.25, 10.0),
    "fable": (15.0, 75.0, 1.5, 18.75, 30.0),
    "sonnet": (3.0, 15.0, 0.3, 3.75, 6.0),
    "haiku": (0.8, 4.0, 0.08, 1.0, 1.6),
    "gpt": (2.5, 10.0, 0.25, 2.5, 2.5),
    "gemini": (1.25, 5.0, 0.125, 1.25, 1.25),
}

_IMG_PATH_RE = re.compile(r"(?:[A-Za-z]:[/\\]|/)?[\w./\\-]+\.(?:png|jpe?g|webp|mp4)\b", re.I)
_VISUAL_OK_RE = re.compile(
    r"\b(?:looks good|checked the frames|clean on screen|visually verified|verified visually)\b", re.I
)
_MANUAL_DEFLECT_RE = re.compile(
    r"\b(?:run this in powershell|paste this(?: one)? command|delete (?:it|them) yourself|"
    r"free (?:the )?space yourself|i don't permanently delete)\b",
    re.I,
)
_STANDING_RULE_RE = re.compile(r"\b(?:saved (?:this |it |that )?as a standing rule|now a standing rule)\b", re.I)
_HARNESS_BLOCK_RE = re.compile(
    r"blocked:\s*sleep|not allowed in subagents|update_plan|wrap_up|permission check blocked",
    re.I,
)
_GIT_C_COMMIT_RE = re.compile(r"\bgit\s+-C\s+\S+.*\bcommit\b", re.I)
_BYPASS_ENV_RE = re.compile(r"\b[A-Z0-9_]+_(?:BYPASS|SKIP|DISABLE)=1\b")


def _long_path(path: Path) -> str:
    """Return a Windows extended-length path string when needed to bypass MAX_PATH."""
    raw = str(path.resolve()) if not str(path).startswith("\\\\?\\") else str(path)
    if os.name == "nt" and len(raw) >= 240 and not raw.startswith("\\\\?\\"):
        return "\\\\?\\" + raw
    return raw


def _model_family(model: str) -> str:
    m = (model or "").lower()
    if "fable" in m:
        return "fable"
    if "opus" in m:
        return "opus"
    if "sonnet" in m:
        return "sonnet"
    if "haiku" in m:
        return "haiku"
    if "gpt" in m or "codex" in m or "o3" in m or "o4" in m:
        return "gpt"
    if "gemini" in m or "argon" in m or "flash" in m:
        return "gemini"
    return "other"


def _estimate_cost(
    model: str,
    input_tok: int,
    output_tok: int,
    cache_read: int,
    cache_5m: int,
    cache_1h: int,
) -> float:
    rates = _PRICING_PER_M.get(_model_family(model), (3.0, 15.0, 0.3, 3.75, 6.0))
    return (
        input_tok * rates[0] + output_tok * rates[1] + cache_read * rates[2] + cache_5m * rates[3] + cache_1h * rates[4]
    ) / 1_000_000.0


def _iso_to_epoch(ts: object) -> float:
    if isinstance(ts, (int, float)):
        return float(ts) / 1000.0 if float(ts) > 1e12 else float(ts)
    if not isinstance(ts, str) or not ts.strip():
        return 0.0
    s = ts.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except ValueError:
        return 0.0


def _init_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path), timeout=10.0)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=5000")
    con.execute("PRAGMA synchronous=NORMAL")
    try:
        os.chmod(db_path, 0o600)
    except OSError:
        pass
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS ingested_files (
            path TEXT PRIMARY KEY,
            provider TEXT NOT NULL,
            mtime REAL NOT NULL,
            size INTEGER NOT NULL,
            ingested_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS turns (
            turn_key TEXT PRIMARY KEY,
            provider TEXT NOT NULL,
            session_id TEXT NOT NULL,
            parent_session_id TEXT,
            is_subagent INTEGER NOT NULL DEFAULT 0,
            ts REAL NOT NULL,
            model TEXT NOT NULL,
            effort TEXT NOT NULL DEFAULT '',
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            cache_read_tokens INTEGER NOT NULL DEFAULT 0,
            cache_5m_tokens INTEGER NOT NULL DEFAULT 0,
            cache_1h_tokens INTEGER NOT NULL DEFAULT 0,
            est_cost_usd REAL NOT NULL DEFAULT 0.0
        );
        CREATE INDEX IF NOT EXISTS idx_turns_ts ON turns(ts);
        CREATE INDEX IF NOT EXISTS idx_turns_provider ON turns(provider, model);
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_path TEXT NOT NULL,
            provider TEXT NOT NULL,
            session_id TEXT NOT NULL,
            ts REAL NOT NULL,
            kind TEXT NOT NULL,
            detail TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_signals_ts ON signals(ts);
        CREATE INDEX IF NOT EXISTS idx_signals_source ON signals(source_path);
        """
    )
    return con


def _file_unchanged(con: sqlite3.Connection, path_key: str, mtime: float, size: int) -> bool:
    row = con.execute("SELECT mtime, size FROM ingested_files WHERE path = ?", (path_key,)).fetchone()
    return row is not None and abs(row["mtime"] - mtime) < 1e-3 and row["size"] == size


def _mark_ingested(con: sqlite3.Connection, path_key: str, provider: str, mtime: float, size: int) -> None:
    con.execute(
        "INSERT OR REPLACE INTO ingested_files(path, provider, mtime, size, ingested_at) VALUES (?, ?, ?, ?, ?)",
        (path_key, provider, mtime, size, time.time()),
    )


def _norm_sentence(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9? ]+", " ", text.lower())).strip()


def _detect_session_signals(
    source_path: str,
    provider: str,
    session_id: str,
    assistant_texts: list[tuple[float, str]],
    tool_events: list[tuple[float, str, dict[str, Any], bool, str]],
) -> list[tuple[str, str, str, float, str, str]]:
    """Run deterministic structural detectors over one session's events."""
    found: list[tuple[str, str, str, float, str, str]] = []

    # 1. Repeated question / prompt spam (>=3x identical normalized question sentence)
    q_counts: Counter[str] = Counter()
    q_last_ts: dict[str, float] = {}
    for ts, txt in assistant_texts:
        seen_in_msg: set[str] = set()
        for part in re.split(r"[\n.!]+", txt):
            if "?" in part:
                norm = _norm_sentence(part)
                if len(norm) >= 24 and norm not in seen_in_msg:
                    seen_in_msg.add(norm)
                    q_counts[norm] += 1
                    q_last_ts[norm] = ts
        if _MANUAL_DEFLECT_RE.search(txt):
            found.append((source_path, provider, session_id, ts, "manual_command_deflection", txt[:140]))
        if _STANDING_RULE_RE.search(txt):
            found.append((source_path, provider, session_id, ts, "standing_rule_claim", txt[:140]))

    for norm, cnt in q_counts.items():
        if cnt >= 3:
            found.append(
                (source_path, provider, session_id, q_last_ts[norm], "repeat_question_spam", f"{cnt}x: {norm[:100]}")
            )

    # 2. Tool-based structural checks
    read_files: set[str] = set()
    edit_counts: Counter[str] = Counter()
    edit_last_ts: dict[str, float] = {}
    last_git_deny_ts = -1.0

    for ts, tname, tinput, is_err, out_txt in tool_events:
        if tname in ("Read", "read_file"):
            fp = str(tinput.get("file_path") or tinput.get("Path") or "")
            if fp:
                read_files.add(os.path.basename(fp).lower())
        elif tname in ("Write", "Edit", "MultiEdit", "write_file", "edit_file"):
            fp = str(tinput.get("file_path") or tinput.get("Path") or "")
            if fp:
                edit_counts[fp] += 1
                edit_last_ts[fp] = ts
                norm_fp = fp.replace("\\", "/").lower()
                if "/.claude/projects/" in norm_fp and "/memory/" in norm_fp and norm_fp.endswith(".md"):
                    found.append((source_path, provider, session_id, ts, "memory_file_write", os.path.basename(fp)))
        elif tname in ("Bash", "run_command"):
            cmd = str(tinput.get("command") or tinput.get("CommandLine") or "")
            if is_err and any(k in out_txt.lower() for k in ("branch-safety", "security-review", "review-before-push")):
                last_git_deny_ts = ts
            elif (
                last_git_deny_ts > 0
                and 0 <= (ts - last_git_deny_ts) <= 300
                and (_GIT_C_COMMIT_RE.search(cmd) or _BYPASS_ENV_RE.search(cmd))
            ):
                found.append((source_path, provider, session_id, ts, "hook_bypass_pair", cmd[:120]))

        if is_err and _HARNESS_BLOCK_RE.search(out_txt):
            found.append((source_path, provider, session_id, ts, "harness_tool_block", f"{tname}: {out_txt[:100]}"))

    # 3. File edit oscillation (>=6 edits to same file in one session)
    for fp, cnt in edit_counts.items():
        if cnt >= 6:
            found.append(
                (
                    source_path,
                    provider,
                    session_id,
                    edit_last_ts.get(fp, 0.0),
                    "file_oscillation",
                    f"{cnt}x edits: {os.path.basename(fp)}",
                )
            )

    # 4. Uninspected visual claims
    for ts, txt in assistant_texts:
        if _VISUAL_OK_RE.search(txt):
            for img in _IMG_PATH_RE.findall(txt):
                base = os.path.basename(img).lower()
                if base and base not in read_files:
                    found.append((source_path, provider, session_id, ts, "uninspected_visual_claim", base))
                    break

    return found


def _ingest_claude(con: sqlite3.Connection, claude_projects: Path, cutoff_epoch: float) -> int:
    if not claude_projects.is_dir():
        return 0
    files: list[Path] = []
    for root, _dirs, fnames in os.walk(_long_path(claude_projects)):
        for fn in fnames:
            if fn.endswith(".jsonl"):
                files.append(Path(root) / fn)

    ingested = 0
    for fpath in files:
        lp = _long_path(fpath)
        try:
            st = os.stat(lp)
        except OSError:
            continue
        if st.st_mtime < cutoff_epoch:
            continue
        path_key = str(fpath)
        if _file_unchanged(con, path_key, st.st_mtime, st.st_size):
            continue

        is_sub = "subagents" in fpath.parts
        session_id = fpath.stem
        parent_id = fpath.parent.parent.name if is_sub else None

        by_msg: dict[str, dict[str, Any]] = {}
        assistant_texts: list[tuple[float, str]] = []
        pending_tools: dict[str, tuple[float, str, dict[str, Any]]] = {}
        tool_events: list[tuple[float, str, dict[str, Any], bool, str]] = []
        last_effort = ""

        try:
            with open(lp, encoding="utf-8", errors="replace") as fh:
                for raw in fh:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        obj = json.loads(raw)
                    except ValueError:
                        continue
                    if not isinstance(obj, dict):
                        continue
                    ts = _iso_to_epoch(obj.get("timestamp"))
                    eff = obj.get("effort") or obj.get("perTurnEffort") or ""
                    if isinstance(eff, str) and eff:
                        last_effort = eff
                    msg = obj.get("message")
                    if not isinstance(msg, dict):
                        continue
                    role = msg.get("role") or obj.get("type")
                    content = msg.get("content")

                    if role == "assistant":
                        mid = str(msg.get("id") or f"{session_id}:{ts}:{len(by_msg)}")
                        model = str(msg.get("model") or "")
                        usage = msg.get("usage") if isinstance(msg.get("usage"), dict) else {}
                        if model and usage:
                            cc_detail = (
                                usage.get("cache_creation") if isinstance(usage.get("cache_creation"), dict) else {}
                            )
                            c5 = int(cc_detail.get("ephemeral_5m_input_tokens") or 0)
                            c1 = int(cc_detail.get("ephemeral_1h_input_tokens") or 0)
                            if c5 == 0 and c1 == 0:
                                c5 = int(usage.get("cache_creation_input_tokens") or 0)
                            inp = int(usage.get("input_tokens") or 0)
                            out = int(usage.get("output_tokens") or 0)
                            cr = int(usage.get("cache_read_input_tokens") or 0)
                            turn_eff = str(obj.get("effort") or obj.get("perTurnEffort") or last_effort or "")
                            by_msg[mid] = {
                                "ts": ts or st.st_mtime,
                                "model": model,
                                "effort": turn_eff,
                                "in": inp,
                                "out": out,
                                "cr": cr,
                                "c5": c5,
                                "c1": c1,
                            }
                        if isinstance(content, list):
                            txt_parts = []
                            for blk in content:
                                if not isinstance(blk, dict):
                                    continue
                                if blk.get("type") == "text" and isinstance(blk.get("text"), str):
                                    txt_parts.append(blk["text"])
                                elif blk.get("type") == "tool_use":
                                    tid = str(blk.get("id") or "")
                                    tname = str(blk.get("name") or "")
                                    tinput = blk.get("input") if isinstance(blk.get("input"), dict) else {}
                                    if tid:
                                        pending_tools[tid] = (ts or st.st_mtime, tname, tinput)
                            if txt_parts:
                                assistant_texts.append((ts or st.st_mtime, "\n".join(txt_parts)))
                    elif role == "user" and isinstance(content, list):
                        for blk in content:
                            if not isinstance(blk, dict) or blk.get("type") != "tool_result":
                                continue
                            tid = str(blk.get("tool_use_id") or "")
                            is_err = bool(blk.get("is_error"))
                            out_val = blk.get("content")
                            out_txt = out_val if isinstance(out_val, str) else json.dumps(out_val or "")[:200]
                            tts, tname, tinput = pending_tools.pop(tid, (ts or st.st_mtime, "unknown", {}))
                            tool_events.append((tts, tname, tinput, is_err, out_txt[:300]))
        except OSError:
            continue

        # Flush remaining tool calls with no error result
        for tts, tname, tinput in pending_tools.values():
            tool_events.append((tts, tname, tinput, False, ""))

        con.execute("DELETE FROM signals WHERE source_path = ?", (path_key,))
        rows = []
        for mid, rec in by_msg.items():
            cost = _estimate_cost(rec["model"], rec["in"], rec["out"], rec["cr"], rec["c5"], rec["c1"])
            rows.append(
                (
                    f"claude:{mid}",
                    "claude",
                    session_id,
                    parent_id,
                    1 if is_sub else 0,
                    rec["ts"],
                    rec["model"],
                    rec["effort"],
                    rec["in"],
                    rec["out"],
                    rec["cr"],
                    rec["c5"],
                    rec["c1"],
                    cost,
                )
            )
        if rows:
            con.executemany(
                """INSERT OR REPLACE INTO turns(
                    turn_key, provider, session_id, parent_session_id, is_subagent,
                    ts, model, effort, input_tokens, output_tokens,
                    cache_read_tokens, cache_5m_tokens, cache_1h_tokens, est_cost_usd
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )

        sigs = _detect_session_signals(path_key, "claude", session_id, assistant_texts, tool_events)
        if sigs:
            con.executemany(
                "INSERT INTO signals(source_path, provider, session_id, ts, kind, detail) VALUES (?, ?, ?, ?, ?, ?)",
                sigs,
            )
        _mark_ingested(con, path_key, "claude", st.st_mtime, st.st_size)
        ingested += 1
    return ingested


def _ingest_codex(con: sqlite3.Connection, codex_dir: Path, cutoff_epoch: float) -> int:
    if not codex_dir.is_dir():
        return 0
    ingested = 0
    state_db = codex_dir / "state_5.sqlite"
    if state_db.is_file():
        st = state_db.stat()
        key = str(state_db)
        if not _file_unchanged(con, key, st.st_mtime, st.st_size):
            try:
                src = sqlite3.connect(f"file:{state_db}?mode=ro", uri=True)
                src.row_factory = sqlite3.Row
                rows = []
                for r in src.execute(
                    "SELECT id, created_at, updated_at, source, model_provider, tokens_used FROM threads WHERE updated_at >= ?",
                    (int(cutoff_epoch),),
                ).fetchall():
                    tok = int(r["tokens_used"] or 0)
                    src_str = str(r["source"] or "")
                    is_sub = 1 if "subagent" in src_str else 0
                    model = f"{r['model_provider'] or 'openai'}:codex"
                    cost = _estimate_cost("gpt", int(tok * 0.85), int(tok * 0.15), 0, 0, 0)
                    rows.append(
                        (
                            f"codex-thread:{r['id']}",
                            "codex",
                            str(r["id"]),
                            None,
                            is_sub,
                            float(r["updated_at"] or r["created_at"] or 0),
                            model,
                            "",
                            tok,
                            0,
                            0,
                            0,
                            0,
                            cost,
                        )
                    )
                src.close()
                if rows:
                    con.executemany(
                        """INSERT OR REPLACE INTO turns(
                            turn_key, provider, session_id, parent_session_id, is_subagent,
                            ts, model, effort, input_tokens, output_tokens,
                            cache_read_tokens, cache_5m_tokens, cache_1h_tokens, est_cost_usd
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        rows,
                    )
                _mark_ingested(con, key, "codex", st.st_mtime, st.st_size)
                ingested += 1
            except sqlite3.Error:
                pass
    return ingested


def _ingest_antigravity(con: sqlite3.Connection, ag_brain: Path, cutoff_epoch: float) -> int:
    if not ag_brain.is_dir():
        return 0
    ingested = 0
    for tr in ag_brain.glob("*/.system_generated/logs/transcript.jsonl"):
        try:
            st = tr.stat()
        except OSError:
            continue
        if st.st_mtime < cutoff_epoch:
            continue
        path_key = str(tr)
        if _file_unchanged(con, path_key, st.st_mtime, st.st_size):
            continue
        conv_id = tr.parent.parent.parent.name
        rows = []
        try:
            with tr.open(encoding="utf-8", errors="replace") as fh:
                for idx, raw in enumerate(fh):
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        obj = json.loads(raw)
                    except ValueError:
                        continue
                    model = str(obj.get("model") or "")
                    if not model:
                        continue
                    inp = int(obj.get("input_tokens") or 0)
                    out = int(obj.get("output_tokens") or 0)
                    cr = int(obj.get("cache_read_tokens") or 0)
                    ts = _iso_to_epoch(obj.get("created_at")) or st.st_mtime
                    cost = _estimate_cost(model, inp, out, cr, 0, 0)
                    rows.append(
                        (
                            f"ag:{conv_id}:{obj.get('step_index', idx)}",
                            "antigravity",
                            conv_id,
                            None,
                            0,
                            ts,
                            model,
                            "",
                            inp,
                            out,
                            cr,
                            0,
                            0,
                            cost,
                        )
                    )
        except OSError:
            continue
        if rows:
            con.executemany(
                """INSERT OR REPLACE INTO turns(
                    turn_key, provider, session_id, parent_session_id, is_subagent,
                    ts, model, effort, input_tokens, output_tokens,
                    cache_read_tokens, cache_5m_tokens, cache_1h_tokens, est_cost_usd
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )
        _mark_ingested(con, path_key, "antigravity", st.st_mtime, st.st_size)
        ingested += 1
    return ingested


def _read_hook_health(learning_dir: Path, cutoff_iso: str, cutoff_local_iso: str | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"governance_blocks": {}, "hook_crashes": {}}
    ldb = learning_dir / "learning.db"
    gov_cutoff = cutoff_local_iso or cutoff_iso
    if ldb.is_file():
        try:
            src = sqlite3.connect(f"file:{ldb}?mode=ro", uri=True)
            for hook, payload_s, cnt in src.execute(
                "SELECT event_type, payload, COUNT(*) FROM governance_events WHERE blocked=1 AND created_at >= ? GROUP BY event_type, payload",
                (gov_cutoff,),
            ).fetchall():
                key = str(hook)
                try:
                    pl = json.loads(payload_s) if payload_s else {}
                    if isinstance(pl, dict) and pl.get("hook"):
                        key = str(pl["hook"]) + (f":{pl['sub_rule']}" if pl.get("sub_rule") else "")
                except ValueError:
                    pass
                out["governance_blocks"][key] = out["governance_blocks"].get(key, 0) + int(cnt)
            src.close()
        except sqlite3.Error:
            pass

    err_log = learning_dir / "hook-errors.jsonl"
    if err_log.is_file():
        crashes: Counter[str] = Counter()
        try:
            with err_log.open(encoding="utf-8", errors="replace") as fh:
                for raw in fh:
                    try:
                        obj = json.loads(raw)
                    except ValueError:
                        continue
                    if str(obj.get("ts") or "") >= cutoff_iso:
                        crashes[f"{obj.get('hook', '?')}:{obj.get('type', '?')}"] += 1
        except OSError:
            pass
        out["hook_crashes"] = dict(crashes.most_common(15))
    return out


def build_report(
    db_path: Path,
    *,
    days: int = 7,
    providers: tuple[str, ...] = ("claude", "codex", "antigravity"),
    claude_projects: Path | None = None,
    codex_dir: Path | None = None,
    ag_brain: Path | None = None,
    learning_dir: Path | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    cutoff_dt = now - timedelta(days=days)
    cutoff_epoch = cutoff_dt.timestamp()
    cutoff_iso = cutoff_dt.isoformat()

    con = _init_db(db_path)
    ingested_counts = {}
    if "claude" in providers:
        ingested_counts["claude"] = _ingest_claude(
            con, claude_projects or (Path.home() / ".claude" / "projects"), cutoff_epoch
        )
    if "codex" in providers:
        ingested_counts["codex"] = _ingest_codex(con, codex_dir or (Path.home() / ".codex"), cutoff_epoch)
    if "antigravity" in providers:
        ingested_counts["antigravity"] = _ingest_antigravity(
            con, ag_brain or (Path.home() / ".gemini" / "antigravity" / "brain"), cutoff_epoch
        )
    con.commit()

    placeholders = ",".join("?" for _ in providers)
    scorecard = []
    for r in con.execute(
        f"""
        SELECT provider, model,
               COUNT(*) AS turns,
               SUM(is_subagent) AS subagent_turns,
               SUM(input_tokens) AS in_tok,
               SUM(output_tokens) AS out_tok,
               SUM(cache_read_tokens) AS cr_tok,
               SUM(cache_5m_tokens + cache_1h_tokens) AS cc_tok,
               ROUND(SUM(est_cost_usd), 2) AS est_cost
        FROM turns
        WHERE ts >= ? AND provider IN ({placeholders})
        GROUP BY provider, model
        ORDER BY est_cost DESC
        """,
        (cutoff_epoch, *providers),
    ).fetchall():
        scorecard.append(dict(r))

    effort_breakdown = [
        dict(r)
        for r in con.execute(
            f"""
            SELECT provider, COALESCE(NULLIF(effort, ''), 'unset') AS effort,
                   COUNT(*) AS turns, ROUND(SUM(est_cost_usd), 2) AS est_cost
            FROM turns
            WHERE ts >= ? AND provider IN ({placeholders})
            GROUP BY provider, effort
            ORDER BY est_cost DESC
            """,
            (cutoff_epoch, *providers),
        ).fetchall()
    ]

    # Effort runaway sessions (>10% xhigh/max with >=20 calls)
    effort_runaways = [
        dict(r)
        for r in con.execute(
            f"""
            SELECT provider, session_id, COUNT(*) AS turns,
                   SUM(CASE WHEN effort IN ('xhigh', 'max') THEN 1 ELSE 0 END) AS high_effort_turns,
                   ROUND(SUM(est_cost_usd), 2) AS est_cost
            FROM turns
            WHERE ts >= ? AND provider IN ({placeholders})
            GROUP BY provider, session_id
            HAVING turns >= 20 AND (1.0 * high_effort_turns / turns) > 0.10
            ORDER BY est_cost DESC
            LIMIT 15
            """,
            (cutoff_epoch, *providers),
        ).fetchall()
    ]

    signal_counts = {
        r["kind"]: r["cnt"]
        for r in con.execute(
            f"SELECT kind, COUNT(*) AS cnt FROM signals WHERE ts >= ? AND provider IN ({placeholders}) GROUP BY kind ORDER BY cnt DESC",
            (cutoff_epoch, *providers),
        ).fetchall()
    }
    con.close()

    default_learning = Path(os.environ.get("CLAUDE_LEARNING_DIR") or (Path.home() / ".claude" / "learning"))
    cutoff_local_iso = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
    health = _read_hook_health(learning_dir or default_learning, cutoff_iso, cutoff_local_iso)
    return {
        "window_days": days,
        "since_utc": cutoff_iso,
        "providers": list(providers),
        "files_ingested_this_run": ingested_counts,
        "scorecard": scorecard,
        "effort_breakdown": effort_breakdown,
        "effort_runaways": effort_runaways,
        "structural_signals": signal_counts,
        "hook_health": health,
    }


def format_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Agent Telemetry Report (last {report['window_days']}d)",
        "",
        "## Provider / Model Scorecard",
        "| Provider | Model | Turns | Subagent | Output Tok | Cache Read | Est USD |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in report["scorecard"]:
        lines.append(
            f"| {row['provider']} | `{row['model']}` | {row['turns']} | {row['subagent_turns']} | "
            f"{row['out_tok']:,} | {row['cr_tok']:,} | ${row['est_cost']:.2f} |"
        )
    if report["effort_breakdown"]:
        lines.extend(["", "## Effort Breakdown", "| Provider | Effort | Turns | Est USD |", "|---|---|---:|---:|"])
        for row in report["effort_breakdown"]:
            lines.append(f"| {row['provider']} | `{row['effort']}` | {row['turns']} | ${row['est_cost']:.2f} |")
    if report["structural_signals"]:
        lines.extend(["", "## Structural Signals", "| Signal | Count |", "|---|---:|"])
        for k, v in report["structural_signals"].items():
            lines.append(f"| `{k}` | {v} |")
    crashes = report["hook_health"].get("hook_crashes") or {}
    if crashes:
        lines.extend(["", "## Hook Crash Hotspots", "| Hook:Exception | Count |", "|---|---:|"])
        for k, v in list(crashes.items())[:10]:
            lines.append(f"| `{k}` | {v} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Multi-provider agent telemetry and diagnostic report.")
    parser.add_argument("--days", type=int, default=7, help="Lookback window in days (default: 7)")
    parser.add_argument("--all-providers", action="store_true", help="Include claude, codex, and antigravity")
    parser.add_argument("--provider", choices=("claude", "codex", "antigravity"), default=None)
    default_db = (
        Path(os.environ.get("CLAUDE_LEARNING_DIR") or (Path.home() / ".claude" / "learning")) / "agent_telemetry.db"
    )
    parser.add_argument("--db", type=Path, default=default_db)
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--md", action="store_true", help="Output Markdown (default)")
    args = parser.parse_args()

    if args.provider:
        providers = (args.provider,)
    elif args.all_providers:
        providers = ("claude", "codex", "antigravity")
    else:
        providers = ("claude", "codex", "antigravity")

    report = build_report(args.db, days=args.days, providers=providers)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_markdown(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
