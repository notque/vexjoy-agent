"""jev_calls: every call_jev records one row; stats aggregate per script."""

from __future__ import annotations

import importlib
import io
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hooks" / "lib"))
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture(autouse=True)
def _isolate_jev_state(tmp_path, monkeypatch):
    """Keep the call cache and breaker off the real state directory and disabled per test."""
    monkeypatch.setenv("JEV_STATE_DIR", str(tmp_path / "jev_state"))
    monkeypatch.setenv("JEV_CACHE_TTL_S", "0")
    monkeypatch.setenv("JEV_BREAKER_TTL_S", "0")


def _isolate_db(tmp_path, monkeypatch):
    import learning_db_v2 as db

    monkeypatch.setattr(db, "DB_PATH", tmp_path / "learning.db", raising=False)
    for name in ("_DB_PATH", "LEARNING_DB", "DEFAULT_DB_PATH"):
        if hasattr(db, name):
            monkeypatch.setattr(db, name, tmp_path / "learning.db")
    monkeypatch.setenv("CLAUDE_LEARNING_DB", str(tmp_path / "learning.db"))
    return db


def test_record_and_stats(tmp_path, monkeypatch):
    db = _isolate_db(tmp_path, monkeypatch)
    assert db.record_jev_call(
        script="jev-harness.py", ok=True, latency_ms=210.0, input_tokens=900, n_questions=12, n_redacted=0
    )
    assert db.record_jev_call(script="jev-harness.py", ok=False, latency_ms=50.0, error="HTTP 422")
    assert db.record_jev_call(script="jev-route.py", ok=True, latency_ms=160.0, input_tokens=6000, n_questions=40)
    rows = {r["script"]: r for r in db.jev_call_stats(1)}
    assert rows["jev-harness.py"]["calls"] == 2 and rows["jev-harness.py"]["failed"] == 1
    assert rows["jev-route.py"]["input_tokens"] == 6000 and rows["jev-route.py"]["questions"] == 40


def test_call_jev_records_success_and_failure(tmp_path, monkeypatch):
    db = _isolate_db(tmp_path, monkeypatch)
    import jev_router_common as jrc

    importlib.reload(jrc)
    monkeypatch.setattr(sys, "argv", ["jev-fake-script.py"])
    body = json.dumps({"answers": {"q": {"noul": 0.7}}, "usage": {"input_tokens": 123, "output_tokens": 4}}).encode()

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(jrc.urllib.request, "urlopen", lambda _req, **_kw: _Resp(body))
    data, ms = jrc.call_jev(
        {"model": "jev-latest", "state": {}, "questions": {"q": {"type": "noul", "instructions": "x"}}}, "k", 5
    )
    assert data["answers"]["q"]["noul"] == 0.7

    def boom(req, **_kw):
        raise jrc.urllib.error.HTTPError(req.full_url, 422, "bad", {}, io.BytesIO(b"schema"))

    monkeypatch.setattr(jrc.urllib.request, "urlopen", boom)
    try:
        jrc.call_jev({"questions": {}}, "k", 5)
    except RuntimeError:
        pass
    rows = {r["script"]: r for r in db.jev_call_stats(1)}
    assert rows["jev-fake-script.py"]["calls"] == 2 and rows["jev-fake-script.py"]["failed"] == 1
    assert rows["jev-fake-script.py"]["input_tokens"] == 123 and rows["jev-fake-script.py"]["questions"] == 1


def test_telemetry_failure_never_breaks_call(tmp_path, monkeypatch):
    import jev_router_common as jrc

    importlib.reload(jrc)
    monkeypatch.setattr(jrc, "_record_jev_call", lambda **_k: (_ for _ in ()).throw(RuntimeError("db down")))
    body = json.dumps({"answers": {}}).encode()

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(jrc.urllib.request, "urlopen", lambda _req, **_kw: _Resp(body))
    data, _ = jrc.call_jev({"questions": {}}, "k", 5)
    assert data == {"answers": {}}
