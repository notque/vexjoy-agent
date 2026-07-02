#!/usr/bin/env python3
"""Tests for scripts/build-dispatch.py (ADR: router-improvement-program, C4).

Covers:
- Marker round-trip against the REAL recorder parser
  (hooks/routing-decision-recorder.py) on 7 marker variants: agent/skill,
  complexity, health gate inputs (numeric and `health=-`), alts, stack.
- Preamble completeness and block order: marker first, then thinking
  directive, token line, Task Specification, the 4 mandatory injections,
  optional worktree/local-only blocks.
- Thinking directive by complexity + slow/fast overrides.
- Graceful degradation: missing optional fields omit their block only.
- Token budget: explicit value, settings.json read, 500000 default.
- CLI: --json / --json-file / stdin; exit 2 + empty stdout on bad input.

Run with: python3 -m pytest scripts/tests/test_build_dispatch.py -v
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "build-dispatch.py"
RECORDER_PATH = REPO_ROOT / "hooks" / "routing-decision-recorder.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    with patch("sys.exit"):
        spec.loader.exec_module(mod)
    return mod


bd = _load(SCRIPT_PATH, "build_dispatch")
recorder = _load(RECORDER_PATH, "routing_decision_recorder")


def _decision(**overrides):
    """A complete, valid routing decision; overrides replace top-level keys."""
    base = {
        "agent": "python-general-engineer",
        "skill": "test-driven-development",
        "complexity": "medium",
        "health": {"confidence": 0.72, "n": 6, "failure": 0, "action": "keep"},
        "stack": ["verification-before-completion"],
        "task_spec": {
            "intent": "Fix the flaky retry test.",
            "constraints": "Branch from main; no force-push.",
            "acceptance": "pytest green; CI green.",
            "files": "scripts/retry.py, scripts/tests/test_retry.py",
            "operator_context": "personal profile, full autonomy",
        },
        "flags": {"worktree": False, "local_only": False, "thinking_override": None},
        "token_remaining": 480000,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Marker round-trip: build with the script, parse with the REAL recorder.
# Each case: (decision overrides, expected recorder reads).
# ---------------------------------------------------------------------------

ROUND_TRIP_CASES = [
    pytest.param(  # V1: everything — numeric health, all gate inputs, alts, stack
        {
            "agent": "golang-general-engineer",
            "skill": "go-patterns",
            "complexity": "complex",
            "health": {
                "confidence": 0.72,
                "n": 6,
                "failure": 1,
                "action": "keep",
                "alts": ["claude:quick", "python-general-engineer:tdd"],
            },
            "stack": ["test-driven-development", "verification-before-completion"],
        },
        {
            "agent": "golang-general-engineer",
            "skill": "go-patterns",
            "complexity": "complex",
            "health": 0.72,
            "n": 6,
            "failure": 1,
            "action": "keep",
            "alternates": ["claude:quick", "python-general-engineer:tdd"],
            "gate_inputs_present": True,
            "stack": ["test-driven-development", "verification-before-completion"],
        },
        id="full-gate-inputs-alts-stack",
    ),
    pytest.param(  # V2: no weight row (health=-) with a stack
        {"health": {}, "stack": ["worktree-agent"]},
        {
            "agent": "python-general-engineer",
            "skill": "test-driven-development",
            "complexity": "medium",
            "health": None,
            "n": None,
            "failure": None,
            "action": None,
            "alternates": None,
            "gate_inputs_present": True,
            "stack": ["worktree-agent"],
        },
        id="health-dash-with-stack",
    ),
    pytest.param(  # V3: agent-only routing => skill=-, recorder reads ""
        {"skill": "", "health": None, "stack": []},
        {
            "agent": "python-general-engineer",
            "skill": "",
            "complexity": "medium",
            "health": None,
            "gate_inputs_present": True,
            "stack": None,
        },
        id="agent-only-skill-dash",
    ),
    pytest.param(  # V4: numeric health alone — no n/fail/action/alts tokens
        {"health": {"confidence": 0.5}, "stack": []},
        {
            "agent": "python-general-engineer",
            "skill": "test-driven-development",
            "complexity": "medium",
            "health": 0.5,
            "n": None,
            "failure": None,
            "action": None,
            "alternates": None,
            "gate_inputs_present": True,
            "stack": None,
        },
        id="numeric-health-alone",
    ),
    pytest.param(  # V5: simple complexity, health key absent entirely
        {"complexity": "simple", "health": None, "stack": []},
        {
            "agent": "python-general-engineer",
            "skill": "test-driven-development",
            "complexity": "simple",
            "health": None,
            "gate_inputs_present": True,
            "stack": None,
        },
        id="simple-no-health-key",
    ),
    pytest.param(  # V6: confidence 1.0 formats as integer '1'; tiebreak action
        {"health": {"confidence": 1.0, "n": 12, "failure": 0, "action": "tiebreak"}, "stack": []},
        {
            "agent": "python-general-engineer",
            "skill": "test-driven-development",
            "complexity": "medium",
            "health": 1.0,
            "n": 12,
            "failure": 0,
            "action": "tiebreak",
            "gate_inputs_present": True,
            "stack": None,
        },
        id="confidence-one-tiebreak",
    ),
    pytest.param(  # V7: trivial complexity, uppercase input normalized
        {"complexity": "Trivial", "agent": "CLAUDE", "skill": "quick", "health": None, "stack": []},
        {
            "agent": "claude",
            "skill": "quick",
            "complexity": "trivial",
            "health": None,
            "gate_inputs_present": True,
            "stack": None,
        },
        id="case-normalized-trivial",
    ),
]


@pytest.mark.parametrize(("overrides", "expected"), ROUND_TRIP_CASES)
def test_marker_round_trip_with_real_recorder(overrides, expected):
    """Every emitted marker parses with the shipped recorder, field for field."""
    preamble = bd.build_preamble(_decision(**overrides))

    routed = recorder.parse_do_route_marker(preamble)
    assert routed == (expected["agent"], expected["skill"])

    complexity, invalid = recorder.parse_marker_complexity(preamble)
    assert (complexity, invalid) == (expected["complexity"], "")

    assert recorder.parse_stack(preamble) == expected["stack"]

    health = recorder.parse_health_inputs(preamble)
    assert health["health"] == expected["health"]
    assert health["gate_inputs_present"] == expected["gate_inputs_present"]
    for key in ("n", "failure", "action", "alternates"):
        assert health[key] == expected.get(key), key


def test_marker_is_first_line_at_line_start():
    """The recorder anchors ^\\s*\\[do-route\\]; the marker must open line 1."""
    preamble = bd.build_preamble(_decision())
    assert preamble.splitlines()[0].startswith("[do-route] agent=")


# ---------------------------------------------------------------------------
# Preamble completeness and order.
# ---------------------------------------------------------------------------


def test_preamble_contains_every_mandatory_block_in_order():
    preamble = bd.build_preamble(_decision(complexity="complex"))
    ordered = [
        "[do-route] agent=python-general-engineer skill=test-driven-development complexity=complex",
        bd.THINKING_SLOW,
        "~480000 tokens available for this task; prioritize accordingly.",
        "## Task Specification (auto-extracted)",
        "**Intent:** Fix the flaky retry test.",
        "**Constraints:** Branch from main; no force-push.",
        "**Acceptance criteria:** pytest green; CI green.",
        "**Relevant file locations:** scripts/retry.py, scripts/tests/test_retry.py",
        "**Operator context:** personal profile, full autonomy",
        bd.INJ_REFERENCE_LOADING,
        bd.INJ_COMPLETENESS,
        bd.INJ_DENSE_COMPLETE,
        bd.INJ_BASE_INSTRUCTIONS,
    ]
    pos = -1
    for piece in ordered:
        found = preamble.find(piece)
        assert found > pos, f"missing or out of order: {piece[:60]!r}"
        pos = found


def test_worktree_and_local_only_blocks_follow_flags():
    both = bd.build_preamble(_decision(flags={"worktree": True, "local_only": True}))
    assert bd.WORKTREE_RULES in both
    assert bd.LOCAL_ONLY_BLOCK in both
    neither = bd.build_preamble(_decision())
    assert bd.WORKTREE_RULES not in neither
    assert bd.LOCAL_ONLY_BLOCK not in neither


@pytest.mark.parametrize(
    ("complexity", "override", "expected"),
    [
        ("simple", None, "THINKING_FAST"),
        ("medium", None, ""),
        ("trivial", None, ""),
        ("complex", None, "THINKING_SLOW"),
        ("simple", "slow", "THINKING_SLOW"),  # category override beats complexity
        ("complex", "fast", "THINKING_FAST"),
    ],
)
def test_thinking_directive_by_complexity_and_override(complexity, override, expected):
    decision = _decision(complexity=complexity, flags={"thinking_override": override})
    directive = bd.build_thinking(decision)
    assert directive == (getattr(bd, expected) if expected else "")
    if expected:
        assert getattr(bd, expected) in bd.build_preamble(decision)
    else:
        assert bd.THINKING_FAST not in bd.build_preamble(decision)
        assert bd.THINKING_SLOW not in bd.build_preamble(decision)


# ---------------------------------------------------------------------------
# Graceful degradation and token budget.
# ---------------------------------------------------------------------------


def test_missing_optional_fields_omit_their_blocks_only():
    minimal = {"agent": "claude", "complexity": "medium"}
    preamble = bd.build_preamble(minimal)
    assert preamble.startswith("[do-route] agent=claude skill=- complexity=medium health=-\n")
    assert "## Task Specification" not in preamble
    assert "stack={" not in preamble
    # Mandatory blocks survive the minimal input.
    for injection in (bd.INJ_REFERENCE_LOADING, bd.INJ_COMPLETENESS, bd.INJ_DENSE_COMPLETE, bd.INJ_BASE_INSTRUCTIONS):
        assert injection in preamble
    assert "tokens available for this task" in preamble


def test_partial_task_spec_emits_only_given_fields():
    preamble = bd.build_preamble(_decision(task_spec={"intent": "Do the thing."}))
    assert "**Intent:** Do the thing." in preamble
    assert "**Constraints:**" not in preamble
    assert "**Acceptance criteria:**" not in preamble


def test_token_budget_reads_settings_and_defaults(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"orchestration": {"token_budget": 250000}}))
    decision = _decision(token_remaining=None)
    line = bd.build_token_line(decision, settings_path=settings)
    assert line == "~250000 tokens available for this task; prioritize accordingly."
    # Missing file => documented default 500000.
    line = bd.build_token_line(decision, settings_path=tmp_path / "absent.json")
    assert line == "~500000 tokens available for this task; prioritize accordingly."


def test_determinism_same_input_same_bytes():
    decision = _decision()
    assert bd.build_preamble(decision) == bd.build_preamble(decision)


# ---------------------------------------------------------------------------
# Validation errors.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"agent": ""},
        {"agent": "Bad Agent!"},
        {"complexity": "low"},  # the audit's real-world invalid value
        {"complexity": ""},
        {"health": {"confidence": 1.5}},
        {"health": {"confidence": -0.1}},
        {"health": {"confidence": 0.5, "action": "boost"}},
        {"health": {"confidence": 0.5, "n": -1}},
        {"stack": ["has space"]},
        {"flags": {"thinking_override": "deep"}},
        {"token_remaining": -5},
    ],
)
def test_invalid_input_raises(overrides):
    with pytest.raises(bd.InputError):
        bd.build_preamble(_decision(**overrides))


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------


def _run_cli(*args, stdin_text=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        input=stdin_text,
        capture_output=True,
        text=True,
    )


def test_cli_json_flag_emits_preamble():
    result = _run_cli("--json", json.dumps(_decision()))
    assert result.returncode == 0
    assert result.stdout == bd.build_preamble(_decision())


def test_cli_json_file_and_stdin(tmp_path):
    decision = _decision()
    path = tmp_path / "route.json"
    path.write_text(json.dumps(decision))
    from_file = _run_cli("--json-file", str(path))
    from_stdin = _run_cli("--json-file", "-", stdin_text=json.dumps(decision))
    assert from_file.returncode == from_stdin.returncode == 0
    assert from_file.stdout == from_stdin.stdout == bd.build_preamble(decision)


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        json.dumps({"complexity": "medium"}),  # agent missing
        json.dumps({"agent": "claude", "complexity": "Low"}),  # invalid enum
    ],
)
def test_cli_bad_input_exits_2_with_empty_stdout(payload):
    result = _run_cli("--json", payload)
    assert result.returncode == 2
    assert result.stdout == ""
    assert "build-dispatch:" in result.stderr
