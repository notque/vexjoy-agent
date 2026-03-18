#!/usr/bin/env python3
"""
Tests for the skill-evaluator hook.

Run with: python3 -m pytest hooks/tests/test_skill_evaluator.py -v
Or directly: python3 hooks/tests/test_skill_evaluator.py
"""

import json
import subprocess
import sys
from pathlib import Path

HOOK_PATH = Path(__file__).parent.parent / "skill-evaluator.py"


def run_hook(event: dict) -> tuple[str, str, int]:
    """Run the hook with given event and return (stdout, stderr, exit_code)."""
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
    )
    return result.stdout, result.stderr, result.returncode


def test_injects_protocol_for_substantive_prompt():
    """Hook should inject evaluation protocol for long, substantive prompts."""
    event = {
        "type": "UserPromptSubmit",
        "prompt": "implement a new feature with comprehensive testing and documentation",
    }
    stdout, stderr, code = run_hook(event)

    assert code == 0, f"Hook failed: {stderr}"
    assert "<skill-evaluation-protocol>" in stdout
    assert "EVALUATE" in stdout
    assert "Route with:" in stdout or "EXECUTE" in stdout


def test_skips_short_prompts():
    """Hook should skip prompts shorter than 20 characters."""
    event = {
        "type": "UserPromptSubmit",
        "prompt": "hello world",
    }
    stdout, stderr, code = run_hook(event)

    assert code == 0
    assert stdout == "", "Should not inject anything for short prompts"


def test_skips_simple_greetings():
    """Hook should skip simple greetings like 'hello' or 'hi'."""
    for greeting in [
        "hello there friend",
        "hi how are you doing today",
        "thanks for your help",
    ]:
        event = {
            "type": "UserPromptSubmit",
            "prompt": greeting,
        }
        stdout, stderr, code = run_hook(event)

        assert code == 0
        assert stdout == "", f"Should skip greeting: {greeting}"


def test_skips_non_user_prompt_events():
    """Hook should skip events that aren't UserPromptSubmit."""
    event = {
        "type": "ToolResult",
        "prompt": "this is a long prompt that would normally trigger injection",
    }
    stdout, stderr, code = run_hook(event)

    assert code == 0
    assert stdout == "", "Should skip non-UserPromptSubmit events"


def test_handles_missing_type_gracefully():
    """Hook should handle events without a type field."""
    event = {
        "prompt": "implement something with a very long prompt here",
    }
    stdout, stderr, code = run_hook(event)

    assert code == 0
    assert stdout == "", "Should skip events without type"


def test_handles_invalid_json():
    """Hook should handle invalid JSON gracefully."""
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input="not valid json {{{",
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, "Should not crash on invalid JSON"


def test_discovers_skills_dynamically():
    """Hook should discover skills from filesystem and include them in output."""
    event = {
        "type": "UserPromptSubmit",
        "prompt": "implement a complex feature with multiple components and testing",
    }
    stdout, stderr, code = run_hook(event)

    assert code == 0, f"Hook failed: {stderr}"
    # Should include dynamically discovered skills (first 10 alphabetically)
    assert "agent-evaluation" in stdout
    assert "code-linting" in stdout
    assert "codebase-analyzer" in stdout


def test_discovers_agents_dynamically():
    """Hook should discover agents from filesystem and include them in output."""
    event = {
        "type": "UserPromptSubmit",
        "prompt": "implement a complex feature with multiple components and testing",
    }
    stdout, stderr, code = run_hook(event)

    assert code == 0, f"Hook failed: {stderr}"
    # Should include priority agents
    assert "golang-general-engineer" in stdout
    assert "database-engineer" in stdout


if __name__ == "__main__":
    # Simple test runner
    tests = [
        test_injects_protocol_for_substantive_prompt,
        test_skips_short_prompts,
        test_skips_simple_greetings,
        test_skips_non_user_prompt_events,
        test_handles_missing_type_gracefully,
        test_handles_invalid_json,
        test_discovers_skills_dynamically,
        test_discovers_agents_dynamically,
    ]

    print("Running hook tests...\n")
    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            print(f"  ✓ {test.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ {test.__name__}: Exception - {e}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
