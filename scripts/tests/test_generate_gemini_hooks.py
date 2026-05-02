"""Tests for scripts/generate-gemini-settings-hooks.py."""

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

_SCRIPT_PATH = Path(__file__).parent.parent / "generate-gemini-settings-hooks.py"


def _load_module():
    """Load generate-gemini-settings-hooks.py as a module."""
    spec = importlib.util.spec_from_file_location("generate_gemini_settings_hooks", _SCRIPT_PATH)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


_mod = _load_module()
parse_allowlist = _mod.parse_allowlist
build_hooks_json = _mod.build_hooks_json
merge_settings = _mod.merge_settings


# ---------------------------------------------------------------------------
# Test 1: Empty allowlist
# ---------------------------------------------------------------------------


def test_empty_allowlist_produces_empty_hooks():
    """Empty allowlist text produces empty dict."""
    entries = parse_allowlist("")
    result = build_hooks_json(entries)
    assert result == {}


def test_comments_and_blanks_only_produces_empty():
    """Allowlist with only comments and blank lines produces empty hooks."""
    text = "# This is a comment\n\n# Another comment\n"
    entries = parse_allowlist(text)
    result = build_hooks_json(entries)
    assert result == {}


# ---------------------------------------------------------------------------
# Test 2: Single SessionStart with no matcher
# ---------------------------------------------------------------------------


def test_single_session_start_no_matcher():
    """SessionStart entry with no matcher omits matcher field entirely."""
    text = "SessionStart:session-github-briefing.py\n"
    entries = parse_allowlist(text)
    result = build_hooks_json(entries, gemini_hooks_dir="/home/user/.gemini/hooks")

    assert "SessionStart" in result
    blocks = result["SessionStart"]
    assert len(blocks) == 1
    block = blocks[0]
    assert "matcher" not in block, "SessionStart blocks must not have a 'matcher' field."
    assert len(block["hooks"]) == 1
    hook = block["hooks"][0]
    assert hook["type"] == "command"
    assert "session-github-briefing.py" in hook["command"]
    assert hook["timeout"] == 600


# ---------------------------------------------------------------------------
# Test 3: Multiple SessionStart entries grouped into one block
# ---------------------------------------------------------------------------


def test_multiple_session_start_entries_grouped():
    """Multiple SessionStart entries are grouped into one matcher block."""
    text = (
        "SessionStart:session-github-briefing.py\n"
        "SessionStart:operator-context-detector.py\n"
        "SessionStart:team-config-loader.py\n"
    )
    entries = parse_allowlist(text)
    result = build_hooks_json(entries, gemini_hooks_dir="/fake/hooks")

    blocks = result["SessionStart"]
    assert len(blocks) == 1, "All SessionStart entries share no matcher, so only one block."
    hook_list = blocks[0]["hooks"]
    assert len(hook_list) == 3
    names = [h["command"] for h in hook_list]
    assert any("session-github-briefing.py" in n for n in names)
    assert any("operator-context-detector.py" in n for n in names)
    assert any("team-config-loader.py" in n for n in names)


# ---------------------------------------------------------------------------
# Test 4: AfterTool without matcher raises ValueError
# ---------------------------------------------------------------------------


def test_aftertool_without_matcher_raises():
    """AfterTool entry without matcher raises ValueError mentioning 'run_shell_command'."""
    text = "AfterTool:posttool-bash-injection-scan.py\n"
    with pytest.raises(ValueError) as exc_info:
        parse_allowlist(text)
    assert "run_shell_command" in str(exc_info.value)


def test_beforetool_without_matcher_raises():
    """BeforeTool entry without matcher raises ValueError."""
    text = "BeforeTool:some-hook.py\n"
    with pytest.raises(ValueError) as exc_info:
        parse_allowlist(text)
    assert "BeforeTool" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test 5: AfterTool with matcher produces correct structure
# ---------------------------------------------------------------------------


def test_aftertool_with_matcher():
    """AfterTool with run_shell_command matcher produces correct block."""
    text = "AfterTool:posttool-bash-injection-scan.py run_shell_command\n"
    entries = parse_allowlist(text)
    result = build_hooks_json(entries, gemini_hooks_dir="/fake/hooks")

    assert "AfterTool" in result
    blocks = result["AfterTool"]
    assert len(blocks) == 1
    assert blocks[0]["matcher"] == "run_shell_command"
    assert len(blocks[0]["hooks"]) == 1


# ---------------------------------------------------------------------------
# Test 6: SessionEnd entry has no matcher field in output
# ---------------------------------------------------------------------------


def test_session_end_no_matcher_field():
    """SessionEnd entry produces a block without a 'matcher' key."""
    text = "SessionEnd:session-learning-recorder.py\n"
    entries = parse_allowlist(text)
    result = build_hooks_json(entries, gemini_hooks_dir="/fake/hooks")

    assert "SessionEnd" in result
    blocks = result["SessionEnd"]
    assert len(blocks) == 1
    assert "matcher" not in blocks[0], "SessionEnd blocks must not have a 'matcher' field."
    assert "hooks" in blocks[0]


# ---------------------------------------------------------------------------
# Test 7: Unknown event raises ValueError
# ---------------------------------------------------------------------------


def test_unknown_event_raises():
    """An unknown event name raises ValueError."""
    text = "UnknownEvent:some-hook.py\n"
    with pytest.raises(ValueError) as exc_info:
        parse_allowlist(text)
    assert "UnknownEvent" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test 8: Malformed line raises ValueError with line number
# ---------------------------------------------------------------------------


def test_malformed_line_raises_with_line_number():
    """A line without ':' raises ValueError that includes the line number."""
    text = "# comment\n\nbadline-no-colon\n"
    with pytest.raises(ValueError) as exc_info:
        parse_allowlist(text)
    msg = str(exc_info.value)
    assert "3" in msg, f"Expected line number 3 in error: {msg}"


# ---------------------------------------------------------------------------
# Test 9: Comments and blank lines are ignored
# ---------------------------------------------------------------------------


def test_comments_and_blank_lines_ignored():
    """Lines starting with # and empty lines do not become entries."""
    text = (
        "# Phase 1: safe on Gemini CLI v0.26.0+\n"
        "\n"
        "SessionStart:session-github-briefing.py\n"
        "\n"
        "# Another comment\n"
        "SessionEnd:session-learning-recorder.py\n"
    )
    entries = parse_allowlist(text)
    assert len(entries) == 2
    events = [e["event"] for e in entries]
    assert "SessionStart" in events
    assert "SessionEnd" in events


# ---------------------------------------------------------------------------
# Test 10: merge_settings preserves existing keys
# ---------------------------------------------------------------------------


def test_merge_preserves_existing_keys():
    """merge_settings preserves all keys except 'hooks'."""
    existing = {
        "theme": "dark",
        "apiKey": "sk-test",
        "model": "gemini-2.5-pro",
        "hooks": {"old": "data"},
    }
    hooks_data = {"SessionStart": [{"hooks": [{"type": "command", "command": "test"}]}]}

    result = merge_settings(existing, hooks_data)

    assert result["theme"] == "dark"
    assert result["apiKey"] == "sk-test"
    assert result["model"] == "gemini-2.5-pro"
    assert result["hooks"] == hooks_data
    # Original dict not mutated
    assert existing["hooks"] == {"old": "data"}


def test_merge_adds_hooks_to_empty_settings():
    """merge_settings works with empty existing settings."""
    hooks_data = {"SessionStart": [{"hooks": [{"type": "command", "command": "test"}]}]}
    result = merge_settings({}, hooks_data)
    assert result == {"hooks": hooks_data}


# ---------------------------------------------------------------------------
# Test 11: Event ordering is canonical
# ---------------------------------------------------------------------------


def test_event_ordering():
    """Events appear in the canonical Gemini order."""
    text = (
        "SessionEnd:session-learning-recorder.py\n"
        "AfterTool:posttool-bash-injection-scan.py run_shell_command\n"
        "SessionStart:session-github-briefing.py\n"
    )
    entries = parse_allowlist(text)
    result = build_hooks_json(entries, gemini_hooks_dir="/fake/hooks")

    keys = list(result.keys())
    # SessionStart should come before SessionEnd, SessionEnd before AfterTool
    assert keys.index("SessionStart") < keys.index("SessionEnd")
    assert keys.index("SessionEnd") < keys.index("AfterTool")


# ---------------------------------------------------------------------------
# Test 12: Command shape uses python3 and the configured hooks dir
# ---------------------------------------------------------------------------


def test_command_shape_uses_configured_dir():
    """Hook command uses python3 and the gemini-hooks-dir path."""
    text = "SessionStart:session-github-briefing.py\n"
    entries = parse_allowlist(text)
    result = build_hooks_json(entries, gemini_hooks_dir="/home/testuser/.gemini/hooks")

    hook = result["SessionStart"][0]["hooks"][0]
    cmd = hook["command"]
    assert cmd.startswith("python3 "), f"Command should start with 'python3 ': {cmd}"
    assert "/home/testuser/.gemini/hooks/session-github-briefing.py" in cmd


def test_command_shape_default_dir_uses_home():
    """Hook command uses $HOME/.gemini/hooks when gemini_hooks_dir is not specified."""
    import os

    home = os.environ.get("HOME", "~")
    text = "SessionStart:session-github-briefing.py\n"
    entries = parse_allowlist(text)
    result = build_hooks_json(entries)

    hook = result["SessionStart"][0]["hooks"][0]
    cmd = hook["command"]
    assert f"{home}/.gemini/hooks/session-github-briefing.py" in cmd


# ---------------------------------------------------------------------------
# Test 13: End-to-end CLI with --dry-run produces valid JSON
# ---------------------------------------------------------------------------


def test_cli_dry_run_produces_valid_json():
    """CLI invocation with --dry-run prints valid JSON to stdout."""
    allowlist_text = (
        "# Phase 1 hooks\n"
        "SessionStart:session-github-briefing.py\n"
        "SessionEnd:session-learning-recorder.py\n"
        "AfterTool:posttool-bash-injection-scan.py run_shell_command\n"
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
                "--gemini-hooks-dir",
                "/fake/hooks",
            ],
            capture_output=True,
            text=True,
        )

    assert result.returncode == 0, f"CLI exited non-zero: {result.stderr}"
    parsed = json.loads(result.stdout)

    assert "hooks" in parsed
    assert "SessionStart" in parsed["hooks"]
    assert "SessionEnd" in parsed["hooks"]
    assert "AfterTool" in parsed["hooks"]

    # Verify structure depth: hooks.SessionStart[0].hooks[0].command
    session_hook = parsed["hooks"]["SessionStart"][0]["hooks"][0]
    assert session_hook["type"] == "command"
    assert "session-github-briefing.py" in session_hook["command"]
    assert session_hook["timeout"] == 600


# ---------------------------------------------------------------------------
# Test 14: CLI --dry-run preserves existing settings keys
# ---------------------------------------------------------------------------


def test_cli_dry_run_preserves_existing_settings():
    """CLI invocation with --dry-run preserves existing settings.json keys."""
    allowlist_text = "SessionStart:session-github-briefing.py\n"
    existing_settings = {"theme": "dark", "model": "gemini-2.5-pro"}

    with tempfile.TemporaryDirectory() as tmpdir:
        allowlist_path = Path(tmpdir) / "allowlist.txt"
        allowlist_path.write_text(allowlist_text, encoding="utf-8")

        settings_path = Path(tmpdir) / "settings.json"
        settings_path.write_text(json.dumps(existing_settings), encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPT_PATH),
                "--allowlist",
                str(allowlist_path),
                "--output",
                str(settings_path),
                "--dry-run",
                "--gemini-hooks-dir",
                "/fake/hooks",
            ],
            capture_output=True,
            text=True,
        )

    assert result.returncode == 0, f"CLI exited non-zero: {result.stderr}"
    parsed = json.loads(result.stdout)

    assert parsed["theme"] == "dark"
    assert parsed["model"] == "gemini-2.5-pro"
    assert "hooks" in parsed


# ---------------------------------------------------------------------------
# Test 15: All known events are valid
# ---------------------------------------------------------------------------


def test_all_known_events_are_accepted():
    """Every event in ALL_KNOWN_EVENTS is accepted by parse_allowlist (where possible)."""
    # Events that don't require matcher (including agent/model lifecycle events)
    no_matcher_events = [
        "SessionStart",
        "SessionEnd",
        "BeforeAgent",
        "AfterAgent",
        "BeforeModel",
        "AfterModel",
        "Notification",
        "PreCompress",
        "BeforeToolSelection",
    ]
    for event in no_matcher_events:
        text = f"{event}:test-hook.py\n"
        entries = parse_allowlist(text)
        assert len(entries) == 1
        assert entries[0]["event"] == event

    # Events that require matcher
    matcher_events = ["BeforeTool", "AfterTool"]
    for event in matcher_events:
        text = f"{event}:test-hook.py run_shell_command\n"
        entries = parse_allowlist(text)
        assert len(entries) == 1
        assert entries[0]["event"] == event
        assert entries[0]["matcher"] == "run_shell_command"


def test_agent_model_events_no_matcher_in_output():
    """BeforeAgent, AfterAgent, BeforeModel, AfterModel produce blocks without matcher."""
    for event in ("BeforeAgent", "AfterAgent", "BeforeModel", "AfterModel"):
        text = f"{event}:test-hook.py\n"
        entries = parse_allowlist(text)
        result = build_hooks_json(entries, gemini_hooks_dir="/fake/hooks")
        assert event in result
        blocks = result[event]
        assert len(blocks) == 1
        assert "matcher" not in blocks[0], f"{event} blocks must not have a 'matcher' field."
