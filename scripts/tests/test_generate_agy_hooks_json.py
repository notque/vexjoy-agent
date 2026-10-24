"""Tests for scripts/generate-agy-hooks-json.py."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "scripts" / "generate-agy-hooks-json.py"
ALLOWLIST_PATH = ROOT / "scripts" / "agy-hooks-allowlist.txt"


def _load_module():
    spec = importlib.util.spec_from_file_location("generate_agy_hooks_json", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mod = _load_module()
parse_allowlist = _mod.parse_allowlist
build_hooks_json = _mod.build_hooks_json
merge_hooks_json = _mod.merge_hooks_json


def test_empty_allowlist_produces_enabled_group():
    entries = parse_allowlist("")
    result = build_hooks_json(entries, agy_hooks_dir="/home/user/.gemini/hooks")
    assert result == {"vexjoy-agent": {"enabled": True}}


def test_flat_events_have_no_matcher_blocks():
    text = (
        "SessionStart:session-github-briefing.py failure=open\n"
        "PreInvocation:prompt-capture.py failure=open\n"
        "PreInvocation:routing-outcome-finalizer.py failure=open\n"
        "Stop:stop-drift-guard.py failure=open\n"
    )
    entries = parse_allowlist(text)
    result = build_hooks_json(entries, agy_hooks_dir="/fake/hooks")
    group = result["vexjoy-agent"]
    assert group["enabled"] is True

    # SessionStart is a flat list of command handlers
    ss = group["SessionStart"]
    assert isinstance(ss, list) and len(ss) == 1
    assert ss[0]["type"] == "command"
    assert "matcher" not in ss[0]
    assert "session-github-briefing.py" in ss[0]["command"]

    # First PreInvocation gets --drain-deferred, second does not
    pre = group["PreInvocation"]
    assert len(pre) == 2
    assert "--drain-deferred" in pre[0]["command"]
    assert "--drain-deferred" not in pre[1]["command"]

    # Stop is flat
    stop = group["Stop"]
    assert len(stop) == 1 and "matcher" not in stop[0]


def test_grouped_events_group_by_matcher():
    text = (
        "PreToolUse:pretool-branch-safety.py matcher=run_command failure=closed\n"
        "PreToolUse:ci-merge-gate.py matcher=run_command failure=closed\n"
        "PreToolUse:pretool-unified-gate.py matcher=edit_file|write_file failure=closed\n"
        "PostToolUse:posttool-security-scan.py matcher=edit_file|write_file failure=open\n"
    )
    entries = parse_allowlist(text)
    result = build_hooks_json(entries, agy_hooks_dir="/fake/hooks")
    group = result["vexjoy-agent"]

    pre_blocks = group["PreToolUse"]
    assert len(pre_blocks) == 2
    by_matcher = {b["matcher"]: b["hooks"] for b in pre_blocks}
    assert len(by_matcher["run_command"]) == 2
    assert len(by_matcher["edit_file|write_file"]) == 1

    post_blocks = group["PostToolUse"]
    assert len(post_blocks) == 1
    assert post_blocks[0]["matcher"] == "edit_file|write_file"


@pytest.mark.parametrize(
    ("bad_line", "expected_substr"),
    [
        ("SessionStart:session-github-briefing.py matcher=startup failure=open\n", "flat event"),
        ("PreToolUse:pretool-branch-safety.py failure=closed\n", "requires matcher"),
        ("PreToolUse:pretool-branch-safety.py matcher=run_command\n", "missing required failure"),
        ("UnknownEvent:pretool-branch-safety.py failure=open\n", "unknown Antigravity event"),
        ("Stop:session-summary.py failure=open\nStop:session-summary.py failure=open\n", "duplicate"),
    ],
)
def test_parse_allowlist_rejects_invalid_lines(bad_line: str, expected_substr: str):
    with pytest.raises(ValueError, match=expected_substr):
        parse_allowlist(bad_line)


def test_production_allowlist_round_trips_and_all_files_exist():
    entries = parse_allowlist(ALLOWLIST_PATH.read_text(encoding="utf-8"))
    assert len(entries) >= 40
    result = build_hooks_json(entries, agy_hooks_dir="/Users/test/.gemini/hooks")
    group = result["vexjoy-agent"]
    assert group["enabled"] is True
    for ev in ("SessionStart", "PreInvocation", "PreToolUse", "PostToolUse", "Stop"):
        assert ev in group


def test_merge_hooks_json_preserves_other_hook_groups():
    existing = {"my-custom-hooks": {"enabled": True, "Stop": [{"type": "command", "command": "echo bye"}]}}
    generated = {"vexjoy-agent": {"enabled": True}}
    merged = merge_hooks_json(existing, generated)
    assert "my-custom-hooks" in merged
    assert "vexjoy-agent" in merged


def test_cli_dry_run_produces_valid_json():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--allowlist", str(ALLOWLIST_PATH), "--dry-run"],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(proc.stdout)
    assert data["vexjoy-agent"]["enabled"] is True
