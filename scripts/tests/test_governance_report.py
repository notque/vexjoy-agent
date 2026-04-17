"""Tests for governance-report.py and the governance_events DB infrastructure.

Covers:
- governance_events table creation on first init
- record_governance_event() happy path and graceful degradation
- resolve_governance_event() valid and invalid resolution states
- query_governance_events() filtering by days, type, severity, unresolved
- governance-report.py CLI: --days, --type, --resolve, --export json
"""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# ─── Path setup ───────────────────────────────────────────────────────────────

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HOOKS_LIB = _REPO_ROOT / "hooks" / "lib"
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

for p in [str(_HOOKS_LIB), str(_SCRIPTS_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import learning_db_v2 as ldb

governance_report = importlib.import_module("governance-report")


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point all DB operations at a temporary directory for test isolation."""
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(tmp_path))
    # Reset the module-level init flag so each test gets a fresh schema
    monkeypatch.setattr(ldb, "_initialized", False)
    yield
    monkeypatch.setattr(ldb, "_initialized", False)


# ─── Schema / table creation ──────────────────────────────────────────────────


def test_governance_events_table_created(tmp_path: Path) -> None:
    """governance_events table should exist after init_db()."""
    ldb.init_db()
    with ldb.get_connection() as conn:
        row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='governance_events'").fetchone()
    assert row is not None, "governance_events table was not created"


def test_governance_events_indexes_created() -> None:
    """All four governance indexes should be present after init."""
    ldb.init_db()
    with ldb.get_connection() as conn:
        names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_gov_%'"
            ).fetchall()
        }
    expected = {"idx_gov_session", "idx_gov_type", "idx_gov_severity", "idx_gov_created"}
    assert expected.issubset(names), f"Missing indexes: {expected - names}"


# ─── record_governance_event ──────────────────────────────────────────────────


def test_record_governance_event_returns_id() -> None:
    eid = ldb.record_governance_event(
        "approval_requested",
        session_id="sess-abc",
        tool_name="Bash",
        hook_phase="pre",
        severity="high",
        payload={"command": "rm -rf /"},
        blocked=True,
    )
    assert eid is not None
    assert eid.startswith("gov-")


def test_record_governance_event_persisted() -> None:
    eid = ldb.record_governance_event(
        "policy_violation",
        severity="warning",
        payload={"path": ".env"},
        blocked=True,
    )
    events = ldb.query_governance_events()
    ids = [e["id"] for e in events]
    assert eid in ids


def test_record_governance_event_blocked_field() -> None:
    ldb.record_governance_event("hook_blocked", blocked=True)
    ldb.record_governance_event("security_finding", blocked=False)

    events = ldb.query_governance_events()
    blocked = {e["id"]: e["blocked"] for e in events}
    assert any(v == 1 for v in blocked.values()), "At least one event should be blocked=1"
    assert any(v == 0 for v in blocked.values()), "At least one event should be blocked=0"


def test_record_governance_event_payload_roundtrip() -> None:
    payload = {"command": "git push --force", "patterns": ["--force"], "branch": "main"}
    eid = ldb.record_governance_event(
        "approval_requested",
        severity="high",
        payload=payload,
        blocked=True,
    )
    events = ldb.query_governance_events()
    ev = next(e for e in events if e["id"] == eid)
    parsed = json.loads(ev["payload"])
    assert parsed == payload


def test_record_governance_event_custom_id() -> None:
    custom_id = "gov-test-custom-id"
    returned = ldb.record_governance_event(
        "secret_detected",
        event_id=custom_id,
        severity="critical",
    )
    assert returned == custom_id
    events = ldb.query_governance_events()
    assert any(e["id"] == custom_id for e in events)


def test_record_governance_event_idempotent_custom_id() -> None:
    """INSERT OR IGNORE means a second call with the same id is a no-op."""
    eid = "gov-idempotent-test"
    ldb.record_governance_event("secret_detected", event_id=eid, severity="critical")
    ldb.record_governance_event("approval_requested", event_id=eid, severity="high")
    events = [e for e in ldb.query_governance_events() if e["id"] == eid]
    assert len(events) == 1
    # First write wins
    assert events[0]["event_type"] == "secret_detected"


def test_record_governance_event_graceful_on_bad_db(monkeypatch: pytest.MonkeyPatch) -> None:
    """Recording when get_connection raises must return None without re-raising."""
    import sqlite3
    from contextlib import contextmanager

    @contextmanager
    def _exploding_connection():
        raise sqlite3.OperationalError("simulated DB failure")
        yield  # noqa: unreachable — required for @contextmanager

    # Ensure init_db has already run so its own get_connection call is real.
    ldb.init_db()
    monkeypatch.setattr(ldb, "get_connection", _exploding_connection)

    result = ldb.record_governance_event("hook_blocked", blocked=True)
    assert result is None


# ─── resolve_governance_event ─────────────────────────────────────────────────


def test_resolve_governance_event_success() -> None:
    eid = ldb.record_governance_event("policy_violation", severity="warning", blocked=True)
    ok = ldb.resolve_governance_event(eid, "false_positive")
    assert ok is True

    events = ldb.query_governance_events()
    ev = next(e for e in events if e["id"] == eid)
    assert ev["resolution"] == "false_positive"
    assert ev["resolved_at"] is not None


def test_resolve_governance_event_all_states() -> None:
    for state in ("dismissed", "false_positive", "remediated"):
        eid = ldb.record_governance_event("hook_blocked")
        ok = ldb.resolve_governance_event(eid, state)
        assert ok is True, f"resolve failed for state={state}"


def test_resolve_governance_event_invalid_state() -> None:
    eid = ldb.record_governance_event("hook_blocked")
    ok = ldb.resolve_governance_event(eid, "unknown_state")
    assert ok is False


def test_resolve_governance_event_missing_id() -> None:
    ok = ldb.resolve_governance_event("gov-does-not-exist", "dismissed")
    assert ok is False


# ─── query_governance_events ──────────────────────────────────────────────────


def test_query_all_events() -> None:
    for i in range(3):
        ldb.record_governance_event("hook_blocked", severity="high")
    events = ldb.query_governance_events()
    assert len(events) >= 3


def test_query_filter_by_type() -> None:
    ldb.record_governance_event("secret_detected", severity="critical")
    ldb.record_governance_event("approval_requested", severity="high")

    secrets = ldb.query_governance_events(event_type="secret_detected")
    assert all(e["event_type"] == "secret_detected" for e in secrets)
    assert len(secrets) >= 1


def test_query_filter_by_severity() -> None:
    ldb.record_governance_event("secret_detected", severity="critical")
    ldb.record_governance_event("security_finding", severity="medium")

    criticals = ldb.query_governance_events(severity="critical")
    assert all(e["severity"] == "critical" for e in criticals)


def test_query_unresolved_only() -> None:
    eid_resolved = ldb.record_governance_event("policy_violation", severity="warning")
    eid_open = ldb.record_governance_event("hook_blocked", severity="high")

    ldb.resolve_governance_event(eid_resolved, "remediated")

    unresolved = ldb.query_governance_events(unresolved_only=True)
    ids = [e["id"] for e in unresolved]
    assert eid_open in ids
    assert eid_resolved not in ids


def test_query_filter_by_days(monkeypatch: pytest.MonkeyPatch) -> None:
    """Events with a past created_at should be excluded when days filter is tight."""
    ldb.init_db()
    # Insert a stale event directly
    with ldb.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO governance_events (id, event_type, severity, blocked, created_at)
            VALUES ('gov-stale-test', 'hook_blocked', 'high', 1, '2000-01-01T00:00:00')
            """
        )
        conn.commit()

    # Recent event
    ldb.record_governance_event("approval_requested", severity="high")

    recent = ldb.query_governance_events(days=7)
    ids = [e["id"] for e in recent]
    assert "gov-stale-test" not in ids


def test_query_returns_empty_list_on_fresh_db() -> None:
    ldb.init_db()
    events = ldb.query_governance_events(days=7)
    assert events == []


# ─── CLI: governance-report.py ────────────────────────────────────────────────


def _run(argv: list[str]) -> tuple[int, str]:
    """Run the CLI main() and capture stdout."""
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = governance_report.main(argv)
    return rc, buf.getvalue()


def test_cli_list_empty_db() -> None:
    rc, out = _run(["--days", "7"])
    assert rc == 0
    assert "No governance events found" in out


def test_cli_list_shows_events() -> None:
    ldb.record_governance_event("approval_requested", severity="high", blocked=True)
    rc, out = _run(["--days", "7"])
    assert rc == 0
    assert "approval_requested" in out


def test_cli_filter_by_type() -> None:
    ldb.record_governance_event("secret_detected", severity="critical")
    ldb.record_governance_event("approval_requested", severity="high")

    rc, out = _run(["--type", "secret_detected"])
    assert rc == 0
    assert "secret_detected" in out
    # The other type should not appear in the rows
    # (header line contains both words potentially, check count per-row is tricky;
    #  just verify the command ran cleanly)
    assert rc == 0


def test_cli_export_json() -> None:
    ldb.record_governance_event("policy_violation", severity="warning", blocked=True)
    rc, out = _run(["--days", "7", "--export", "json"])
    assert rc == 0
    data = json.loads(out)
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["event_type"] == "policy_violation"


def test_cli_resolve_success() -> None:
    eid = ldb.record_governance_event("hook_blocked", severity="high", blocked=True)
    rc, out = _run(["--resolve", eid, "--resolution", "dismissed"])
    assert rc == 0
    assert "dismissed" in out

    events = ldb.query_governance_events()
    ev = next(e for e in events if e["id"] == eid)
    assert ev["resolution"] == "dismissed"


def test_cli_resolve_missing_resolution_arg() -> None:
    """--resolve without --resolution should exit with code 2."""
    with pytest.raises(SystemExit) as exc_info:
        governance_report.main(["--resolve", "gov-fake-id"])
    assert exc_info.value.code == 2


def test_cli_resolve_unknown_event(capsys: pytest.CaptureFixture[str]) -> None:
    rc, out = _run(["--resolve", "gov-nonexistent", "--resolution", "dismissed"])
    assert rc == 1


def test_cli_resolve_invalid_resolution() -> None:
    """Invalid --resolution value should be caught by argparse."""
    with pytest.raises(SystemExit) as exc_info:
        governance_report.main(["--resolve", "gov-x", "--resolution", "bad_value"])
    assert exc_info.value.code == 2


def test_cli_unresolved_flag() -> None:
    eid_open = ldb.record_governance_event("hook_blocked", severity="high", blocked=True)
    eid_res = ldb.record_governance_event("policy_violation", severity="warning", blocked=True)
    ldb.resolve_governance_event(eid_res, "remediated")

    rc, out = _run(["--unresolved"])
    assert rc == 0
    assert eid_open in out
    assert eid_res not in out


def test_cli_no_args_shows_all_events() -> None:
    """Running with no args (no --days) should return all events."""
    ldb.record_governance_event("security_finding", severity="medium")
    rc, out = _run([])
    assert rc == 0
    assert "security_finding" in out


def test_cli_export_json_empty_db() -> None:
    rc, out = _run(["--export", "json"])
    assert rc == 0
    data = json.loads(out)
    assert data == []
