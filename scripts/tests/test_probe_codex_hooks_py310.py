"""scripts/probe-codex-hooks.py loads on Python 3.10, which has no ``datetime.UTC`` (added in 3.11)."""

from __future__ import annotations

import datetime
import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "probe-codex-hooks.py"

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the probe imports pty, termios and fcntl")


def test_probe_imports_without_datetime_utc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delattr(datetime, "UTC", raising=False)  # what Python 3.10 looks like
    spec = importlib.util.spec_from_file_location("probe_codex_hooks_py310", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    stamp = module.datetime.now(module.timezone.utc).replace(microsecond=0).isoformat()
    assert stamp.endswith("+00:00")
