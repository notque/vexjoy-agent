"""Tests for scripts/weak_model_run.py (prompt building and reply extraction; no model calls)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import weak_model_run as w


def test_build_prompt_orders_format_guidance_task() -> None:
    p = w.build_prompt("  Build X  ", ["RULE A", "RULE B"], "html")
    assert p.index("<!doctype html>") < p.index("RULE A") < p.index("RULE B") < p.index("TASK:\nBuild X")


def test_build_prompt_without_guidance_or_format() -> None:
    assert w.build_prompt("t", [], "text") == "TASK:\nt\n"


def test_extract_html_strips_commentary() -> None:
    reply = "Here you go:\n<!DOCTYPE html><html><body>x</body></html>\nDone."
    assert w.extract_html(reply) == "<!DOCTYPE html><html><body>x</body></html>"


def test_extract_html_falls_back_to_reply() -> None:
    assert w.extract_html("no html") == "no html"


def test_extract_files_splits_blocks_and_strips_fences() -> None:
    reply = "=== FILE: go.mod ===\nmodule x\n=== FILE: cmd/main.go ===\n```go\npackage main\n```\n"
    assert w.extract_files(reply) == {"go.mod": "module x\n", "cmd/main.go": "package main\n"}


@pytest.mark.parametrize("path", ["/etc/passwd", "../escape.go", "a/../../b.go"])
def test_extract_files_rejects_unsafe_paths(path: str) -> None:
    with pytest.raises(ValueError):
        w.extract_files(f"=== FILE: {path} ===\nx\n")


def test_run_model_drops_adaptive_thinking_override(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"], seen["env"] = cmd, kw["env"]

        class P:
            stdout, stderr = "ok", ""

        return P()

    monkeypatch.setenv("CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING", "1")
    monkeypatch.setattr(w.subprocess, "run", fake_run)
    assert w.run_model("hi", "claude-opus-4-6", 5) == ("ok", "")
    assert "CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING" not in seen["env"]
    assert seen["cmd"][:4] == ["claude", "-p", "--model", "claude-opus-4-6"]
