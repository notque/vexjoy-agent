#!/usr/bin/env python3
"""Tests for scripts/detect-workflow-capability.py — harness identity from env.

Covers the env-matrix harness classifier (claude-code / codex / gemini /
factory / reasonix / unknown), the workflow_capable proxy (true only for
claude-code), the never-raises / exit-0 contract, and the JSON output shape.
The env signal is a PROXY: the orchestrator LLM adds the authoritative
tool-list gate.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "detect-workflow-capability.py"

# Import the module directly for unit-level tests of the pure classifier.
sys.path.insert(0, str(SCRIPT.parent))
import importlib.util

_spec = importlib.util.spec_from_file_location("detect_workflow_capability", SCRIPT)
dwc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dwc)


# --- Pure classifier: harness identity from an env dict ----------------------


@pytest.mark.parametrize(
    "env,expected",
    [
        # claude-code: any of the distinctive markers
        ({"CLAUDECODE": "1"}, "claude-code"),
        ({"CLAUDE_CODE_ENTRYPOINT": "cli"}, "claude-code"),
        ({"CLAUDE_CODE_SESSION_ID": "abc123"}, "claude-code"),
        # codex: home / hooks dir markers
        ({"CODEX_HOME": "/home/u/.codex"}, "codex"),
        ({"CODEX_HOOKS_DIR": "/x"}, "codex"),
        # gemini: explicit CLI identifier
        ({"GEMINI_CLI": "1"}, "gemini"),
        # factory / droid
        ({"FACTORY_SESSION_ID": "f1"}, "factory"),
        ({"DROID_SESSION_ID": "d1"}, "factory"),
        # reasonix: no env marker — keyed off the _ invocation var (basename match)
        ({"_": "/usr/local/bin/reasonix"}, "reasonix"),
        ({"_": "/opt/node/bin/Reasonix"}, "reasonix"),
        ({"_": "/usr/local/bin/reasonix-dev"}, "reasonix"),
        # basename guard: "reasonix" in the parent path must NOT match
        ({"_": "/Users/reasonix-fan/bin/python3"}, "unknown"),
        ({"_": "/opt/reasonix-corp/python"}, "unknown"),
        # nothing distinctive
        ({}, "unknown"),
    ],
)
def test_detect_harness(env, expected):
    assert dwc.detect_harness(env) == expected


def test_generic_api_keys_do_not_classify():
    """A bare GEMINI_API_KEY/GOOGLE_API_KEY must NOT be read as the gemini
    harness — those vars are commonly set even under Claude Code."""
    assert dwc.detect_harness({"GEMINI_API_KEY": "x"}) == "unknown"
    assert dwc.detect_harness({"GOOGLE_API_KEY": "x"}) == "unknown"


def test_claude_code_wins_over_other_markers():
    """If both Claude Code and another marker are present, Claude Code wins:
    the toolkit ships from Claude Code and copies env-laden config around."""
    env = {"CLAUDECODE": "1", "CODEX_HOME": "/x", "GEMINI_CLI": "1"}
    assert dwc.detect_harness(env) == "claude-code"


# --- workflow_capable proxy --------------------------------------------------


@pytest.mark.parametrize(
    "harness,expected",
    [
        ("claude-code", True),
        ("codex", False),
        ("gemini", False),
        ("factory", False),
        ("reasonix", False),
        ("unknown", False),
    ],
)
def test_workflow_capable(harness, expected):
    assert dwc.workflow_capable(harness) is expected


def test_workflow_capable_set_is_single_source_of_truth():
    """Adding a harness to WORKFLOW_CAPABLE is the one-line migration when a
    harness ships native Workflow upstream. Pin the set so future changes are
    deliberate.
    """
    expected = frozenset({"claude-code"})
    assert dwc.WORKFLOW_CAPABLE == expected  # noqa: SIM300 — left side is the unit-under-test
    # Every member of WORKFLOW_CAPABLE must classify as workflow_capable=True.
    for h in dwc.WORKFLOW_CAPABLE:
        assert dwc.workflow_capable(h) is True
    # Every harness NOT in the set must classify as False.
    for h in dwc.HARNESSES:
        if h not in dwc.WORKFLOW_CAPABLE:
            assert dwc.workflow_capable(h) is False


# --- never raises ------------------------------------------------------------


def test_classify_never_raises_on_garbage():
    # Non-string values must not crash the classifier.
    assert dwc.detect_harness({"CLAUDECODE": None}) in dwc.HARNESSES
    assert dwc.detect_harness(None) == "unknown"


# --- CLI / JSON contract -----------------------------------------------------


def _run(env):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        env=env,
    )
    return proc


def test_cli_exit_zero_and_json_shape():
    proc = _run({"CLAUDECODE": "1", "PATH": "/usr/bin"})
    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    assert out == {"harness": "claude-code", "workflow_capable": True}


def test_cli_unknown_harness():
    # Empty-ish env (PATH only) → unknown, not capable.
    proc = _run({"PATH": "/usr/bin"})
    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    assert out["harness"] == "unknown"
    assert out["workflow_capable"] is False
