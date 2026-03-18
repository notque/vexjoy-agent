#!/usr/bin/env python3
"""
Tests for the auto-plan-detector hook.

Run with: python3 -m pytest hooks/tests/test_auto_plan_detector.py -v
Or directly: python3 hooks/tests/test_auto_plan_detector.py
"""

import json
import subprocess
import sys
from pathlib import Path

HOOK_PATH = Path(__file__).parent.parent / "auto-plan-detector.py"


def run_hook(event: dict) -> tuple[str, str, int]:
    """Run the hook with given event and return (stdout, stderr, exit_code)."""
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
    )
    return result.stdout, result.stderr, result.returncode


def parse_output(stdout: str) -> dict:
    """Parse JSON output from hook."""
    if not stdout.strip():
        return {}
    return json.loads(stdout)


# =============================================================================
# Code Modification Verb Tests
# =============================================================================


def test_triggers_for_implement():
    """Hook should trigger for 'implement' verb."""
    event = {"type": "UserPromptSubmit", "prompt": "implement a new feature"}
    stdout, stderr, code = run_hook(event)

    assert code == 0, f"Hook failed: {stderr}"
    output = parse_output(stdout)
    assert "additionalContext" in output.get("hookSpecificOutput", {})
    assert "<auto-plan-required>" in output["hookSpecificOutput"]["additionalContext"]


def test_triggers_for_build():
    """Hook should trigger for 'build' verb."""
    event = {"type": "UserPromptSubmit", "prompt": "build a user authentication system"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert "<auto-plan-required>" in output.get("hookSpecificOutput", {}).get("additionalContext", "")


def test_triggers_for_fix():
    """Hook should trigger for 'fix' verb."""
    event = {"type": "UserPromptSubmit", "prompt": "fix the login bug"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert "<auto-plan-required>" in output.get("hookSpecificOutput", {}).get("additionalContext", "")


def test_triggers_for_debug():
    """Hook should trigger for 'debug' verb."""
    event = {"type": "UserPromptSubmit", "prompt": "debug the failing tests"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert "<auto-plan-required>" in output.get("hookSpecificOutput", {}).get("additionalContext", "")


def test_triggers_for_refactor():
    """Hook should trigger for 'refactor' verb."""
    event = {"type": "UserPromptSubmit", "prompt": "refactor the database module"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert "<auto-plan-required>" in output.get("hookSpecificOutput", {}).get("additionalContext", "")


def test_triggers_for_create():
    """Hook should trigger for 'create' verb."""
    event = {"type": "UserPromptSubmit", "prompt": "create a new API endpoint"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert "<auto-plan-required>" in output.get("hookSpecificOutput", {}).get("additionalContext", "")


def test_triggers_for_add():
    """Hook should trigger for 'add' verb."""
    event = {"type": "UserPromptSubmit", "prompt": "add validation to the form"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert "<auto-plan-required>" in output.get("hookSpecificOutput", {}).get("additionalContext", "")


def test_triggers_for_update():
    """Hook should trigger for 'update' verb."""
    event = {"type": "UserPromptSubmit", "prompt": "update the user profile page"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert "<auto-plan-required>" in output.get("hookSpecificOutput", {}).get("additionalContext", "")


def test_triggers_for_rename():
    """Hook should trigger for 'rename' verb."""
    event = {"type": "UserPromptSubmit", "prompt": "rename the function to be more descriptive"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert "<auto-plan-required>" in output.get("hookSpecificOutput", {}).get("additionalContext", "")


def test_triggers_for_modify():
    """Hook should trigger for 'modify' verb."""
    event = {"type": "UserPromptSubmit", "prompt": "modify the config settings"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert "<auto-plan-required>" in output.get("hookSpecificOutput", {}).get("additionalContext", "")


def test_triggers_for_change():
    """Hook should trigger for 'change' verb."""
    event = {"type": "UserPromptSubmit", "prompt": "change the API response format"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert "<auto-plan-required>" in output.get("hookSpecificOutput", {}).get("additionalContext", "")


def test_triggers_for_improve():
    """Hook should trigger for 'improve' verb."""
    event = {"type": "UserPromptSubmit", "prompt": "improve the error messages"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert "<auto-plan-required>" in output.get("hookSpecificOutput", {}).get("additionalContext", "")


def test_triggers_for_optimize():
    """Hook should trigger for 'optimize' verb."""
    event = {"type": "UserPromptSubmit", "prompt": "optimize the database queries"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert "<auto-plan-required>" in output.get("hookSpecificOutput", {}).get("additionalContext", "")


def test_triggers_for_migrate():
    """Hook should trigger for 'migrate' verb."""
    event = {"type": "UserPromptSubmit", "prompt": "migrate the data to the new schema"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert "<auto-plan-required>" in output.get("hookSpecificOutput", {}).get("additionalContext", "")


def test_triggers_for_upgrade():
    """Hook should trigger for 'upgrade' verb."""
    event = {"type": "UserPromptSubmit", "prompt": "upgrade the dependencies"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert "<auto-plan-required>" in output.get("hookSpecificOutput", {}).get("additionalContext", "")


def test_triggers_for_rewrite():
    """Hook should trigger for 'rewrite' verb."""
    event = {"type": "UserPromptSubmit", "prompt": "rewrite the parser module"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert "<auto-plan-required>" in output.get("hookSpecificOutput", {}).get("additionalContext", "")


def test_triggers_for_restructure():
    """Hook should trigger for 'restructure' verb."""
    event = {"type": "UserPromptSubmit", "prompt": "restructure the project layout"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert "<auto-plan-required>" in output.get("hookSpecificOutput", {}).get("additionalContext", "")


# =============================================================================
# Research Verb Tests
# =============================================================================


def test_triggers_for_research():
    """Hook should trigger for 'research' verb."""
    event = {"type": "UserPromptSubmit", "prompt": "research the benefits of testing"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert "<auto-plan-required>" in output.get("hookSpecificOutput", {}).get("additionalContext", "")


def test_triggers_for_investigate():
    """Hook should trigger for 'investigate' verb."""
    event = {"type": "UserPromptSubmit", "prompt": "investigate why the API is slow"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert "<auto-plan-required>" in output.get("hookSpecificOutput", {}).get("additionalContext", "")


def test_triggers_for_analyze():
    """Hook should trigger for 'analyze' verb."""
    event = {"type": "UserPromptSubmit", "prompt": "analyze the codebase structure"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert "<auto-plan-required>" in output.get("hookSpecificOutput", {}).get("additionalContext", "")


def test_triggers_for_explore():
    """Hook should trigger for 'explore' verb."""
    event = {"type": "UserPromptSubmit", "prompt": "explore the database schema"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert "<auto-plan-required>" in output.get("hookSpecificOutput", {}).get("additionalContext", "")


def test_triggers_for_understand():
    """Hook should trigger for 'understand' verb."""
    event = {"type": "UserPromptSubmit", "prompt": "understand how the auth system works"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert "<auto-plan-required>" in output.get("hookSpecificOutput", {}).get("additionalContext", "")


def test_triggers_for_study():
    """Hook should trigger for 'study' verb."""
    event = {"type": "UserPromptSubmit", "prompt": "study the performance patterns"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert "<auto-plan-required>" in output.get("hookSpecificOutput", {}).get("additionalContext", "")


def test_triggers_for_examine():
    """Hook should trigger for 'examine' verb."""
    event = {"type": "UserPromptSubmit", "prompt": "examine the error logs closely"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert "<auto-plan-required>" in output.get("hookSpecificOutput", {}).get("additionalContext", "")


def test_triggers_for_review():
    """Hook should trigger for 'review' verb (research context)."""
    event = {"type": "UserPromptSubmit", "prompt": "review the authentication flow"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert "<auto-plan-required>" in output.get("hookSpecificOutput", {}).get("additionalContext", "")


# =============================================================================
# Multi-Step Indicator Tests
# =============================================================================


def test_triggers_for_first_then():
    """Hook should trigger for 'first...then' pattern."""
    event = {
        "type": "UserPromptSubmit",
        "prompt": "first set up the database, then add the API endpoints",
    }
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert "<auto-plan-required>" in output.get("hookSpecificOutput", {}).get("additionalContext", "")


def test_triggers_for_numbered_list():
    """Hook should trigger for numbered list pattern."""
    event = {"type": "UserPromptSubmit", "prompt": "1. add tests 2. fix bugs 3. deploy"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert "<auto-plan-required>" in output.get("hookSpecificOutput", {}).get("additionalContext", "")


def test_triggers_for_and_also():
    """Hook should trigger for 'and also' pattern."""
    event = {
        "type": "UserPromptSubmit",
        "prompt": "update the config and also add documentation",
    }
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert "<auto-plan-required>" in output.get("hookSpecificOutput", {}).get("additionalContext", "")


def test_triggers_for_step_1():
    """Hook should trigger for 'step 1' pattern."""
    event = {"type": "UserPromptSubmit", "prompt": "step 1 set up the database step 2 add the API"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert "<auto-plan-required>" in output.get("hookSpecificOutput", {}).get("additionalContext", "")


def test_triggers_for_after_that():
    """Hook should trigger for 'after that' pattern."""
    event = {"type": "UserPromptSubmit", "prompt": "create the model, after that add validation"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert "<auto-plan-required>" in output.get("hookSpecificOutput", {}).get("additionalContext", "")


def test_triggers_for_next_comma():
    """Hook should trigger for 'next,' pattern."""
    event = {"type": "UserPromptSubmit", "prompt": "set up the tests, next, run them all"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert "<auto-plan-required>" in output.get("hookSpecificOutput", {}).get("additionalContext", "")


# =============================================================================
# Agent Trigger + Modification Intent Tests
# =============================================================================


def test_triggers_for_python_with_modification():
    """Hook should trigger for Python + modification intent."""
    event = {"type": "UserPromptSubmit", "prompt": "add a new Python function"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert "<auto-plan-required>" in output.get("hookSpecificOutput", {}).get("additionalContext", "")


def test_triggers_for_kubernetes_with_research():
    """Hook should trigger for Kubernetes + research intent."""
    event = {"type": "UserPromptSubmit", "prompt": "research kubernetes deployment options"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert "<auto-plan-required>" in output.get("hookSpecificOutput", {}).get("additionalContext", "")


# =============================================================================
# Trivial Task Tests (should NOT trigger)
# =============================================================================


def test_silent_for_what_is():
    """Hook should be silent for 'what is' questions."""
    event = {"type": "UserPromptSubmit", "prompt": "what is the syntax for python decorators"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    # Should have empty output or no additionalContext
    assert output.get("hookSpecificOutput", {}).get("additionalContext") is None


def test_silent_for_how_do_i():
    """Hook should be silent for 'how do I' questions."""
    event = {"type": "UserPromptSubmit", "prompt": "how do i use git rebase"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert output.get("hookSpecificOutput", {}).get("additionalContext") is None


def test_silent_for_git_status():
    """Hook should be silent for 'git status' command."""
    event = {"type": "UserPromptSubmit", "prompt": "git status"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert output.get("hookSpecificOutput", {}).get("additionalContext") is None


def test_silent_for_read_file():
    """Hook should be silent for 'read' commands."""
    event = {"type": "UserPromptSubmit", "prompt": "read the config file"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert output.get("hookSpecificOutput", {}).get("additionalContext") is None


def test_silent_for_explain():
    """Hook should be silent for 'explain' requests."""
    event = {"type": "UserPromptSubmit", "prompt": "explain how async works in python"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert output.get("hookSpecificOutput", {}).get("additionalContext") is None


def test_silent_for_show_me_simple():
    """Hook should be silent for simple 'show me the/this/that' requests."""
    event = {"type": "UserPromptSubmit", "prompt": "show me the error logs"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert output.get("hookSpecificOutput", {}).get("additionalContext") is None


def test_triggers_for_show_me_how_to_build():
    """Hook should trigger for 'show me how to build' (complex task, not trivial)."""
    event = {"type": "UserPromptSubmit", "prompt": "show me how to build authentication"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    # "build" is a code modification verb, so this should trigger
    assert "<auto-plan-required>" in output.get("hookSpecificOutput", {}).get("additionalContext", "")


# =============================================================================
# Edge Cases
# =============================================================================


def test_handles_empty_prompt():
    """Hook should handle empty prompt gracefully."""
    event = {"type": "UserPromptSubmit", "prompt": ""}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert output.get("hookSpecificOutput", {}).get("additionalContext") is None


def test_handles_missing_prompt():
    """Hook should handle missing prompt field gracefully."""
    event = {"type": "UserPromptSubmit"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert output.get("hookSpecificOutput", {}).get("additionalContext") is None


def test_handles_invalid_json():
    """Hook should handle invalid JSON input gracefully."""
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input="not valid json",
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, "Hook should not fail on invalid JSON"


def test_case_insensitive_detection():
    """Hook should detect verbs case-insensitively."""
    event = {"type": "UserPromptSubmit", "prompt": "IMPLEMENT A NEW FEATURE"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    assert "<auto-plan-required>" in output.get("hookSpecificOutput", {}).get("additionalContext", "")


def test_output_contains_plan_template():
    """Hook output should contain the plan template."""
    event = {"type": "UserPromptSubmit", "prompt": "implement user authentication"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    context = output.get("hookSpecificOutput", {}).get("additionalContext", "")
    assert "task_plan.md" in context
    assert "## Goal" in context
    assert "## Phases" in context
    assert "## Errors Encountered" in context


def test_silent_for_agent_trigger_only():
    """Hook should be silent for agent trigger without modification intent."""
    # Mentions 'python' but no modification/research verb - should be trivial
    event = {"type": "UserPromptSubmit", "prompt": "what syntax does python use for type hints"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    # Should NOT trigger - agent trigger alone is not enough
    assert output.get("hookSpecificOutput", {}).get("additionalContext") is None


def test_no_partial_word_matching():
    """Verbs embedded in other words should not trigger."""
    # 'unimplemented' contains 'implement' but should not match
    event = {"type": "UserPromptSubmit", "prompt": "the function is unimplemented"}
    stdout, stderr, code = run_hook(event)

    assert code == 0
    output = parse_output(stdout)
    # Should NOT trigger - word is 'unimplemented', not 'implement'
    assert output.get("hookSpecificOutput", {}).get("additionalContext") is None


def test_debug_mode_outputs_reason():
    """Debug mode should output trigger reason to stderr."""
    import os

    event = {"type": "UserPromptSubmit", "prompt": "implement a feature"}
    env = os.environ.copy()
    env["CLAUDE_HOOKS_DEBUG"] = "1"

    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0
    assert "[auto-plan]" in result.stderr
    assert "code modification" in result.stderr.lower()


def test_handles_non_dict_json():
    """Hook should handle non-dict JSON input gracefully."""
    # Valid JSON but not a dict - should log and return empty
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input='["this", "is", "a", "list"]',
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    # Should log the type error
    assert "Expected dict input" in result.stderr or result.stderr == ""


def test_json_parse_error_logs():
    """JSON parse errors should be logged to stderr."""
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input="not valid json at all {{{",
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    # Should log the parse error
    assert "JSON parse error" in result.stderr


# =============================================================================
# Run tests directly
# =============================================================================

if __name__ == "__main__":
    try:
        import pytest

        sys.exit(pytest.main([__file__, "-v"]))
    except ImportError:
        # Fallback: run tests manually without pytest
        print("Running tests without pytest...")
        import traceback

        # Get all test functions from module globals
        test_functions = {name: func for name, func in globals().items() if name.startswith("test_") and callable(func)}
        passed = 0
        failed = 0

        for name, func in sorted(test_functions.items()):
            try:
                func()
                print(f"  ✓ {name}")
                passed += 1
            except AssertionError as e:
                print(f"  ✗ {name}: {e}")
                failed += 1
            except Exception as e:
                print(f"  ✗ {name}: {e}")
                traceback.print_exc()
                failed += 1

        print(f"\n{passed} passed, {failed} failed")
        sys.exit(0 if failed == 0 else 1)
