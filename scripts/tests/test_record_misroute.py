#!/usr/bin/env python3
"""Tests for exit codes in scripts/record-misroute.py.

Covers: crash path exits 1 (not 0), success path exits 0, and the
subprocess return code propagating through unchanged.

Run with: python3 -m pytest scripts/tests/test_record_misroute.py -v
"""

import runpy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_repo_root = Path(__file__).resolve().parents[2]
SCRIPT_PATH = str(_repo_root / "scripts" / "record-misroute.py")

VALID_ARGV = [
    SCRIPT_PATH,
    "--request",
    "original request",
    "--routed-to",
    "agent:skill",
    "--should-have-been",
    "other-agent:skill",
    "--reason",
    "wrong domain",
]


def _completed(returncode: int, stderr: str = ""):
    """Return a subprocess.run stand-in with a fixed result."""
    return lambda *_args, **_kwargs: SimpleNamespace(returncode=returncode, stderr=stderr, stdout="")


def _run_script(monkeypatch: pytest.MonkeyPatch, fake_run) -> SystemExit:
    """Run the script's __main__ path with subprocess.run replaced."""
    monkeypatch.setattr(sys, "argv", list(VALID_ARGV))
    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(SCRIPT_PATH, run_name="__main__")
    return exc_info.value


def test_crash_exits_one(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    """A crash while recording must exit 1, not report success."""

    def _boom(*_args, **_kwargs):
        raise RuntimeError("recording crashed")

    exc = _run_script(monkeypatch, _boom)
    assert exc.code == 1
    assert "recording crashed" in capsys.readouterr().err


def test_success_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """A clean recording exits 0."""
    exc = _run_script(monkeypatch, _completed(0))
    assert exc.code == 0


def test_subprocess_failure_propagates(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    """A failing learning-db subprocess exit code passes through unchanged."""
    exc = _run_script(monkeypatch, _completed(3, stderr="db locked"))
    assert exc.code == 3
    assert "db locked" in capsys.readouterr().err
