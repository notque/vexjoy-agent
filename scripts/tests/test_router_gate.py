"""Behavioral regressions for mandatory router handoffs, including bypasses."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import jev_intent_align
import router_gate as gate

_REAL_PROTECTED_GUARD = gate._protected_guard


def _decision(tmp_path: Path, *, router: str = "d", complexity: str = "simple") -> dict:
    (tmp_path / "task_plan.md").write_text("# Plan\nCheck and finish the requested change.\n")
    return {
        "router": router,
        "complexity": complexity,
        "agent": "python-general-engineer",
        "skill": "workflow",
        "pipeline": None,
        "source": "jev",
        "reasoning": "Python change",
        "plan_file": "task_plan.md",
        "stack": ["anti-rationalization-core"],
        "creation_request": False,
        "code_change": True,
        "explicit_workflow": False,
        "routing_steps": dict.fromkeys(("classification", "selection", "enhancement", "handoff"), "checked"),
        "routing_gates": {
            name: {"status": "not_applicable", "reason": "simple edit"}
            for name in ("creation", "quality_loop", "workflow", "composition")
        },
        "task_spec": {
            "request_verbatim": "$d fix the parser",
            "intent": "Fix the parser.",
            **dict.fromkeys(
                ("constraints", "decisions", "gaps", "acceptance", "files", "ownership", "operator_context"), "none"
            ),
        },
    }


@pytest.fixture(autouse=True)
def isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("JEV_ROUTER_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("JEV_SESSION_ID", "test-session")
    monkeypatch.setattr(gate, "_protected_guard", lambda *_: None)
    monkeypatch.setattr(
        jev_intent_align,
        "evaluate_alignment",
        lambda *_args: {"phase": "proposed", "alignment": "aligned", "aligned": True, "clarification_needed": False},
    )


@pytest.mark.parametrize("router", ["d", "do"])
@pytest.mark.parametrize(
    "source", ["jev", "pre-route-force", "jev-trivial-bypass", "unavailable", "error", "invalid-pick"]
)
def test_all_paths_run_actual_proposed_check(monkeypatch, tmp_path, router, source):
    decision = _decision(tmp_path, router=router, complexity="trivial" if source == "jev-trivial-bypass" else "simple")
    decision["source"] = source
    seen = []

    def evaluate(request, route, intent):
        seen.append((request, route, intent))
        return {"alignment": "aligned", "aligned": True, "clarification_needed": False}

    monkeypatch.setattr(jev_intent_align, "evaluate_alignment", evaluate)
    decision["intent_alignment"] = {"alignment": "aligned", "phase": "baseline"}
    gate.validate_router_handoff(decision, tmp_path, direct=decision["complexity"] == "trivial")
    assert len(seen) == 1
    assert seen[0][0] == decision["task_spec"]["request_verbatim"]
    assert seen[0][2] == decision["task_spec"]["intent"]
    assert seen[0][1]["source"] == source


@pytest.mark.parametrize(
    "field",
    [
        "request_verbatim",
        "intent",
        "constraints",
        "decisions",
        "gaps",
        "acceptance",
        "files",
        "ownership",
        "operator_context",
    ],
)
def test_missing_handoff_field_blocks(tmp_path, field):
    decision = _decision(tmp_path)
    del decision["task_spec"][field]
    with pytest.raises(gate.RouterGateError, match=field):
        gate.validate_router_handoff(decision, tmp_path)


@pytest.mark.parametrize("phase", ["classification", "selection", "enhancement", "handoff"])
def test_missing_phase_blocks(tmp_path, phase):
    decision = _decision(tmp_path)
    del decision["routing_steps"][phase]
    with pytest.raises(gate.RouterGateError, match=phase):
        gate.validate_router_handoff(decision, tmp_path)


def test_missing_plan_blocks(tmp_path):
    decision = _decision(tmp_path)
    (tmp_path / "task_plan.md").unlink()
    with pytest.raises(gate.RouterGateError, match=r"task_plan\.md"):
        gate.validate_router_handoff(decision, tmp_path)


@pytest.mark.parametrize(
    "name,updates",
    [
        ("creation", {"creation_request": True}),
        ("quality_loop", {"complexity": "medium"}),
        ("workflow", {"explicit_workflow": True}),
    ],
)
def test_applicable_gate_cannot_be_marked_inapplicable(tmp_path, name, updates):
    decision = _decision(tmp_path)
    decision.update(updates)
    with pytest.raises(gate.RouterGateError, match=name):
        gate.validate_router_handoff(decision, tmp_path)


def test_complex_requires_composition_or_explanation(tmp_path):
    decision = _decision(tmp_path, complexity="complex")
    for name in ("quality_loop", "workflow", "composition"):
        decision["routing_gates"][name]["status"] = "applied"
        decision["routing_gates"][name]["artifact"] = "task_plan.md"
    with pytest.raises(gate.RouterGateError, match="composition_exception"):
        gate.validate_router_handoff(decision, tmp_path)
    decision["composition_exception"] = "One tightly bounded Python module; no independent parallel work."
    assert gate.validate_router_handoff(decision, tmp_path)["aligned"]


@pytest.mark.parametrize(
    "receipt",
    [
        None,
        {},
        {"alignment": "unavailable"},
        {"alignment": "error"},
        {"alignment": "review", "aligned": False},
        {"alignment": "aligned", "aligned": True, "clarification_needed": True},
    ],
)
def test_no_approval_blocks_dispatch_and_allows_blocker_report(monkeypatch, tmp_path, receipt):
    decision = _decision(tmp_path)
    gate.set_required_router("test-session", "d", decision["task_spec"]["request_verbatim"])
    monkeypatch.setattr(jev_intent_align, "evaluate_alignment", lambda *_: receipt)
    with pytest.raises(gate.RouterGateError, match="did not approve"):
        gate.validate_router_handoff(decision, tmp_path)
    marker = gate.get_required_router("test-session")
    assert marker["pending"] is True
    assert marker["status"] == "checked_blocked"


def test_active_marker_prevents_omitting_router_or_changing_request(tmp_path):
    decision = _decision(tmp_path)
    gate.set_required_router("test-session", "d", decision["task_spec"]["request_verbatim"])
    del decision["router"]
    with pytest.raises(gate.RouterGateError, match="cannot be omitted"):
        gate.validate_router_handoff(decision, tmp_path)
    decision["router"] = "d"
    decision["task_spec"]["request_verbatim"] = "different request"
    with pytest.raises(gate.RouterGateError, match="current router invocation"):
        gate.validate_router_handoff(decision, tmp_path)


def test_success_does_not_let_followup_dispatch_reuse_old_check(monkeypatch, tmp_path):
    decision = _decision(tmp_path)
    request = decision["task_spec"]["request_verbatim"]
    gate.set_required_router("test-session", "d", request)
    gate.validate_router_handoff(decision, tmp_path)
    gate.mark_validated("test-session", request, decision["task_spec"]["intent"], {})
    assert gate.get_required_router("test-session")["pending"] is False
    decision["task_spec"]["intent"] = "Delete everything instead"
    monkeypatch.setattr(jev_intent_align, "evaluate_alignment", lambda *_: {"alignment": "review"})
    with pytest.raises(gate.RouterGateError, match="did not approve"):
        gate.validate_router_handoff(decision, tmp_path)
    assert gate.get_required_router("test-session")["pending"] is True


def test_corrupt_marker_fails_closed(tmp_path):
    gate.set_required_router("test-session", "d", "request")
    gate._marker_path("test-session").write_text("{")
    with pytest.raises(gate.RouterGateError, match="marker"):
        gate.validate_router_handoff({}, tmp_path)


def test_non_router_caller_unchanged(tmp_path):
    assert gate.validate_router_handoff({}, tmp_path) is None


def test_request_changes_while_check_in_flight_cannot_unlock_new_turn(tmp_path):
    gate.set_required_router("test-session", "d", "first")
    gate.set_required_router("test-session", "do", "second")
    with pytest.raises(gate.RouterGateError, match="request changed"):
        gate.mark_validated("test-session", "first", "intent", {})
    assert gate.get_required_router("test-session")["pending"] is True


def test_builder_direct_path_really_runs_gate(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("build_dispatch_router_test", SCRIPTS / "build-dispatch.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    decision = _decision(tmp_path, complexity="trivial")
    gate.set_required_router("test-session", "d", decision["task_spec"]["request_verbatim"])
    monkeypatch.setattr(jev_intent_align, "evaluate_alignment", lambda *_: {"alignment": "unavailable"})
    with pytest.raises(builder.InputError, match="did not approve"):
        builder.finalize_router(decision, tmp_path)
    monkeypatch.setattr(
        jev_intent_align,
        "evaluate_alignment",
        lambda *_: {"alignment": "aligned", "aligned": True, "clarification_needed": False},
    )
    assert json.loads(builder.finalize_router(decision, tmp_path))["router_finalized"] is True
    assert gate.get_required_router("test-session")["pending"] is False


def test_dispatch_authorization_is_exact_single_use_and_supports_fanout(tmp_path):
    gate.set_required_router("test-session", "d", "request")
    gate.authorize_dispatch("test-session", "request", "prompt A")
    gate.authorize_dispatch("test-session", "request", "prompt B")
    assert not gate.consume_dispatch("test-session", "prompt A changed")
    assert gate.consume_dispatch("test-session", "prompt A")
    assert not gate.consume_dispatch("test-session", "prompt A")
    assert gate.consume_dispatch("test-session", "prompt B")
    assert gate.get_required_router("test-session")["status"] == "dispatched"


def test_direct_validation_never_authorizes_agent_dispatch(tmp_path):
    gate.set_required_router("test-session", "d", "request")
    gate.mark_validated("test-session", "request", "intent", {})
    assert not gate.consume_dispatch("test-session", "anything")


def test_applicable_gate_requires_actual_artifact(tmp_path):
    decision = _decision(tmp_path, complexity="medium")
    decision["routing_gates"]["quality_loop"] = {"status": "applied", "reason": "will run"}
    with pytest.raises(gate.RouterGateError, match="artifact"):
        gate.validate_router_handoff(decision, tmp_path)


@pytest.mark.parametrize("direct", [False, True])
def test_same_request_new_turn_invalidates_old_check(tmp_path, direct):
    gate.set_required_router("test-session", "d", "same request")
    generation = gate.get_required_router("test-session")["generation"]
    gate.set_required_router("test-session", "d", "same request")
    with pytest.raises(gate.RouterGateError, match="changed"):
        if direct:
            gate.mark_validated("test-session", "same request", "intent", {}, expected_generation=generation)
        else:
            gate.authorize_dispatch("test-session", "same request", "prompt", expected_generation=generation)
    assert gate.get_required_router("test-session")["pending"] is True


def test_concurrent_fanout_and_consumption_do_not_lose_or_reuse_approvals(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    gate.set_required_router("test-session", "d", "request")
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda index: gate.authorize_dispatch("test-session", "request", f"prompt {index}"), range(20)))
    assert len(gate.get_required_router("test-session")["dispatch_prompt_hashes"]) == 20
    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(lambda _: gate.consume_dispatch("test-session", "prompt 0"), range(20)))
    assert sum(outcomes) == 1
    assert len(gate.get_required_router("test-session")["dispatch_prompt_hashes"]) == 19


def test_prior_context_reaches_actual_intent_evaluator(monkeypatch, tmp_path):
    decision = _decision(tmp_path)
    decision["task_spec"]["prior_context"] = ["Do not remove the intent checks."]
    seen = []

    def evaluate(request, route, intent, **kwargs):
        seen.append(kwargs["prior_context"])
        return {"alignment": "aligned", "aligned": True, "clarification_needed": False}

    monkeypatch.setattr(jev_intent_align, "evaluate_alignment", evaluate)
    gate.validate_router_handoff(decision, tmp_path)
    assert seen == [decision["task_spec"]["prior_context"]]


def test_builder_dispatch_binds_exact_emitted_prompt(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("build_dispatch_router_gate", SCRIPTS / "build-dispatch.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    monkeypatch.setattr(builder, "load_known_agents", lambda: frozenset({"python-general-engineer"}))
    monkeypatch.setattr(builder, "load_known_skills", lambda: frozenset({"workflow"}))
    monkeypatch.setattr(builder, "load_known_pipelines", frozenset)
    monkeypatch.setattr(builder, "load_known_stack_patterns", lambda: frozenset({"anti-rationalization-core"}))
    decision = _decision(tmp_path)
    decision["model"] = "inherit"
    decision["provider"] = "openai"
    gate.set_required_router("test-session", "d", decision["task_spec"]["request_verbatim"])
    output = builder.build_preamble(decision, gather=False, repo_root=tmp_path)
    assert "Intent alignment:" in output
    assert not gate.consume_dispatch("test-session", output + "extra instructions")
    assert gate.consume_dispatch("test-session", output)
    assert not gate.consume_dispatch("test-session", output)


def test_builder_rejects_unmanifested_agent_before_intent_check(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("build_dispatch_unknown_router", SCRIPTS / "build-dispatch.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    monkeypatch.setattr(builder, "load_known_agents", lambda: frozenset({"python-general-engineer", "general-purpose"}))
    monkeypatch.setattr(builder, "load_known_skills", lambda: frozenset({"workflow"}))
    monkeypatch.setattr(builder, "load_known_pipelines", frozenset)
    monkeypatch.setattr(builder, "load_known_stack_patterns", lambda: frozenset({"anti-rationalization-core"}))
    decision = _decision(tmp_path)
    decision.update(agent="unknown-agent", model="inherit", provider="openai")
    calls = []
    monkeypatch.setattr(jev_intent_align, "evaluate_alignment", lambda *_: calls.append(True))
    with pytest.raises(builder.InputError, match="live manifest"):
        builder.build_preamble(decision, gather=False, repo_root=tmp_path)
    assert not calls


def test_unprefixed_continuation_keeps_original_obligation(tmp_path, monkeypatch):
    decision = _decision(tmp_path)
    original = decision["task_spec"]["request_verbatim"]
    gate.set_required_router("test-session", "d", original)
    generation = gate.get_required_router("test-session")["generation"]
    gate.continue_required_router("test-session", "also preserve the checks")
    marker = gate.get_required_router("test-session")
    assert marker["pending"] is True
    assert marker["generation"] != generation
    decision["task_spec"]["request_verbatim"] = "also preserve the checks"
    with pytest.raises(gate.RouterGateError, match="prior_context"):
        gate.validate_router_handoff(decision, tmp_path)
    decision["task_spec"]["prior_context"] = [original]
    monkeypatch.setattr(
        jev_intent_align,
        "evaluate_alignment",
        lambda *_args, **_kwargs: {"alignment": "aligned", "aligned": True, "clarification_needed": False},
    )
    assert gate.validate_router_handoff(decision, tmp_path)["aligned"]


def test_long_continuation_retains_original_anchor_and_bounded_recent_context(tmp_path):
    gate.set_required_router("test-session", "d", "original request")
    for index in range(12):
        gate.continue_required_router("test-session", f"clarification {index}")
    hashes = gate.get_required_router("test-session")["prior_request_hashes"]
    assert len(hashes) == 8
    assert hashes[0] == gate.text_hash("original request")
    assert hashes[-1] == gate.text_hash("clarification 10")


def test_long_original_request_can_be_validated_on_continuation(tmp_path, monkeypatch):
    decision = _decision(tmp_path)
    original = "/d " + "x" * 16000
    gate.set_required_router("test-session", "d", original)
    gate.continue_required_router("test-session", "yes proceed")
    decision["task_spec"].update(request_verbatim="yes proceed", prior_context=[original])
    calls = []

    def evaluate(request, route, intent, **kwargs):
        calls.append(kwargs["prior_context"])
        return {"alignment": "aligned", "aligned": True, "clarification_needed": False}

    monkeypatch.setattr(jev_intent_align, "evaluate_alignment", evaluate)
    assert gate.validate_router_handoff(decision, tmp_path)["aligned"]
    assert calls == [[original]]


def test_oversized_continuation_reports_safe_restart_without_dropping_original(tmp_path, monkeypatch):
    decision = _decision(tmp_path)
    original = "/d " + "x" * 100000
    clarification = "y" * 90000
    gate.set_required_router("test-session", "d", original)
    gate.continue_required_router("test-session", clarification)
    decision["task_spec"].update(request_verbatim=clarification, prior_context=[original])
    called = []
    monkeypatch.setattr(jev_intent_align, "evaluate_alignment", lambda *_args, **_kwargs: called.append(True))
    with pytest.raises(gate.RouterGateError, match="Start a fresh /d or /do"):
        gate.validate_router_handoff(decision, tmp_path)
    marker = gate.get_required_router("test-session")
    assert marker["prior_request_hashes"] == [gate.text_hash(original)]
    assert marker["status"] == "checked_blocked"
    assert not called
    # The explicitly described recovery creates a feasible new obligation.
    restarted = "/d Fix the parser and preserve the existing intent checks."
    gate.set_required_router("test-session", "d", restarted)
    decision["task_spec"].update(request_verbatim=restarted, prior_context=[])
    monkeypatch.setattr(
        jev_intent_align,
        "evaluate_alignment",
        lambda *_args, **_kwargs: {"alignment": "aligned", "aligned": True, "clarification_needed": False},
    )
    assert gate.validate_router_handoff(decision, tmp_path)["aligned"]


@pytest.mark.parametrize("latest", ["yes proceed", "Do not push yet; prepare the patch locally."])
def test_continuation_cannot_remove_original_protected_guard(tmp_path, monkeypatch, latest):
    decision = _decision(tmp_path)
    original = "$d git push"
    gate.set_required_router("test-session", "d", original)
    gate.continue_required_router("test-session", latest)
    decision["task_spec"].update(request_verbatim=latest, prior_context=[original])
    monkeypatch.setattr(gate, "_protected_guard", _REAL_PROTECTED_GUARD)
    with pytest.raises(gate.RouterGateError, match="protected route requires skill pr-workflow"):
        gate.validate_router_handoff(decision, tmp_path)
    decision["skill"] = "pr-workflow"
    seen = []

    def evaluate(request, route, intent, **kwargs):
        seen.append((request, kwargs["prior_context"]))
        return {"alignment": "aligned", "aligned": True, "clarification_needed": False}

    monkeypatch.setattr(jev_intent_align, "evaluate_alignment", evaluate)
    assert gate.validate_router_handoff(decision, tmp_path)["aligned"]
    assert seen == [(latest, [original])]
