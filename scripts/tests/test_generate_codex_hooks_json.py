"""Tests for scripts/generate-codex-hooks-json.py."""

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Module import helper (hyphen in filename requires importlib)
# ---------------------------------------------------------------------------

_SCRIPT_PATH = Path(__file__).parent.parent / "generate-codex-hooks-json.py"


def _load_module():
    """Load generate-codex-hooks-json.py as a module."""
    spec = importlib.util.spec_from_file_location("generate_codex_hooks_json", _SCRIPT_PATH)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


_mod = _load_module()
parse_allowlist = _mod.parse_allowlist
build_hooks_json = _mod.build_hooks_json


# ---------------------------------------------------------------------------
# Test 1: Empty allowlist
# ---------------------------------------------------------------------------


def test_empty_allowlist_produces_empty_hooks():
    """Empty allowlist text produces {'hooks': {}}."""
    entries = parse_allowlist("")
    result = build_hooks_json(entries)
    assert result == {"hooks": {}}


def test_comments_and_blanks_only_produces_empty():
    """Allowlist with only comments and blank lines produces empty hooks."""
    text = "# This is a comment\n\n# Another comment\n"
    entries = parse_allowlist(text)
    result = build_hooks_json(entries)
    assert result == {"hooks": {}}


# ---------------------------------------------------------------------------
# Test 2: Single SessionStart with no matcher
# ---------------------------------------------------------------------------


def test_single_session_start_no_matcher():
    """SessionStart entry with no matcher gets default matcher 'startup|resume'."""
    text = "SessionStart:kairos-briefing-injector.py\n"
    entries = parse_allowlist(text)
    result = build_hooks_json(entries, codex_hooks_dir="/home/user/.codex/hooks")

    assert "SessionStart" in result["hooks"]
    blocks = result["hooks"]["SessionStart"]
    assert len(blocks) == 1
    block = blocks[0]
    assert block["matcher"] == "startup|resume"
    assert len(block["hooks"]) == 1
    hook = block["hooks"][0]
    assert hook["type"] == "command"
    assert "kairos-briefing-injector.py" in hook["command"]
    assert hook["timeout"] == 600


# ---------------------------------------------------------------------------
# Test 3: Multiple SessionStart entries grouped into one matcher block
# ---------------------------------------------------------------------------


def test_multiple_session_start_entries_grouped():
    """Multiple SessionStart entries are grouped into one matcher block."""
    text = (
        "SessionStart:kairos-briefing-injector.py\n"
        "SessionStart:adr-context-injector.py\n"
        "SessionStart:instruction-reminder.py\n"
    )
    entries = parse_allowlist(text)
    result = build_hooks_json(entries, codex_hooks_dir="/fake/hooks")

    blocks = result["hooks"]["SessionStart"]
    assert len(blocks) == 1, "All SessionStart entries share the same default matcher, so only one block."
    hook_list = blocks[0]["hooks"]
    assert len(hook_list) == 3
    names = [h["command"] for h in hook_list]
    assert any("kairos-briefing-injector.py" in n for n in names)
    assert any("adr-context-injector.py" in n for n in names)
    assert any("instruction-reminder.py" in n for n in names)


# ---------------------------------------------------------------------------
# Test 4: PreToolUse without matcher raises ValueError
# ---------------------------------------------------------------------------


def test_pretooluse_without_matcher_raises():
    """PreToolUse entry without matcher raises ValueError mentioning 'Bash'."""
    text = "PreToolUse:pretool-bash-injection-scan.py\n"
    with pytest.raises(ValueError) as exc_info:
        parse_allowlist(text)
    assert "Bash" in str(exc_info.value)


def test_posttooluse_without_matcher_raises():
    """PostToolUse entry without matcher raises ValueError mentioning 'Bash'."""
    text = "PostToolUse:posttool-bash-injection-scan.py\n"
    with pytest.raises(ValueError) as exc_info:
        parse_allowlist(text)
    assert "Bash" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test 5: PreToolUse+PostToolUse with Bash matcher produce separate event keys
# ---------------------------------------------------------------------------


def test_pretooluse_and_posttooluse_with_bash_matcher():
    """PreToolUse and PostToolUse with Bash matcher produce separate event keys."""
    text = "PreToolUse:pretool-bash-injection-scan.py Bash\nPostToolUse:posttool-bash-injection-scan.py Bash\n"
    entries = parse_allowlist(text)
    result = build_hooks_json(entries, codex_hooks_dir="/fake/hooks")

    assert "PreToolUse" in result["hooks"]
    assert "PostToolUse" in result["hooks"]

    pre_blocks = result["hooks"]["PreToolUse"]
    assert len(pre_blocks) == 1
    assert pre_blocks[0]["matcher"] == "Bash"
    assert len(pre_blocks[0]["hooks"]) == 1

    post_blocks = result["hooks"]["PostToolUse"]
    assert len(post_blocks) == 1
    assert post_blocks[0]["matcher"] == "Bash"
    assert len(post_blocks[0]["hooks"]) == 1


# ---------------------------------------------------------------------------
# Test 6: Comments and blank lines are ignored
# ---------------------------------------------------------------------------


def test_comments_and_blank_lines_ignored():
    """Lines starting with # and empty lines do not become entries."""
    text = (
        "# Phase 1: safe on Codex v0.114.0+\n"
        "\n"
        "SessionStart:kairos-briefing-injector.py\n"
        "\n"
        "# Another comment\n"
        "Stop:suggest-compact.py\n"
    )
    entries = parse_allowlist(text)
    assert len(entries) == 2
    events = [e["event"] for e in entries]
    assert "SessionStart" in events
    assert "Stop" in events


# ---------------------------------------------------------------------------
# Test 7: Malformed line raises ValueError with line number
# ---------------------------------------------------------------------------


def test_malformed_line_raises_with_line_number():
    """A line without ':' raises ValueError that includes the line number."""
    text = "# comment\n\nbadline-no-colon\n"
    with pytest.raises(ValueError) as exc_info:
        parse_allowlist(text)
    msg = str(exc_info.value)
    assert "3" in msg, f"Expected line number 3 in error: {msg}"


def test_malformed_unknown_event_raises():
    """An unknown event name raises ValueError."""
    text = "UnknownEvent:some-hook.py\n"
    with pytest.raises(ValueError) as exc_info:
        parse_allowlist(text)
    assert "UnknownEvent" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test 8: UserPromptSubmit entry has no matcher field in output
# ---------------------------------------------------------------------------


def test_user_prompt_submit_no_matcher_field():
    """UserPromptSubmit entry produces a block without a 'matcher' key."""
    text = "UserPromptSubmit:auto-plan-detector.py\n"
    entries = parse_allowlist(text)
    result = build_hooks_json(entries, codex_hooks_dir="/fake/hooks")

    assert "UserPromptSubmit" in result["hooks"]
    blocks = result["hooks"]["UserPromptSubmit"]
    assert len(blocks) == 1
    assert "matcher" not in blocks[0], "UserPromptSubmit blocks must not have a 'matcher' field."
    assert "hooks" in blocks[0]


def test_stop_entry_no_matcher_field():
    """Stop entry produces a block without a 'matcher' key."""
    text = "Stop:suggest-compact.py\n"
    entries = parse_allowlist(text)
    result = build_hooks_json(entries, codex_hooks_dir="/fake/hooks")

    blocks = result["hooks"]["Stop"]
    assert len(blocks) == 1
    assert "matcher" not in blocks[0]


# ---------------------------------------------------------------------------
# Test 9: End-to-end CLI with --dry-run produces valid JSON
# ---------------------------------------------------------------------------


def test_cli_dry_run_produces_valid_json():
    """CLI invocation with --dry-run prints valid JSON to stdout."""
    allowlist_text = (
        "# Phase 1 hooks\n"
        "SessionStart:kairos-briefing-injector.py\n"
        "UserPromptSubmit:auto-plan-detector.py\n"
        "PreToolUse:pretool-bash-injection-scan.py Bash\n"
        "Stop:suggest-compact.py\n"
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        allowlist_path = Path(tmpdir) / "allowlist.txt"
        allowlist_path.write_text(allowlist_text, encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPT_PATH),
                "--allowlist",
                str(allowlist_path),
                "--dry-run",
                "--codex-hooks-dir",
                "/fake/hooks",
            ],
            capture_output=True,
            text=True,
        )

    assert result.returncode == 0, f"CLI exited non-zero: {result.stderr}"
    parsed = json.loads(result.stdout)

    assert "hooks" in parsed
    assert "SessionStart" in parsed["hooks"]
    assert "UserPromptSubmit" in parsed["hooks"]
    assert "PreToolUse" in parsed["hooks"]
    assert "Stop" in parsed["hooks"]

    # Verify structure depth: hooks.SessionStart[0].hooks[0].command
    session_hook = parsed["hooks"]["SessionStart"][0]["hooks"][0]
    assert session_hook["type"] == "command"
    assert "kairos-briefing-injector.py" in session_hook["command"]
    assert session_hook["timeout"] == 600


# ---------------------------------------------------------------------------
# Test 10: Event ordering is canonical
# ---------------------------------------------------------------------------


def test_event_ordering():
    """Events appear in SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, Stop order."""
    text = (
        "Stop:suggest-compact.py\n"
        "PostToolUse:posttool-bash-injection-scan.py Bash\n"
        "SessionStart:kairos-briefing-injector.py\n"
        "PreToolUse:pretool-bash-injection-scan.py Bash\n"
        "UserPromptSubmit:auto-plan-detector.py\n"
    )
    entries = parse_allowlist(text)
    result = build_hooks_json(entries, codex_hooks_dir="/fake/hooks")

    keys = list(result["hooks"].keys())
    expected_order = ["SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop"]
    assert keys == expected_order, f"Got order: {keys}"


# ---------------------------------------------------------------------------
# Test 11: Command shape uses python3 and the configured hooks dir
# ---------------------------------------------------------------------------


def test_command_shape_uses_configured_dir():
    """Hook command uses python3 and the codex-hooks-dir path."""
    text = "SessionStart:kairos-briefing-injector.py\n"
    entries = parse_allowlist(text)
    result = build_hooks_json(entries, codex_hooks_dir="/home/testuser/.codex/hooks")

    hook = result["hooks"]["SessionStart"][0]["hooks"][0]
    cmd = hook["command"]
    assert cmd.startswith("python3 "), f"Command should start with 'python3 ': {cmd}"
    assert "/home/testuser/.codex/hooks/kairos-briefing-injector.py" in cmd


def test_command_shape_default_dir_uses_home():
    """Hook command uses $HOME/.codex/hooks when codex_hooks_dir is not specified."""
    import os

    home = os.environ.get("HOME", "~")
    text = "SessionStart:kairos-briefing-injector.py\n"
    entries = parse_allowlist(text)
    result = build_hooks_json(entries)

    hook = result["hooks"]["SessionStart"][0]["hooks"][0]
    cmd = hook["command"]
    assert f"{home}/.codex/hooks/kairos-briefing-injector.py" in cmd
