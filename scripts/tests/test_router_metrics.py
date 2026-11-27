"""Tests for scripts/router-metrics.py: per-router main/dispatch share, reasons, pipeline rate, skill load."""

from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("router_metrics", REPO / "scripts" / "router-metrics.py")
rm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rm)

T0 = 1_800_000_000.0  # 2027-01-15T08:00:00Z


def _iso(epoch: float) -> str:
    from datetime import datetime, timezone

    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


def _write(tmp_path: Path) -> tuple[Path, Path]:
    events = [
        {"type": "decision", "ts": T0, "session": "a", "agent": "main", "skill": "programming", "router": "d"},
        {
            "type": "decision",
            "ts": T0 + 10,
            "session": "a",
            "agent": "general-purpose",
            "skill": "review",
            "router": "d",
            "dispatch_reason": "verifier",
            "pipeline": "comprehensive-review",
        },
        {"type": "decision", "ts": T0 + 20, "session": "b", "agent": "general-purpose", "skill": "testing"},
        {"type": "decision", "ts": T0 - 86400 * 30, "session": "c", "agent": "main", "skill": "data"},
        {"type": "outcome", "ts": T0 + 30, "session": "a", "key": "main:programming", "outcome": "success"},
        "not json",
    ]
    ev = tmp_path / "route-events.jsonl"
    ev.write_text("\n".join(e if isinstance(e, str) else json.dumps(e) for e in events) + "\n", encoding="utf-8")
    db = tmp_path / "usage.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE skill_invocations (id INTEGER PRIMARY KEY, skill_name TEXT, timestamp TEXT, session_id TEXT)"
    )
    rows = [
        ("d", _iso(T0 - 30), "a"),  # the router itself, not the routed skill
        ("programming", _iso(T0 + 5), "a"),  # main-loop load, inside the window
        ("review", _iso(T0 + 4000), "a"),  # outside the 30-minute window
        ("vexjoy:testing", _iso(T0 + 25), "b"),  # namespaced name still counts
    ]
    conn.executemany("INSERT INTO skill_invocations (skill_name, timestamp, session_id) VALUES (?, ?, ?)", rows)
    conn.commit()
    conn.close()
    return ev, db


def test_report_splits_routers_and_measures_each_metric(tmp_path: Path) -> None:
    ev, db = _write(tmp_path)
    decisions = rm.load_decisions(ev, since=T0 - 60)
    report = rm.summarize(decisions, rm.load_skill_calls(db, {d["session"] for d in decisions}))

    assert set(report) == {"d", "do"}
    d = report["d"]
    assert d["decisions"] == 2 and d["main_share"] == 0.5 and d["dispatch_share"] == 0.5
    assert d["dispatch_reasons"] == {"verifier": 1}
    assert d["pipeline_rate"] == 0.5
    assert d["skill_load"]["main"] == {"n": 1, "loaded": 1, "rate": 1.0}
    assert d["skill_load"]["dispatch"]["loaded"] == 0
    do = report["do"]
    assert do["decisions"] == 1 and do["dispatch_reasons"] == {"unstated": 1}
    assert do["skill_load"]["dispatch"]["loaded"] == 1


def test_cli_json_and_missing_sources(tmp_path: Path, capsys) -> None:
    ev, db = _write(tmp_path)
    assert rm.main(["--events", str(ev), "--usage-db", str(db), "--json"]) == 0
    assert set(json.loads(capsys.readouterr().out)) == {"d", "do"}
    assert rm.main(["--events", str(tmp_path / "none.jsonl"), "--usage-db", str(tmp_path / "none.db")]) == 0
    assert "No routing decisions" in capsys.readouterr().out
    assert rm.main(["--since", "not-a-date"]) == 2


def test_verify_followthrough_ignores_empty_session_ids() -> None:
    base = {"router": "d", "agent": "main", "skill": "x", "pipeline": None, "dispatch_reason": None}
    rows = [
        {**base, "ts": 10.0, "session": "", "d_flags": ["verify=required"]},
        {**base, "ts": 20.0, "session": "", "agent": "general-purpose", "dispatch_reason": "verifier", "d_flags": []},
        {**base, "ts": 30.0, "session": "s1", "d_flags": ["verify=required"]},
        {**base, "ts": 40.0, "session": "s1", "agent": "general-purpose", "dispatch_reason": "verifier", "d_flags": []},
    ]
    out = rm.summarize(rows, {})["d"]
    assert out["verify"] == {"required": 2, "verified": 1, "rate": 0.5}
