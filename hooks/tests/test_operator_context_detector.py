#!/usr/bin/env python3
"""Tests for the operator-context-detector SessionStart hook.

The personal profile used to tell every session "Full autonomy. No approval
gates.", which contradicts the approval phrases /home/feedgen/CLAUDE.md
reserves for the owner (B-12 / I-02). It now grants autonomy within branch
safety and the CLAUDE.md approval rules.

Run with: python3 -m pytest hooks/tests/test_operator_context_detector.py -v
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK_PATH = Path(__file__).resolve().parent.parent / "operator-context-detector.py"

spec = importlib.util.spec_from_file_location("operator_context_detector", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

_FALSE_CLAIMS = ("No approval gates", "Full autonomy", "No additional approval steps required")


def test_personal_summary_keeps_the_claude_md_approval_rules() -> None:
    injection = mod.get_profile_injection("personal", "default")
    first_line = injection.splitlines()[0]
    assert first_line.startswith("[operator-context] Profile: personal — ")
    assert "branch safety" in first_line
    assert "CLAUDE.md approval rules" in first_line
    for claim in _FALSE_CLAIMS:
        assert claim not in injection
    assert injection.splitlines()[1] == "[operator-context] Detection: default"


def test_unknown_profile_falls_back_to_the_personal_summary() -> None:
    personal = mod.get_profile_injection("personal", "x").splitlines()[0].split(" — ", 1)[1]
    unknown = mod.get_profile_injection("mystery", "OPERATOR_PROFILE=mystery").splitlines()[0]
    assert unknown == f"[operator-context] Profile: mystery — {personal}"


def test_personal_guidance_names_the_owner_approval_reservation() -> None:
    guidance = mod.PROFILE_GUIDANCE["personal"]
    for claim in _FALSE_CLAIMS:
        assert claim not in guidance
    assert "CLAUDE.md" in guidance
    assert "never commit to main" in guidance


@pytest.mark.skipif(Path("/.dockerenv").exists(), reason="a container is always the ci profile")
def test_hook_injects_the_personal_summary(tmp_path: Path) -> None:
    env = {k: v for k, v in os.environ.items() if k not in ("CI", "GITHUB_ACTIONS", "GITLAB_CI", "PRODUCTION")}
    env.update({"HOME": str(tmp_path), "OPERATOR_PROFILE": "personal", "PROTECTED_ORGS": ""})
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps({"hook_event_name": "SessionStart", "source": "startup"}),
        capture_output=True,
        text=True,
        env=env,
        cwd=tmp_path,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert context.startswith("[operator-context] Profile: personal — ")
    assert "CLAUDE.md approval rules" in context
    assert "No approval gates" not in context
