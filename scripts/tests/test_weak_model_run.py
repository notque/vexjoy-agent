"""Tests for scripts/weak_model_run.py (prompt building and reply extraction; no model calls)."""

from __future__ import annotations

import json
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
    assert seen["cmd"][-3:] == ["--output-format", "stream-json", "--verbose"]


def _events(*events: dict) -> str:
    return "\n".join(json.dumps(e) for e in events)


def test_parse_reply_collects_every_text_block_and_cost() -> None:
    stdout = _events(
        {"type": "system", "subtype": "init"},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "=== FILE: a.py ===\nx = 1"}]}},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "Summary of the work."}]}},
        {"type": "result", "result": "Summary of the work.", "total_cost_usd": 0.42, "usage": {"output_tokens": 700}},
    )
    blocks, cost = w.parse_reply(stdout)
    assert blocks == ["=== FILE: a.py ===\nx = 1", "Summary of the work."]
    assert cost["total_cost_usd"] == 0.42
    assert cost["output_tokens"] == 700
    assert cost["cache_read_input_tokens"] is None


def test_parse_reply_falls_back_to_result_field() -> None:
    blocks, _ = w.parse_reply(_events({"type": "result", "result": "only this", "total_cost_usd": 0.1}))
    assert blocks == ["only this"]


@pytest.mark.parametrize("stdout", ["plain reply", "[1, 2]"])
def test_parse_reply_passes_through_non_event_output(stdout: str) -> None:
    assert w.parse_reply(stdout) == ([stdout], {})


def test_split_commentary_keeps_trailing_prose_out_of_files() -> None:
    blocks = ["=== FILE: a.py ===\nx = 1", "=== FILE: b.py ===\ny = 2", "The files above are complete."]
    files_text, commentary = w.split_commentary(blocks)
    assert w.extract_files(files_text) == {"a.py": "x = 1\n", "b.py": "y = 2\n"}
    assert commentary == "The files above are complete."


def test_split_commentary_without_markers_returns_everything() -> None:
    assert w.split_commentary(["a", "b"]) == ("a\n\nb", "")


def test_main_fails_when_reply_has_no_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    limit = json.dumps({"type": "result", "result": "You've hit your session limit", "total_cost_usd": 0})
    monkeypatch.setattr(w, "run_model", lambda *_a: (limit, ""))
    task = tmp_path / "task.txt"
    task.write_text("build x", encoding="utf-8")
    assert w.main(["--task", str(task), "--out", str(tmp_path / "run"), "--format", "files"]) == 1
    assert not (tmp_path / "run").exists()
