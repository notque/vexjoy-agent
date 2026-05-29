#!/usr/bin/env python3
"""Tests for scripts/validate-workflow-conformance.py — the conformance gate.

A native .js workflow declares a pure-literal ``meta.contract`` (phases, the
static Wave-1 roster of ``{agentType, skill}``, ``agents:{static,dynamic}``, and a
top-level ``dynamic`` flag for data-driven passes). The validator asserts the
actual script against that contract:

- STATIC: ``meta.phases`` titles == ``contract.phases``; the static roster's
  agentType+skill pairs are present in source ``agentType:``/``Skill("..")``
  tokens; the declared static agent count matches the roster.
- DYNAMIC (only when node is available): shells to conformance-harness.mjs and
  asserts the recorded trace (phases entered subset of contract.phases; static
  Wave-1 roster agentType+skills) against the contract. For ``dynamic:true``
  rosters it asserts SHAPE + SKILLS, not COUNT (honest limits).

Files WITHOUT a ``meta.contract`` are EXEMPT (skipped), not failed.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "validate-workflow-conformance.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "conformance"
REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_WORKFLOW_DIR = REPO_ROOT / "skills" / "workflow" / "references"

# Import the module for unit-level tests of the static checker.
sys.path.insert(0, str(SCRIPT.parent))
import importlib.util

_spec = importlib.util.spec_from_file_location("validate_workflow_conformance", SCRIPT)
vwc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vwc)

NODE = shutil.which("node")


def _run_json(*paths_or_flags):
    """Run the validator CLI with --json over given dir/flags; return (rc, data)."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--json", *paths_or_flags],
        capture_output=True,
        text=True,
    )
    data = json.loads(proc.stdout) if proc.stdout.strip() else {}
    return proc.returncode, data


def _result_for(data, name_substr):
    """Find the per-file result whose path contains name_substr."""
    for r in data["files"]:
        if name_substr in r["file"]:
            return r
    raise AssertionError(f"no result for {name_substr} in {[r['file'] for r in data['files']]}")


# --- STATIC: pure parser unit tests ------------------------------------------


def test_extract_contract_present():
    src = (FIXTURES / "matching.js").read_text()
    contract = vwc.extract_contract(src)
    assert contract is not None
    assert contract["phases"] == ["wave-1", "verify"]
    assert contract["agents"]["static"] == 2


def test_extract_contract_absent_is_none():
    src = (FIXTURES / "no-contract.js").read_text()
    assert vwc.extract_contract(src) is None


def test_extract_phase_titles_from_source():
    src = (FIXTURES / "matching.js").read_text()
    assert vwc.extract_phase_titles(src) == {"wave-1", "verify"}


def test_extract_skill_tokens_from_source():
    src = (FIXTURES / "matching.js").read_text()
    skills = vwc.extract_skill_tokens(src)
    assert "systematic-code-review" in skills
    assert "roast" in skills


def test_count_agent_callsites():
    src = (FIXTURES / "matching.js").read_text()
    # matching.js dispatches agent() twice (wave-1 map + verify).
    assert vwc.count_agent_callsites(src) == 2


# --- STATIC: pass / fail matrix via the CLI ----------------------------------


def test_matching_fixture_passes():
    rc, data = _run_json("--dir", str(FIXTURES), "--static-only")
    res = _result_for(data, "matching.js")
    assert res["status"] == "pass", res
    # matching.js itself passes; rc reflects whole-dir (which includes mismatches).


def test_mismatch_phase_fails():
    rc, data = _run_json("--dir", str(FIXTURES), "--static-only")
    res = _result_for(data, "mismatch-phase.js")
    assert res["status"] == "fail"
    assert any("phase" in e.lower() for e in res["static_errors"]), res["static_errors"]
    assert rc != 0


def test_mismatch_skill_fails():
    rc, data = _run_json("--dir", str(FIXTURES), "--static-only")
    res = _result_for(data, "mismatch-skill.js")
    assert res["status"] == "fail"
    assert any("skill" in e.lower() for e in res["static_errors"]), res["static_errors"]


def test_mismatch_agentcount_fails():
    rc, data = _run_json("--dir", str(FIXTURES), "--static-only")
    res = _result_for(data, "mismatch-agentcount.js")
    assert res["status"] == "fail"
    assert any("count" in e.lower() or "roster" in e.lower() or "static" in e.lower() for e in res["static_errors"]), (
        res["static_errors"]
    )


def test_no_contract_is_exempt():
    rc, data = _run_json("--dir", str(FIXTURES), "--static-only")
    res = _result_for(data, "no-contract.js")
    assert res["status"] == "exempt"


def test_dir_with_any_failure_exits_nonzero():
    rc, _ = _run_json("--dir", str(FIXTURES), "--static-only")
    assert rc != 0  # fixtures dir contains deliberate mismatches


# --- The real hardened workflow MUST conform (static) ------------------------


def test_real_comprehensive_review_workflow_passes_static():
    rc, data = _run_json("--dir", str(REAL_WORKFLOW_DIR), "--static-only")
    res = _result_for(data, "comprehensive-review-workflow.js")
    assert res["status"] == "pass", res
    assert rc == 0, data


# --- DYNAMIC: only when node is available ------------------------------------


@pytest.mark.skipif(NODE is None, reason="node not available; dynamic harness is a local/dev tool")
def test_matching_fixture_passes_dynamic():
    rc, data = _run_json("--dir", str(FIXTURES))
    res = _result_for(data, "matching.js")
    assert res["status"] == "pass", res
    assert res.get("dynamic_ran") is True


@pytest.mark.skipif(NODE is None, reason="node not available; dynamic harness is a local/dev tool")
def test_real_workflow_dynamic_trace_matches_contract():
    rc, data = _run_json("--dir", str(REAL_WORKFLOW_DIR))
    res = _result_for(data, "comprehensive-review-workflow.js")
    assert res["status"] == "pass", res
    assert res.get("dynamic_ran") is True
    assert not res["dynamic_errors"], res["dynamic_errors"]


def test_node_absent_skips_dynamic_gracefully(monkeypatch):
    """When node is unavailable the dynamic pass is skipped, not failed."""
    # Force the 'node missing' path regardless of host.
    monkeypatch.setattr(vwc, "node_available", lambda: False)
    results = vwc.validate_dir(FIXTURES / "matching.js", static_only=False)
    res = results[0]
    assert res["status"] == "pass"
    assert res["dynamic_ran"] is False
    assert any("node" in n.lower() for n in res["notes"]), res["notes"]


# --- Honest-limits surface ---------------------------------------------------


def test_output_labels_count_vs_shape_checks():
    """The validator must say which checks are COUNT vs SHAPE+SKILLS."""
    rc, data = _run_json("--dir", str(FIXTURES), "--static-only")
    res = _result_for(data, "matching.js")
    blob = json.dumps(res).lower()
    assert "count" in blob and ("shape" in blob or "skills" in blob), res
