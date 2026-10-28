"""Tests for the Claude/Anthropic model-skip guard in gemini-turn-gate-userprompt.py.

Covers hook version 1.1.0 addition: _CLAUDE_MODEL_RE and the early-return guard
in main() that emits valid JSON empty output when the model field matches
claude/anthropic/sonnet/haiku/opus/fable (case-insensitive).

Test cases:
1. claude model string   -> skips injection (valid JSON, no routing mandate)
2. gemini model string   -> proceeds normally (mandate injected for non-trivial prompt)
3. anthropic model string -> skips injection (valid JSON, no routing mandate)
4. empty model string    -> proceeds normally (mandate injected for non-trivial prompt)
5. fable model string    -> skips injection (valid JSON, no routing mandate)
6. ANTHROPIC_MODEL env var -> skips injection when event has no model key
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TURN_GATE = ROOT / "hooks" / "gemini-turn-gate-userprompt.py"

_NON_TRIVIAL_PROMPT = "Refactor the authentication module and add unit tests for OAuth"


def _run(
    payload: dict,
    env_override: dict[str, str] | None = None,
    env_remove: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    for key in env_remove or []:
        env.pop(key, None)
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


def _assert_valid_json_skip(res: subprocess.CompletedProcess[str]) -> None:
    """Assert exit 0, valid JSON stdout, and no routing mandate."""
    assert res.returncode == 0
    assert "[VEXJOY ROUTING MANDATE]" not in res.stdout
    parsed = json.loads(res.stdout)
    assert isinstance(parsed, dict)


class TestClaudeModelSkipGuard:
    """Model-skip guard: claude/anthropic/fable model strings produce valid-JSON empty output."""

    def test_claude_model_skips_injection(self, tmp_path: Path) -> None:
        """Model containing 'claude' produces valid JSON empty output, no mandate."""
        res = _run(
            {
                "session_id": "test-skip-claude",
                "model": "claude-sonnet-4-5",
                "prompt": _NON_TRIVIAL_PROMPT,
            },
            {"VEXJOY_ROUTING_STATE_DIR": str(tmp_path / "state")},
            env_remove=["ANTHROPIC_MODEL", "CLAUDE_MODEL"],
        )
        _assert_valid_json_skip(res)

    def test_anthropic_model_skips_injection(self, tmp_path: Path) -> None:
        """Model containing 'anthropic' produces valid JSON empty output, no mandate."""
        res = _run(
            {
                "session_id": "test-skip-anthropic",
                "model": "us.anthropic.claude-3-opus",
                "prompt": _NON_TRIVIAL_PROMPT,
            },
            {"VEXJOY_ROUTING_STATE_DIR": str(tmp_path / "state")},
            env_remove=["ANTHROPIC_MODEL", "CLAUDE_MODEL"],
        )
        _assert_valid_json_skip(res)

    def test_fable_model_skips_injection(self, tmp_path: Path) -> None:
        """Model containing 'fable' produces valid JSON empty output, no mandate."""
        res = _run(
            {
                "session_id": "test-skip-fable",
                "model": "fable",
                "prompt": _NON_TRIVIAL_PROMPT,
            },
            {"VEXJOY_ROUTING_STATE_DIR": str(tmp_path / "state")},
            env_remove=["ANTHROPIC_MODEL", "CLAUDE_MODEL"],
        )
        _assert_valid_json_skip(res)

    def test_anthropic_model_env_var_skips_injection(self, tmp_path: Path) -> None:
        """ANTHROPIC_MODEL env var triggers skip when event has no model key."""
        res = _run(
            {
                "session_id": "test-skip-env",
                "prompt": _NON_TRIVIAL_PROMPT,
            },
            {
                "VEXJOY_ROUTING_STATE_DIR": str(tmp_path / "state"),
                "ANTHROPIC_MODEL": "claude-opus-4",
            },
            env_remove=["CLAUDE_MODEL"],
        )
        _assert_valid_json_skip(res)

    def test_gemini_model_injects_mandate(self, tmp_path: Path) -> None:
        """Gemini model string proceeds normally and injects the routing mandate."""
        res = _run(
            {
                "session_id": "test-gemini",
                "model": "gemini-2.0-flash",
                "prompt": _NON_TRIVIAL_PROMPT,
            },
            {"VEXJOY_ROUTING_STATE_DIR": str(tmp_path / "state")},
            env_remove=["ANTHROPIC_MODEL", "CLAUDE_MODEL"],
        )
        assert res.returncode == 0
        assert "[VEXJOY ROUTING MANDATE]" in res.stdout

    def test_empty_model_injects_mandate(self, tmp_path: Path) -> None:
        """Absent model field proceeds normally and injects the routing mandate."""
        res = _run(
            {
                "session_id": "test-no-model",
                "prompt": _NON_TRIVIAL_PROMPT,
            },
            {"VEXJOY_ROUTING_STATE_DIR": str(tmp_path / "state")},
            env_remove=["ANTHROPIC_MODEL", "CLAUDE_MODEL"],
        )
        assert res.returncode == 0
        assert "[VEXJOY ROUTING MANDATE]" in res.stdout
