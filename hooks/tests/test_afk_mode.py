#!/usr/bin/env python3
"""
Tests for the afk-mode hook (SessionStart, ADR-143).

Run with: python3 -m pytest hooks/tests/test_afk_mode.py -v
"""

import json
import os
import subprocess
import sys
from pathlib import Path

HOOK_SRC = Path(__file__).parent.parent / "afk-mode.py"

_HOST_VARS = ("SSH_CONNECTION", "SSH_TTY", "SSH_CLIENT", "TMUX", "STY")


def _context(mode: str, extra_env: dict | None = None) -> str | None:
    env = {k: v for k, v in os.environ.items() if k not in _HOST_VARS}
    env.pop("AFK_MODE_BYPASS", None)
    env["CLAUDE_AFK_MODE"] = mode
    env.update(extra_env or {})
    result = subprocess.run(
        [sys.executable, str(HOOK_SRC)],
        input="{}",
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)["hookSpecificOutput"].get("additionalContext")


def test_always_mode_states_the_setting_not_an_observation():
    """B-12: nothing detects focus, so the text must not claim the terminal is unfocused."""
    context = _context("always")
    assert context.startswith("<afk-mode>\n") and context.endswith("\n</afk-mode>")
    assert 'AFK mode is set to "always" (CLAUDE_AFK_MODE)' in context
    assert "unfocused" not in context
    assert "is not actively watching" not in context
    # The proactive-work guidance stays.
    assert "Work proactively. Complete multi-step tasks without asking for confirmation." in context
    assert "If you can determine the next logical step, take it." in context
    assert "CLAUDE.md" in context


def test_auto_mode_names_what_it_detected():
    context = _context("auto", {"TMUX": "/tmp/tmux-1000/default,1,0"})
    assert 'AFK mode is "auto" (CLAUDE_AFK_MODE) and this session runs over SSH, tmux or screen' in context
    assert "unfocused" not in context
    assert "Work proactively." in context


def test_auto_mode_without_indicators_injects_nothing():
    assert _context("auto") is None


def test_never_mode_exits_0():
    """Baseline: CLAUDE_AFK_MODE=never exits 0 with empty SessionStart output."""
    result = subprocess.run(
        [sys.executable, str(HOOK_SRC)],
        capture_output=True,
        text=True,
        env={**os.environ, "CLAUDE_AFK_MODE": "never"},
    )
    assert result.returncode == 0
    assert "SessionStart" in result.stdout


def test_exits_0_on_injected_exception(tmp_path):
    """A crash inside main() must still fail open (exit 0): the __main__
    guard's except-block must catch it and print a visibility signal,
    not just silently swallow it."""
    # Copy the real hook unmodified; point its own `lib/` import at a stub
    # hook_utils that raises, so main()'s call into it crashes for real.
    hook_copy = tmp_path / "afk-mode.py"
    hook_copy.write_text(HOOK_SRC.read_text())
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    (lib_dir / "hook_utils.py").write_text(
        "import sys\n"
        "def context_output(*a, **k):\n"
        "    raise RuntimeError('injected failure')\n"
        "def empty_output(*a, **k):\n"
        "    raise RuntimeError('injected failure')\n"
        "def hook_error(name, exc):\n"
        "    print(f'[{name}] HOOK-ERROR: {type(exc).__name__}: {exc}', file=sys.stderr)\n"
    )

    result = subprocess.run(
        [sys.executable, str(hook_copy)],
        capture_output=True,
        text=True,
        env={**os.environ, "CLAUDE_AFK_MODE": "always"},
    )

    assert result.returncode == 0
    assert "[afk-mode] HOOK-ERROR: RuntimeError" in result.stderr
