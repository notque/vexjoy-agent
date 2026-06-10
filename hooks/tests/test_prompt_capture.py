#!/usr/bin/env python3
"""Tests for the prompt-capture UserPromptSubmit hook machine-prompt filter.

An audit found 217 of 279 voice-sample rows were machine text: headless
`claude -p` jobs and agent-generated prompts fire UserPromptSubmit just like
human turns. These tests pin the filter that keeps machine prompts out of the
voice corpus while never filtering genuine human prompts.

Run with: python3 -m pytest hooks/tests/test_prompt_capture.py -v
"""

import importlib.util
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

HOOK_PATH = Path(__file__).parent.parent / "prompt-capture.py"

spec = importlib.util.spec_from_file_location("prompt_capture", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)

with patch("sys.exit"):
    spec.loader.exec_module(mod)


# ---------------------------------------------------------------------------
# Real pollution examples (verbatim shapes from the live voice corpus)
# ---------------------------------------------------------------------------

AUTO_DREAM = (
    "You are running the Auto-Dream memory consolidation cycle.\n"
    "This is a headless background job — no interactive session, no CLAUDE.md, "
    "no hooks.\nAll instructions are contained in this prompt."
)

TOOLKIT_EVOLUTION = (
    "You are running the nightly toolkit evolution cycle for the vexjoy-agent.\n\n"
    "Read and execute the skill at skills/meta/toolkit-evolution/SKILL.md — it "
    "defines the full 6-phase pipeline for this run."
)

SKILL_ANALYSIS = (
    "You are analyzing a Claude Code skill file to extract cross-cutting "
    "behavioral principles.\n\nSkill: csuite\n\n<skill_content>\n---\nname: csuite\n"
    "description: C-suite executive decision frameworks\n---\n</skill_content>"
)

ROUTING_AGENT = (
    "You are a routing agent. Classify the request below and pick the best "
    "agent for the job from the manifest.\n\nROUTING MANIFEST:\n"
    "- go-engineer: Go source changes\n- hook-development-engineer: hooks\n"
)

AUTONOMOUS_LOOP = (
    "# Autonomous loop check\n\n"
    "You're being invoked on a timer while the user is away or occupied. "
    "The point is to keep work moving forward without the user present."
)

DO_ROUTE_DISPATCH = (
    "[do-route] agent=hook-development-engineer skill=test-driven-development "
    "complexity=Medium health=- action=keep\n\nBefore starting work, read your "
    "agent file and load matching references for the task at hand."
)

MACHINE_PROMPTS = [
    AUTO_DREAM,
    TOOLKIT_EVOLUTION,
    SKILL_ANALYSIS,
    ROUTING_AGENT,
    AUTONOMOUS_LOOP,
    DO_ROUTE_DISPATCH,
]

# Genuine casual human prompts (realistic shapes from the corpus, paraphrased)
HUMAN_LONG = (
    "we have blind a/b tests already, so make sure the new welcome screen goes "
    "through the same pipeline before we ship it to everyone please"
)
HUMAN_SHORT = "login done, take us home"
HUMAN_LOWERCASE_YOU = (
    "you are wrong about the ranking dropdown, it should be ordered by name "
    "and the ranking option should not be there at all in that mode"
)

HUMAN_PROMPTS = [HUMAN_LONG, HUMAN_SHORT, HUMAN_LOWERCASE_YOU]


# ---------------------------------------------------------------------------
# Unit tests: is_machine_prompt
# ---------------------------------------------------------------------------


class TestMachinePromptFilter:
    @pytest.mark.parametrize("prompt", MACHINE_PROMPTS)
    def test_real_pollution_is_machine(self, prompt):
        assert mod.is_machine_prompt(prompt) is True

    @pytest.mark.parametrize("prompt", HUMAN_PROMPTS)
    def test_human_prompts_are_not_machine(self, prompt):
        assert mod.is_machine_prompt(prompt) is False

    def test_short_casual_human_prompt_never_filtered(self):
        # Hard requirement: short casual human text must never be machine.
        assert mod.is_machine_prompt(HUMAN_SHORT) is False

    def test_length_ceiling_rejects_generated_spec(self):
        spec_text = "carry out the migration step " * 150  # 750 words
        assert mod.is_machine_prompt(spec_text) is True

    def test_human_length_prompt_under_ceiling_passes(self):
        text = "please keep the share buttons but add twitter and facebook " * 20
        assert mod.word_count(text) < 500
        assert mod.is_machine_prompt(text) is False

    def test_empty_and_whitespace_are_safe(self):
        assert mod.is_machine_prompt("") is False
        assert mod.is_machine_prompt("   \n\t  ") is False


# ---------------------------------------------------------------------------
# Integration: is_natural_language composite guard
# ---------------------------------------------------------------------------


class TestNaturalLanguageGuard:
    @pytest.mark.parametrize("prompt", MACHINE_PROMPTS)
    def test_machine_prompts_rejected(self, prompt):
        assert mod.is_natural_language(prompt) is False

    def test_genuine_human_prompt_accepted(self):
        assert mod.is_natural_language(HUMAN_LONG) is True


# ---------------------------------------------------------------------------
# End-to-end: run the hook as a subprocess against a temp learning DB
# ---------------------------------------------------------------------------


def _run_hook(stdin_text: str, learning_dir: Path, cwd: Path) -> subprocess.CompletedProcess:
    env = {
        "CLAUDE_LEARNING_DIR": str(learning_dir),
        "PATH": "/usr/bin:/bin",
        "HOME": str(learning_dir),
    }
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=stdin_text,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(cwd),
        timeout=30,
    )


def _voice_rows(learning_dir: Path) -> list[str]:
    db = learning_dir / "learning.db"
    if not db.exists():
        return []
    with sqlite3.connect(db) as conn:
        return [r[0] for r in conn.execute("SELECT value FROM learnings WHERE topic='voice-sample'")]


@pytest.fixture()
def repo_cwd(tmp_path: Path) -> Path:
    """A fake git repo so the in-repo capture guard passes."""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    return repo


@pytest.fixture()
def learning_dir(tmp_path: Path) -> Path:
    d = tmp_path / "learning"
    d.mkdir()
    return d


class TestEndToEnd:
    def test_machine_prompt_not_captured_and_exit_zero(self, learning_dir, repo_cwd):
        payload = json.dumps({"prompt": AUTO_DREAM, "cwd": str(repo_cwd), "session_id": "s1"})
        result = _run_hook(payload, learning_dir, repo_cwd)
        assert result.returncode == 0
        assert _voice_rows(learning_dir) == []

    def test_human_prompt_captured_and_exit_zero(self, learning_dir, repo_cwd):
        payload = json.dumps({"prompt": HUMAN_LONG, "cwd": str(repo_cwd), "session_id": "s1"})
        result = _run_hook(payload, learning_dir, repo_cwd)
        assert result.returncode == 0
        rows = _voice_rows(learning_dir)
        assert len(rows) == 1
        assert rows[0].startswith("we have blind a/b tests")

    def test_empty_stdin_exits_zero(self, learning_dir, repo_cwd):
        result = _run_hook("", learning_dir, repo_cwd)
        assert result.returncode == 0
        assert _voice_rows(learning_dir) == []

    def test_malformed_json_exits_zero(self, learning_dir, repo_cwd):
        result = _run_hook("{not json", learning_dir, repo_cwd)
        assert result.returncode == 0
        assert _voice_rows(learning_dir) == []

    def test_missing_prompt_field_exits_zero(self, learning_dir, repo_cwd):
        result = _run_hook(json.dumps({"cwd": str(repo_cwd)}), learning_dir, repo_cwd)
        assert result.returncode == 0
        assert _voice_rows(learning_dir) == []
