"""Tests for preflight.py — reference-file existence check."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = str(Path(__file__).parent.parent / "preflight.py")


def _run(*args: str) -> tuple[dict, int]:
    proc = subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True, timeout=10, check=False)
    return json.loads(proc.stdout), proc.returncode


def test_preflight_ok_for_known_shape() -> None:
    """deck shape: ok=true and exactly the 3 expected reference files."""
    payload, rc = _run("--shape", "deck")
    assert rc == 0
    assert payload["ok"] is True
    assert payload["shape"] == "deck"
    assert payload["missing"] == []
    assert set(payload["loaded"]) == {
        "design-system.md",
        "interaction-patterns.md",
        "shape-slide-deck.md",
    }


def test_preflight_unknown_shape() -> None:
    """nonsense shape: exit 2, ok=false, error mentions invalid shape."""
    payload, rc = _run("--shape", "nonsense")
    assert rc == 2
    assert payload["ok"] is False
    assert "Invalid shape" in payload["error"]
    assert "valid_shapes" in payload
    assert "deck" in payload["valid_shapes"]
