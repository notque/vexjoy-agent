"""Marker-line scope test for pretool-dispatch-spec-gate.

Added from the E2 mutation check. The complexity token counts only on the marker's
own line. Without this test, a hook that scanned the whole prompt for
`complexity=` passed every existing test.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "pretool-dispatch-spec-gate.py"


def _stdout(prompt: str, env_override: dict[str, str] | None = None) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith("DISPATCH_SPEC_GATE")}
    if env_override:
        env.update(env_override)
    event = {"tool_name": "Agent", "tool_input": {"prompt": prompt}}
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def test_complexity_token_on_a_later_line_does_not_gate_the_dispatch():
    prompt = "[do-route] agent=x skill=y\ncomplexity=complex\nplain body without handoff blocks"
    assert _stdout(prompt) == ""


def test_complexity_token_on_the_marker_line_gates_the_dispatch(tmp_path: Path):
    prompt = "[do-route] agent=x complexity=complex\nplain body without handoff blocks"
    out = json.loads(_stdout(prompt, {"CLAUDE_LEARNING_DIR": str(tmp_path)}))["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"
    assert "missing 3 handoff block(s)" in out["permissionDecisionReason"]


def test_complexity_token_on_the_marker_line_warns_when_mode_is_warn():
    prompt = "[do-route] agent=x complexity=complex\nplain body without handoff blocks"
    out = json.loads(_stdout(prompt, {"DISPATCH_SPEC_GATE_MODE": "warn"}))["hookSpecificOutput"]
    assert "permissionDecision" not in out
    assert "missing 3 handoff block(s)" in out["additionalContext"]
