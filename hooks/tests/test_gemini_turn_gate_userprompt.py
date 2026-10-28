"""Tests for the Claude/Anthropic model-skip guard in gemini-turn-gate-userprompt.py.

Covers hook version 1.1.0 addition: _CLAUDE_MODEL_RE and the early-return guard
in main() that emits empty output when the model field matches claude/anthropic/
sonnet/haiku/opus (case-insensitive).

Test cases:
1. claude model string  -> skips injection (empty output, no routing mandate)
2. gemini model string  -> proceeds normally (mandate injected for non-trivial prompt)
3. anthropic model string -> skips injection
4. empty model string   -> proceeds normally (mandate injected for non-trivial prompt)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TURN_GATE = ROOT / "hooks" / "gemini-turn-gate-userprompt.py"

_NON_TRIVIAL_PROMPT = "Refactor the authentication module and add unit tests for OAuth"


def _run(
    payload: dict,
    env_override: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    if env_override:
        env.update(env_override)
    return subprocess.run(
        [sys.executable, str(TURN_GATE)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


class TestClaudeModelSkipGuard:
    """Model-skip guard: claude/anthropic model strings skip injection."""

    def test_claude_model_skips_injection(self, tmp_path: Path) -> None:
        """A model field containing 'claude' produces empty output."""
        res = _run(
            {
                "session_id": "test-skip-claude",
                "model": "claude-sonnet-4-5",
                "prompt": _NON_TRIVIAL_PROMPT,
            },
            {"VEXJOY_ROUTING_STATE_DIR": str(tmp_path / "state")},
        )
        assert res.returncode == 0
        assert "[VEXJOY ROUTING MANDATE]" not in res.stdout

    def test_anthropic_model_skips_injection(self, tmp_path: Path) -> None:
        """A model field containing 'anthropic' produces empty output."""
        res = _run(
            {
                "session_id": "test-skip-anthropic",
                "model": "us.anthropic.claude-3-opus",
                "prompt": _NON_TRIVIAL_PROMPT,
            },
            {"VEXJOY_ROUTING_STATE_DIR": str(tmp_path / "state")},
        )
        assert res.returncode == 0
        assert "[VEXJOY ROUTING MANDATE]" not in res.stdout

    def test_gemini_model_injects_mandate(self, tmp_path: Path) -> None:
        """A gemini model string proceeds normally and injects the routing mandate."""
        res = _run(
            {
                "session_id": "test-gemini",
                "model": "gemini-2.0-flash",
                "prompt": _NON_TRIVIAL_PROMPT,
            },
            {"VEXJOY_ROUTING_STATE_DIR": str(tmp_path / "state")},
        )
        assert res.returncode == 0
        assert "[VEXJOY ROUTING MANDATE]" in res.stdout

    def test_empty_model_injects_mandate(self, tmp_path: Path) -> None:
        """An absent model field proceeds normally and injects the routing mandate."""
        res = _run(
            {
                "session_id": "test-no-model",
                "prompt": _NON_TRIVIAL_PROMPT,
            },
            {"VEXJOY_ROUTING_STATE_DIR": str(tmp_path / "state")},
        )
        assert res.returncode == 0
        assert "[VEXJOY ROUTING MANDATE]" in res.stdout
