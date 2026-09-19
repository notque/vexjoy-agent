"""compaction_events / session_usage tables and the evidence ingester."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_LIB = Path(__file__).resolve().parents[1] / "lib"
_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

import learning_db_v2 as ldb


@pytest.fixture
def db_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(tmp_path))
    monkeypatch.setattr(ldb, "_initialized", False)
    return tmp_path


def _load_evidence_module():
    spec = importlib.util.spec_from_file_location("jev_compact_evidence", _SCRIPTS / "jev-compact-evidence.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_COUNT_SQL = {
    "compaction_events": "SELECT COUNT(*) FROM compaction_events",
    "session_usage": "SELECT COUNT(*) FROM session_usage",
}


def _count(table: str) -> int:
    with ldb.get_connection() as conn:
        return conn.execute(_COUNT_SQL[table]).fetchone()[0]


def test_migration_creates_tables_and_bumps_version(db_env):
    ldb.init_db()
    with ldb.get_connection() as conn:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        version = conn.execute("PRAGMA user_version").fetchone()[0]
    assert {"compaction_events", "session_usage"} <= names
    assert version == ldb._CURRENT_SCHEMA_VERSION


def test_record_compaction_event_is_idempotent(db_env):
    kwargs = dict(
        session_id="s1",
        ts="2026-09-18T01:51:42.559Z",
        source="plugin",
        trigger="plugin",
        engine="jev",
        messages_before=197,
        messages_after=171,
        tokens_before=128057,
        reduction_ratio=0.26,
        dropped_calls=12,
        truncated_results=1,
        latency_ms=557,
    )
    assert ldb.record_compaction_event(**kwargs) is True
    assert ldb.record_compaction_event(**kwargs) is False
    assert _count("compaction_events") == 1
    with ldb.get_connection() as conn:
        row = dict(conn.execute("SELECT * FROM compaction_events").fetchone())
    assert row["tokens_after"] is None  # absent stays NULL, never 0
    assert row["dropped_calls"] == 12
    assert row["engine"] == "jev"


def test_record_session_usage(db_env):
    assert ldb.record_session_usage(
        session_id="s1",
        ts="2026-09-18T01:51:00Z",
        phase="turn_complete",
        context_tokens=120000,
        context_window=1000000,
        context_percent=12.0,
        cost_usd=1.5,
    )
    assert _count("session_usage") == 1


def test_ingest_jsonl_and_transcript(db_env, tmp_path):
    mod = _load_evidence_module()
    jsonl = tmp_path / "compaction-events.jsonl"
    jsonl.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "kind": "compaction",
                        "session_id": "abc",
                        "ts": "2026-09-18T01:51:42.000Z",
                        "source": "plugin",
                        "trigger": "plugin",
                        "engine": "jev",
                        "messages_before": 197,
                        "messages_after": 171,
                        "reduction_ratio": 0.26,
                        "dropped_calls": 12,
                    }
                ),
                json.dumps(
                    {
                        "kind": "usage",
                        "session_id": "abc",
                        "ts": "2026-09-18T01:51:40.000Z",
                        "phase": "turn_complete",
                        "context_tokens": 128057,
                    }
                ),
                "not json",
                json.dumps({"kind": "compaction"}),  # missing session/ts: skipped
            ]
        )
        + "\n"
    )
    transcript = tmp_path / "abc.jsonl"
    transcript.write_text(
        "\n".join(
            [
                json.dumps({"type": "user", "message": {"content": "hi"}}),
                json.dumps(
                    {
                        "type": "system",
                        "subtype": "compact_boundary",
                        "timestamp": "2026-09-18T01:51:42.559Z",
                        "compactMetadata": {
                            "trigger": "manual",
                            "preTokens": 128057,
                            "postTokens": 91645,
                            "durationMs": 336,
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "system",
                        "subtype": "compact_boundary",
                        "timestamp": "2026-09-18T01:56:42.713Z",
                        "compactMetadata": {"trigger": "manual", "preTokens": 2346, "durationMs": 147014},
                    }
                ),
            ]
        )
        + "\n"
    )

    assert mod.ingest_jsonl(jsonl) == 2
    assert mod.ingest_jsonl(jsonl) == 0  # re-run inserts nothing
    assert mod.ingest_transcript(transcript) == 2
    assert _count("compaction_events") == 3
    assert _count("session_usage") == 1

    rows = mod._rows("abc", 10)
    claims = [r for r in rows if r["source"] == "plugin"]
    by_ts = {r["ts"]: r for r in rows if r["source"] == "transcript"}
    # The 336ms engine record sits within 20s of the plugin's jev claim.
    assert mod._classify_transcript(by_ts["2026-09-18T01:51:42.559Z"], claims) == "jev (confirmed)"
    # The 147s one has no claim nearby and is too slow to be Jev.
    assert mod._classify_transcript(by_ts["2026-09-18T01:56:42.713Z"], claims) == "builtin-llm"


def test_report_runs_on_empty_db(db_env, capsys):
    mod = _load_evidence_module()
    assert mod.report(None, 10) == 0
    assert "No compaction events" in capsys.readouterr().out


def test_ingest_store_finds_plugin_store_by_content(db_env, tmp_path):
    mod = _load_evidence_module()
    root = tmp_path / "plugins"
    store = root / "data" / "jev-auto-compact-jev-auto-compact" / "store.json"
    store.parent.mkdir(parents=True)
    store.write_text(
        json.dumps(
            {
                "events": [
                    {
                        "kind": "compaction",
                        "session_id": "s9",
                        "ts": "2026-09-18T03:00:00.000Z",
                        "source": "plugin",
                        "trigger": "plugin",
                        "engine": "jev",
                        "messages_before": 50,
                        "messages_after": 30,
                        "reduction_ratio": 0.4,
                    },
                    {"kind": "usage", "session_id": "s9", "ts": "2026-09-18T02:59:00Z", "context_percent": 61.0},
                    {"kind": "usage"},  # no session/ts: skipped
                ]
            }
        )
    )
    # A store from another plugin, and a non-store JSON, are ignored.
    other = root / "data" / "other-plugin" / "store.json"
    other.parent.mkdir(parents=True)
    other.write_text(json.dumps({"events": [{"kind": "usage", "session_id": "x", "ts": "2026-09-18T00:00:00Z"}]}))
    (root / "jev-auto-compact-manifest.json").write_text(json.dumps({"version": "1.3.0"}))

    assert mod.ingest_store(root) == 2
    assert mod.ingest_store(root) == 0  # idempotent
    assert _count("compaction_events") == 1
    assert _count("session_usage") == 1


def test_record_compaction_event_rejects_unknown_kwargs(db_env):
    with pytest.raises(TypeError) as exc_info:
        ldb.record_compaction_event(
            session_id="s1",
            ts="2026-09-18T01:51:42.559Z",
            source="plugin",
            dropped_calls=1,
            droped_calls=2,
            bogus=3,
        )
    assert str(exc_info.value).endswith("unexpected keyword arguments: bogus, droped_calls")
    ldb.init_db()
    assert _count("compaction_events") == 0


def test_store_files_survive_stat_oserror(db_env, tmp_path):
    mod = _load_evidence_module()
    root = tmp_path / "plugins"
    good = root / "jev-auto-compact" / "store.json"
    good.parent.mkdir(parents=True)
    good.write_text(json.dumps({"events": []}), encoding="utf-8")
    vanished = root / "jev-auto-compact" / "gone.json"

    real_stat = Path.stat

    def flaky_stat(self, *args, **kwargs):
        if self.name == "gone.json":
            raise OSError("vanished")
        return real_stat(self, *args, **kwargs)

    def fake_rglob(_self, _pattern):
        return iter([vanished, good])

    with (
        patch.object(Path, "rglob", fake_rglob),
        patch.object(Path, "stat", flaky_stat),
    ):
        hits = mod._store_files(root)
    assert hits == [good]


def test_report_matches_claims_outside_limit_window(db_env, capsys):
    mod = _load_evidence_module()
    # One plugin claim, then many newer transcript rows that push it out of a LIMIT window.
    assert ldb.record_compaction_event(
        session_id="sess-a", ts="2026-09-18T01:00:00+00:00", source="plugin", engine="jev", trigger="plugin"
    )
    assert ldb.record_compaction_event(
        session_id="sess-a",
        ts="2026-09-18T01:00:05+00:00",
        source="transcript",
        duration_ms=60000,
        tokens_before=10,
        tokens_after=5,
    )
    for i in range(5):
        assert ldb.record_compaction_event(
            session_id="sess-b", ts=f"2026-09-18T02:00:0{i}+00:00", source="transcript", duration_ms=60000
        )
    # LIMIT 6 covers the sess-a transcript row but not its older plugin claim.
    assert mod.report(None, 6) == 0
    out = capsys.readouterr().out
    sess_a_lines = [line for line in out.splitlines() if line.startswith("2026-09-18T01:00:05")]
    assert len(sess_a_lines) == 1
    assert "jev (confirmed)" in sess_a_lines[0]


def test_claims_for_sessions_empty(db_env):
    mod = _load_evidence_module()
    assert mod._claims_for_sessions(set()) == []
    assert mod._claims_for_sessions({""}) == []


def test_plugin_jev_calls_reach_the_call_log_once(db_env):
    mod = _load_evidence_module()
    ok_call = {
        "kind": "jev_call",
        "session_id": "s1",
        "ts": "2026-01-01T00:00:00.000Z",
        "ok": True,
        "latency_ms": 140,
        "input_tokens": 5200,
        "output_tokens": 300,
        "n_questions": 24,
    }
    failed_call = {**ok_call, "ts": "2026-01-01T00:00:01.000Z", "ok": False, "input_tokens": None, "error": "HTTP 402"}

    assert mod._insert_record(ok_call) is True
    assert mod._insert_record(failed_call) is True
    # The plugin store is read again on every ingest; a second pass adds nothing.
    assert mod._insert_record(ok_call) is False
    assert mod._insert_record(failed_call) is False

    with ldb.get_connection() as conn:
        rows = conn.execute(
            "SELECT script, session_id, ok, input_tokens, n_questions, error FROM jev_calls ORDER BY ts"
        ).fetchall()
    assert [tuple(r) for r in rows] == [
        ("jev-auto-compact.mjs", "s1", 1, 5200, 24, None),
        ("jev-auto-compact.mjs", "s1", 0, None, 24, "HTTP 402"),
    ]
