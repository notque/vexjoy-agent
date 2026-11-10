"""Governance dedup works across hook processes, and timestamps share one form.

Each hook invocation is a new process, so the old in-process dict never
suppressed anything. ``record_governance`` now derives one event id per
(session, event type, tool, hook, command head, blocked) and time window, and
the primary key drops the copy.

Run with: python3 -m pytest hooks/tests/test_hook_utils_governance_dedup.py -v
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

LIB_DIR = Path(__file__).resolve().parent.parent / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

import hook_utils
import learning_db_v2


@pytest.fixture
def gov_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    learning = tmp_path / "learning"
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(learning))
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    monkeypatch.setattr(learning_db_v2, "_initialized", False)
    monkeypatch.setattr(hook_utils, "_GOV_DEDUP", {})
    return learning / "learning.db"


def _rows(db: Path) -> list[tuple]:
    conn = sqlite3.connect(db)
    try:
        return conn.execute("SELECT id, session_id, payload, created_at FROM governance_events ORDER BY id").fetchall()
    finally:
        conn.close()


def _record(monkeypatch: pytest.MonkeyPatch, at: float, *, new_process: bool = True, **overrides: object) -> str | None:
    """Record one event at clock time ``at``. ``new_process`` drops the in-process cache first."""
    if new_process:
        monkeypatch.setattr(hook_utils, "_GOV_DEDUP", {})
    monkeypatch.setattr(hook_utils.time, "time", lambda: at)
    kwargs: dict = {
        "hook_name": "pretool-unified-gate",
        "tool_name": "Bash",
        "hook_phase": "pre",
        "severity": "high",
        "blocked": True,
        "event": {"session_id": "s1"},
        "command": "echo hi",
    }
    kwargs.update(overrides)
    return hook_utils.record_governance("hook_blocked", **kwargs)


def test_same_event_from_two_processes_is_one_row(gov_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    first = _record(monkeypatch, 1000.1)
    second = _record(monkeypatch, 1000.9)

    assert first is not None
    assert second == first, "the second process derives the id of the row already stored"
    assert len(_rows(gov_db)) == 1


def test_same_process_duplicate_returns_none(gov_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _record(monkeypatch, 1000.1) is not None
    assert _record(monkeypatch, 1000.2, new_process=False) is None
    assert len(_rows(gov_db)) == 1


def test_next_window_is_recorded(gov_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _record(monkeypatch, 1000.1)
    _record(monkeypatch, 1000.1 + hook_utils._GOV_DEDUP_WINDOW_S)

    assert len(_rows(gov_db)) == 2


@pytest.mark.parametrize(
    "overrides",
    [
        {"event": {"session_id": "s2"}},
        {"hook_name": "pretool-branch-safety"},
        {"tool_name": "Write"},
        {"command": "echo other"},
        {"blocked": False},
        {"severity": "critical"},
    ],
    ids=["session", "hook", "tool", "command", "blocked", "severity"],
)
def test_a_different_event_in_the_same_window_is_kept(
    overrides: dict, gov_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _record(monkeypatch, 1000.1)
    _record(monkeypatch, 1000.2, **overrides)

    assert len(_rows(gov_db)) == 2


def test_blocked_edits_of_two_files_in_one_window_are_two_rows(gov_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Edit and Write carry no command, so the target file is the only difference.
    for at, path in ((1000.1, "/repo/a.py"), (1000.2, "/repo/b.py"), (1000.3, "/repo/a.py")):
        _record(
            monkeypatch,
            at,
            tool_name="Edit",
            command="",
            event={"session_id": "s1", "tool_input": {"file_path": path}},
        )

    assert len(_rows(gov_db)) == 2, "a.py twice is one row; b.py is its own"


def test_event_id_keeps_the_gov_ms_hex_shape(gov_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    eid = _record(monkeypatch, 1000.1)

    assert eid is not None
    prefix, ms, digest = eid.split("-")
    assert (prefix, ms) == ("gov", "1000000")
    assert len(digest) == 16 and int(digest, 16) >= 0


_CHILD = """
import sys
sys.path.insert(0, {lib!r})
import hook_utils
hook_utils.time.time = lambda: 2000.5
print(hook_utils.record_governance(
    "hook_blocked", hook_name="h", tool_name="Bash", hook_phase="pre",
    severity="high", blocked=True, event={{"session_id": "s1"}}, command="echo hi",
))
"""


def test_real_subprocesses_dedup(gov_db: Path) -> None:
    """Three separate interpreters record the same event: one row."""
    ids = []
    for _ in range(3):
        out = subprocess.run(
            [sys.executable, "-c", _CHILD.format(lib=str(LIB_DIR))],
            capture_output=True,
            text=True,
            env=dict(os.environ),
            timeout=30,
            check=True,
        )
        ids.append(out.stdout.strip())

    assert len(set(ids)) == 1 and ids[0].startswith("gov-2000000-")
    assert len(_rows(gov_db)) == 1


def test_governance_timestamp_is_naive_local_time() -> None:
    before = datetime.now()
    stamp = datetime.fromisoformat(learning_db_v2.governance_timestamp())
    after = datetime.now()

    assert stamp.tzinfo is None
    assert before <= stamp <= after


def test_governance_timestamp_subtracts_age() -> None:
    cutoff = datetime.fromisoformat(learning_db_v2.governance_timestamp(timedelta(days=7)))

    assert timedelta(days=7) <= datetime.now() - cutoff < timedelta(days=7, seconds=5)


def test_days_filter_matches_what_the_writer_stores(gov_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A row written now is inside a 1-day window and a row two days old is not, in any time zone."""
    learning_db_v2.record_governance_event("hook_blocked", event_id="gov-new", blocked=True)
    learning_db_v2.record_governance_event("hook_blocked", event_id="gov-old", blocked=True)
    conn = sqlite3.connect(gov_db)
    conn.execute(
        "UPDATE governance_events SET created_at = ? WHERE id = 'gov-old'",
        (learning_db_v2.governance_timestamp(timedelta(days=2)),),
    )
    conn.commit()
    conn.close()

    assert [r["id"] for r in learning_db_v2.query_governance_events(days=1)] == ["gov-new"]
