"""Stop hooks defer advisories; the UserPromptSubmit injector delivers them once."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "hooks" / "lib"))
import hook_utils

spec = importlib.util.spec_from_file_location("inj", ROOT / "hooks" / "pending-advisory-injector-userprompt.py")
inj = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inj)


def _redirect(tmp_path, monkeypatch):
    d = tmp_path / "pending"
    monkeypatch.setattr(hook_utils, "PENDING_ADVISORY_DIR", d)
    monkeypatch.setattr(inj, "PENDING_DIR", d)
    return d


def test_defer_then_drain_once(tmp_path, monkeypatch):
    _redirect(tmp_path, monkeypatch)
    assert hook_utils.defer_advisory("s1", "stop-drift-guard", "README count off", "drift found")
    assert hook_utils.defer_advisory("s1", "example-check", "ungrounded claim", "Citation check: ungrounded")
    ctx = inj.drain("s1")
    assert "stop-drift-guard" in ctx and "README count off" in ctx
    assert "example-check" in ctx and "ungrounded claim" in ctx
    assert inj.drain("s1") is None, "delivered once"


def test_bad_session_ids_rejected(tmp_path, monkeypatch):
    _redirect(tmp_path, monkeypatch)
    for bad in (None, "", "../x", "a/b", "."):
        assert not hook_utils.defer_advisory(bad, "x", "m", "s")


def test_stale_rows_dropped(tmp_path, monkeypatch):
    d = _redirect(tmp_path, monkeypatch)
    d.mkdir()
    (d / "s2.jsonl").write_text(json.dumps({"ts": 0, "source": "x", "summary": "old", "message": "old"}) + "\n")
    assert inj.drain("s2", now=10**9) is None


def test_other_session_untouched(tmp_path, monkeypatch):
    _redirect(tmp_path, monkeypatch)
    hook_utils.defer_advisory("a", "x", "for a", "s")
    hook_utils.defer_advisory("b", "x", "for b", "s")
    assert "for a" in inj.drain("a") and inj.drain("b") and inj.drain("a") is None


def test_injector_subprocess_emits_context(tmp_path, monkeypatch):
    d = _redirect(tmp_path, monkeypatch)
    hook_utils.defer_advisory("s3", "stop-drift-guard", "msg body", "sum")
    env = {"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"}
    # the script derives PENDING_DIR from HOME; mirror the file there
    real = tmp_path / ".claude" / "state" / "pending-advisories"
    real.mkdir(parents=True)
    (real / "s3.jsonl").write_text((d / "s3.jsonl").read_text())
    out = subprocess.run(
        [sys.executable, str(ROOT / "hooks" / "pending-advisory-injector-userprompt.py")],
        input=json.dumps({"session_id": "s3", "prompt": "hi"}),
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )
    assert out.returncode == 0
    data = json.loads(out.stdout)
    assert "msg body" in data["hookSpecificOutput"]["additionalContext"]
    assert not (real / "s3.jsonl").exists()
