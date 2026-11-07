#!/usr/bin/env python3
"""Tests for the session-summary Stop hook.

Run with: python3 -m pytest hooks/tests/test_session_summary.py -v
"""

from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

HOOK_PATH = Path(__file__).resolve().parent.parent / "session-summary.py"

spec = importlib.util.spec_from_file_location("session_summary", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def _run(monkeypatch: pytest.MonkeyPatch, event: dict) -> None:
    monkeypatch.setattr(mod, "read_stdin", lambda **_kwargs: json.dumps(event))
    with pytest.raises(SystemExit) as exit_info:
        mod.main()
    assert exit_info.value.code == 0


def test_session_row_is_keyed_on_the_event_session_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """Claude Code sends session_id on stdin and never sets CLAUDE_SESSION_ID (B-04)."""
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    recorded: list[str] = []
    monkeypatch.setattr(mod, "record_session", lambda session_id, **_kwargs: recorded.append(session_id))
    monkeypatch.setattr(mod, "get_stats", lambda: {})

    _run(monkeypatch, {"hook_event_name": "Stop", "session_id": "sess-stop-1"})

    assert recorded == ["sess-stop-1"]


def test_repeated_stops_update_one_session_row(monkeypatch: pytest.MonkeyPatch, isolate_learning_db: Path) -> None:
    """Every turn ends in a Stop event; one session must stay one learning.db row."""
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    for _ in range(3):
        _run(monkeypatch, {"hook_event_name": "Stop", "session_id": "sess-stop-2"})

    with sqlite3.connect(isolate_learning_db / "learning.db") as conn:
        rows = conn.execute("SELECT session_id FROM sessions").fetchall()
    assert rows == [("sess-stop-2",)]
