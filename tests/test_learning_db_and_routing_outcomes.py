#!/usr/bin/env python3
"""Tests for the shared learning-DB storage layer and routing-outcome telemetry.

Formerly test_learning_loop_fixes.py. The learning loop was retired; the
classes that covered its deleted hooks went with it. What remains covers
subsystems that survive on top of learning_db_v2: the context sanitizers,
routing-outcome finalization by the next-turn finalizer (the Stop fallback
lives in hooks/tests/test_routing_decision_recorder.py), and the shared
get_db_dir() path resolver.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Resolve paths
REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = REPO_ROOT / "hooks"
LIB_DIR = HOOKS_DIR / "lib"

# Add lib to path so we can import hook modules
sys.path.insert(0, str(LIB_DIR))
sys.path.insert(0, str(HOOKS_DIR))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_learning_dir(tmp_path):
    """Isolated learning directory for DB tests."""
    db_dir = tmp_path / "learning"
    db_dir.mkdir()
    with patch.dict(os.environ, {"CLAUDE_LEARNING_DIR": str(db_dir)}):
        # Reset the module-level _initialized flag so init_db() runs fresh
        import learning_db_v2

        learning_db_v2._initialized = False
        yield db_dir
        learning_db_v2._initialized = False


# ===========================================================================
# Context sanitizers (learning_db_v2, consumed by session-context.py)
# ===========================================================================


class TestSanitizerCaseInsensitive:
    """sanitize_for_context replaces only lowercase <system> etc.
    <SYSTEM> passes through. Fix: case-insensitive replacement.
    """

    @pytest.mark.parametrize(
        "tag",
        ["system", "SyStEm", "USER", "assistant", "human"],
    )
    def test_role_tag_neutralized(self, tag):
        from learning_db_v2 import sanitize_for_context

        text = f"before <{tag}> middle </{tag}> after"
        result = sanitize_for_context(text)
        # The tag must be gone regardless of case
        lower_result = result.lower()
        assert f"<{tag.lower()}>" not in lower_result, f"<{tag}> was NOT neutralized"
        assert f"</{tag.lower()}>" not in lower_result, f"</{tag}> was NOT neutralized"

    def test_zero_width_chars_stripped(self):
        from learning_db_v2 import sanitize_for_context

        text = "hello​world‍﻿"
        result = sanitize_for_context(text)
        assert "​" not in result
        assert "‍" not in result
        assert "﻿" not in result
        assert "helloworld" in result

    def test_empty_and_none(self):
        from learning_db_v2 import sanitize_for_context

        assert sanitize_for_context("") == ""
        assert sanitize_for_context(None) is None


# ===========================================================================
# Routing-outcome finalization: every pending dispatch reaches a terminal state
# ===========================================================================


class TestOutcomeFinalizerCoverage:
    """567 decisions vs 41 outcomes. Every pending decision must reach a
    terminal state by session end; UserPromptSubmit resolves it here.
    """

    @pytest.fixture()
    def routing_state_dir(self, tmp_path):
        """Isolated routing state dir."""
        state_dir = tmp_path / "routing_state"
        state_dir.mkdir()
        with patch.dict(os.environ, {"CLAUDE_ROUTING_STATE_DIR": str(state_dir)}):
            yield state_dir

    def test_userprompt_resolves_single_pending(self, tmp_learning_dir, routing_state_dir):
        """A single pending dispatch + acceptance prompt -> success outcome."""
        import learning_db_v2

        learning_db_v2._initialized = False
        learning_db_v2.init_db()

        learning_db_v2.record_learning(
            topic="routing",
            key="agent:skill",
            value="test route",
            category="effectiveness",
            confidence=0.5,
            source="test-seed",
        )

        from routing_outcome_state import append_pending_outcome, peek_pending_outcomes

        session_id = "test-session-accept"
        append_pending_outcome(session_id, "agent:skill", errors=False)

        # Simulate UserPromptSubmit with acceptance
        event = {
            "hook_event_name": "UserPromptSubmit",
            "session_id": session_id,
            "prompt": "thanks, that worked",
        }
        env = os.environ.copy()
        env["CLAUDE_LEARNING_DIR"] = str(tmp_learning_dir)
        env["CLAUDE_ROUTING_STATE_DIR"] = str(routing_state_dir)
        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "routing-outcome-finalizer.py")],
            input=json.dumps(event),
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        assert result.returncode == 0

        # After finalizer: pending must be empty
        remaining = peek_pending_outcomes(session_id)
        assert len(remaining) == 0, f"Finalizer left {len(remaining)} pending"


# ===========================================================================
# Shared DB-path resolution: get_db_dir() is the single exported path source
# ===========================================================================


class TestGetDbDirExported:
    """get_db_dir() must be a public export of learning_db_v2, keeping
    ADR-122 chmod hardening.
    """

    def test_get_db_dir_honors_env(self, tmp_path):
        from learning_db_v2 import get_db_dir

        custom = tmp_path / "custom_learning"
        with patch.dict(os.environ, {"CLAUDE_LEARNING_DIR": str(custom)}):
            result = get_db_dir()
            assert result == custom

    def test_get_db_dir_falls_back_to_the_module_default(self, monkeypatch):
        """With CLAUDE_LEARNING_DIR unset, get_db_dir() returns _DEFAULT_DB_DIR."""
        import learning_db_v2

        monkeypatch.delenv("CLAUDE_LEARNING_DIR", raising=False)
        assert learning_db_v2.get_db_dir() == learning_db_v2._DEFAULT_DB_DIR
