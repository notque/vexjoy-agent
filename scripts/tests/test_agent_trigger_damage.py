#!/usr/bin/env python3
"""Tests for check_agent_trigger_damage in scripts/validate-index-integrity.py.

Contract: agent triggers must not be run-on rename damage (``programmingui``)
and no single-word trigger may be shared by 3+ agents.

Run with: python3 -m pytest scripts/tests/test_agent_trigger_damage.py -v
"""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "validate-index-integrity.py"

_spec = importlib.util.spec_from_file_location("validate_index_integrity", SCRIPT)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

check_agent_trigger_damage = _mod.check_agent_trigger_damage


def _index(**agents: list[str]) -> dict:
    return {"agents": {name: {"triggers": trig} for name, trig in agents.items()}}


def test_clean_triggers_pass() -> None:
    errors, _ = check_agent_trigger_damage(_index(a=["swift", "swiftui"], b=["php", "phpunit"]))
    assert errors == []


def test_runon_programming_trigger_is_an_error() -> None:
    for bad in ("programmingui", "programminglint", "programming-cs-fixer"):
        errors, _ = check_agent_trigger_damage(_index(a=[bad]))
        assert len(errors) == 1 and "rename damage" in errors[0]


def test_plain_programming_trigger_is_allowed() -> None:
    errors, _ = check_agent_trigger_damage(_index(a=["programming", "programming flow"]))
    assert errors == []


def test_single_word_shared_by_three_agents_is_an_error() -> None:
    errors, _ = check_agent_trigger_damage(_index(a=["review"], b=["Review"], c=["review"]))
    assert len(errors) == 1 and "shared trigger" in errors[0]


def test_single_word_shared_by_two_agents_passes() -> None:
    errors, _ = check_agent_trigger_damage(_index(a=["review"], b=["review"]))
    assert errors == []
