"""Run the jev-auto-compact plugin's node tests under pytest, so CI covers the .mjs twin of jev_redact.py."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

PLUGIN_TESTS = Path(__file__).resolve().parents[2] / "plugins" / "jev-auto-compact" / "tests"


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_plugin_node_tests_pass() -> None:
    files = sorted(str(p) for p in PLUGIN_TESTS.glob("*.test.mjs"))
    assert files, "no plugin tests found"
    proc = subprocess.run(
        ["node", "--test", *files],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-1000:]
