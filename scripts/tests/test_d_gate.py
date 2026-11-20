"""Tests for /d's tool-enforced rules: scripts/d_gate.py and build-dispatch.py's /d mode.

Covers the intent receipt (written by jev_intent_align on every path, read by
build-dispatch with "router": "d"), the dispatch-reason enum and preconditions,
the skill-reference handover, the router marker tokens and their recorder
round trip, and that /do output carries none of it.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))

import d_gate
import jev_intent_align

pytestmark = pytest.mark.usefixtures("use_public_index")


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    with patch("sys.exit"):
        spec.loader.exec_module(mod)
    return mod


bd = _load(SCRIPTS / "build-dispatch.py", "build_dispatch_d")
recorder = _load(REPO / "hooks" / "routing-decision-recorder.py", "routing_decision_recorder_d")

REQUEST = "fix the flaky test in pkg/api and nothing else"
INTENT = "Fix the flaky test in pkg/api; change nothing else."
ACCEPTANCE = "go test ./pkg/api -count=20 passes"


def _receipt(alignment: str = "aligned", *, request: str = REQUEST, intent: str = INTENT, phase="proposed", **extra):
    result = {"alignment": alignment, "issues": extra.pop("issues", []), **extra}
    return d_gate.write_receipt(request, intent, result, phase)


def _decision(**overrides) -> dict:
    decision = {
        "router": "d",
        "skill": "programming",
        "complexity": "medium",
        "task_spec": {"request_verbatim": REQUEST, "intent": INTENT, "acceptance": ACCEPTANCE},
    }
    decision.update(overrides)
    return decision


def _preamble(decision: dict) -> str:
    return bd.build_preamble(decision, gather=False)


# ------------------------------------------------------------------ receipts


def test_receipt_holds_hashes_only_and_is_owner_only() -> None:
    path = _receipt()
    assert path is not None and path.is_file()
    body = path.read_text(encoding="utf-8")
    assert REQUEST not in body and INTENT not in body
    assert oct(path.stat().st_mode & 0o777) == "0o600"


def test_missing_receipt_names_the_command_to_run() -> None:
    problem = d_gate.check_receipt({"request_verbatim": REQUEST, "intent": INTENT})
    assert problem and "jev-intent-align.py" in problem and "--proposed-intent-file" in problem


def test_trailing_newline_in_the_request_file_still_matches() -> None:
    _receipt(request=REQUEST + "\n")
    assert d_gate.check_receipt({"request_verbatim": REQUEST, "intent": INTENT}) is None


def test_receipt_for_another_intent_is_refused() -> None:
    _receipt(intent="Rewrite the whole api package.")
    problem = d_gate.check_receipt({"request_verbatim": REQUEST, "intent": INTENT})
    assert problem and "different intent" in problem


def test_baseline_receipt_is_refused() -> None:
    _receipt(phase="baseline")
    assert "proposed-intent-file" in d_gate.check_receipt({"request_verbatim": REQUEST, "intent": INTENT})


def test_stale_receipt_is_refused() -> None:
    _receipt()
    later = time.time() + d_gate.RECEIPT_MAX_AGE_S + 5
    assert "older than 6 hours" in d_gate.check_receipt({"request_verbatim": REQUEST, "intent": INTENT}, now=later)


@pytest.mark.parametrize("alignment", ["unavailable", "error", "aligned"])
def test_fail_open_and_aligned_receipts_allow_execution(alignment: str) -> None:
    _receipt(alignment)
    assert d_gate.check_receipt({"request_verbatim": REQUEST, "intent": INTENT}) is None


def test_clarification_stops_until_the_answer_is_recorded() -> None:
    _receipt("review", clarification_needed=True)
    spec = {"request_verbatim": REQUEST, "intent": INTENT, "gaps": "x"}
    assert "Ask the user" in d_gate.check_receipt(spec)
    assert d_gate.check_receipt({**spec, "clarification": "only pkg/api"}) is None


def test_review_needs_the_issues_carried_into_gaps() -> None:
    _receipt("review", issues=["proposed intent drops material scope"])
    spec = {"request_verbatim": REQUEST, "intent": INTENT}
    problem = d_gate.check_receipt(spec)
    assert "task_spec.gaps" in problem and "drops material scope" in problem
    assert d_gate.check_receipt({**spec, "gaps": "scope: confirm pkg/api only"}) is None


def test_intent_align_writes_a_receipt_even_when_jev_is_unavailable() -> None:
    result = jev_intent_align.evaluate_alignment(REQUEST, {"skill": "programming"}, INTENT)
    assert result["alignment"] == "unavailable"
    assert d_gate.check_receipt({"request_verbatim": REQUEST, "intent": INTENT}) is None


def test_session_scoping_isolates_receipts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "session-a")
    monkeypatch.delenv("JEV_SESSION_ID", raising=False)
    _receipt()
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "session-b")
    assert d_gate.check_receipt({"request_verbatim": REQUEST, "intent": INTENT}) is not None


# ------------------------------------------------------------------ build-dispatch /d mode


def test_d_route_without_receipt_is_refused_with_the_command() -> None:
    with pytest.raises(bd.InputError, match=r"jev-intent-align\.py"):
        _preamble(_decision())


def test_d_defaults_to_the_main_loop_and_marks_the_router() -> None:
    _receipt()
    out = _preamble(_decision())
    marker = out.splitlines()[0]
    assert marker.endswith(" router=d exec=main")
    assert "agent=main" in marker and "Call the Skill tool with `programming`." in out
    assert "## Task Specification" not in out


def test_d_main_loop_pipeline_gets_the_in_order_note() -> None:
    _receipt()
    out = _preamble(_decision(pipeline="systematic-debugging"))
    assert "Run every pipeline phase in order in this thread" in out
    assert "OBSERVE -> HYPOTHESIZE -> TEST -> FIX -> RECORD" in out
    assert bd.INJ_REFERENCE_LOADING in out


def test_d_main_loop_carries_local_only() -> None:
    _receipt()
    out = _preamble(_decision(stack=["programming", "local-only"]))
    assert bd.LOCAL_ONLY_BLOCK in out
    assert bd.LOCAL_ONLY_BLOCK not in _preamble(_decision())


def test_flat_installed_layout_resolves_the_skill_dir(tmp_path: Path) -> None:
    flat = tmp_path / "skills" / "programming"
    (flat / "references").mkdir(parents=True)
    (flat / "SKILL.md").write_text("x", encoding="utf-8")
    (flat / "references" / "go.md").write_text("x", encoding="utf-8")
    entries = {"programming": {"file": "skills/programming/programming/SKILL.md"}}
    refs, problem = d_gate.resolve_references("programming", ["go"], entries, [tmp_path])
    assert problem is None and refs == [str((flat / "references" / "go.md").resolve())]


def test_unresolvable_skill_dir_refuses_instead_of_passing(tmp_path: Path) -> None:
    refs, problem = d_gate.resolve_references("nope", [], {}, [tmp_path])
    assert refs == [] and "cannot find skill" in problem


def test_d_trivial_goes_through_the_gate() -> None:
    _receipt()
    out = _preamble(_decision(skill="-", complexity="trivial"))
    assert out.startswith("[do-route] agent=main skill=- complexity=trivial") and "router=d exec=main" in out
    assert "intent=skipped" not in out


@pytest.mark.parametrize("request_text", ["what is 2+2", "thanks", "push my changes and open a PR", ""])
def test_d_trivial_never_skips_the_intent_validator(request_text: str) -> None:
    """Owner, 2026-11-19: every /d route runs the intent check, Trivial included."""
    trivial = {"router": "d", "skill": "-", "complexity": "trivial", "task_spec": {"request_verbatim": request_text}}
    with pytest.raises(bd.InputError, match=r"jev-intent-align\.py|task_spec\.intent|request_verbatim"):
        _preamble(trivial)


# ------------------------------------------------------------------ verify


def test_medium_main_route_needs_acceptance() -> None:
    _receipt()
    with pytest.raises(bd.InputError, match=r"task_spec\.acceptance"):
        _preamble(_decision(task_spec={"request_verbatim": REQUEST, "intent": INTENT}))


def test_simple_main_route_needs_no_acceptance() -> None:
    _receipt()
    out = _preamble(_decision(complexity="simple", task_spec={"request_verbatim": REQUEST, "intent": INTENT}))
    assert "verify=required" not in out and "Before you report done" not in out


@pytest.mark.parametrize("path", ["hooks/sync-to-user-claude.py", "scripts/vexinstall/plan.py", "scripts/jev-route.py"])
def test_risky_paths_need_a_real_scenario(path: str) -> None:
    _receipt()
    spec = {"request_verbatim": REQUEST, "intent": INTENT, "acceptance": ACCEPTANCE, "files": path}
    with pytest.raises(bd.InputError, match=r"task_spec\.scenario"):
        _preamble(_decision(task_spec=spec))
    spec["scenario"] = "install origin/main into a temp HOME, switch to the branch, run sync and doctor"
    out = _preamble(_decision(task_spec=spec))
    assert "verify=required router=d exec=main" in out.splitlines()[0]
    assert "dispatch_reason verifier" in out and "install origin/main into a temp HOME" in out


def test_ordinary_paths_need_no_scenario() -> None:
    _receipt()
    spec = {"request_verbatim": REQUEST, "intent": INTENT, "acceptance": ACCEPTANCE, "files": "pkg/api/client.go"}
    assert "Before you report done" in _preamble(_decision(task_spec=spec))


def test_scenario_paths_normalize_absolute_and_ranged_entries() -> None:
    hits = d_gate.scenario_paths("/home/u/vexjoy-agent/hooks/x.py:10-40, ./scripts/d_gate.py docs/a.md")
    assert hits == ["hooks/x.py", "scripts/d_gate.py"]


# ------------------------------------------------------------------ context budget


def test_context_budget_is_measured(tmp_path: Path) -> None:
    small = tmp_path / "small"
    small.mkdir()
    (small / "a.md").write_text("x" * 100, encoding="utf-8")
    big = tmp_path / "big"
    big.mkdir()
    for i in range(10):
        (big / f"f{i}.md").write_text("x", encoding="utf-8")
    heavy = tmp_path / "heavy.log"
    heavy.write_text("x" * (60 * 1024), encoding="utf-8")
    assert "names 1 files" in d_gate.check_budget({"acceptance": "x", "files": "small"}, tmp_path)
    assert d_gate.check_budget({"acceptance": "x", "files": "big"}, tmp_path) is None
    assert d_gate.check_budget({"acceptance": "x", "files": ["heavy.log"]}, tmp_path) is None
    assert "acceptance" in d_gate.check_budget({"files": "big"}, tmp_path)
    assert "names 0 files" in d_gate.check_budget({"acceptance": "x", "files": "missing/"}, tmp_path)


def test_context_budget_dispatch_through_build_dispatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _receipt()
    monkeypatch.chdir(tmp_path)
    for i in range(12):
        (tmp_path / f"f{i}.md").write_text("x", encoding="utf-8")
    spec = {"request_verbatim": REQUEST, "intent": INTENT, "acceptance": "a findings list", "files": "."}
    base = _decision(execution="dispatch", model="opus", dispatch_reason="context-budget", task_spec=spec)
    with pytest.raises(bd.InputError, match="references"):
        _preamble(base)
    small = dict(base, task_spec=dict(spec, files="f0.md"))
    with pytest.raises(bd.InputError, match="at least 10 existing files"):
        _preamble(small)


def test_d_dispatch_needs_an_allowed_reason() -> None:
    _receipt()
    with pytest.raises(bd.InputError, match="fan-out"):
        _preamble(_decision(execution="dispatch", model="opus"))
    with pytest.raises(bd.InputError, match="one of"):
        _preamble(_decision(execution="dispatch", model="opus", dispatch_reason="convenience"))


def test_main_loop_rejects_a_dispatch_reason() -> None:
    _receipt()
    with pytest.raises(bd.InputError, match="only to execution='dispatch'"):
        _preamble(_decision(dispatch_reason="fan-out"))


@pytest.mark.parametrize(
    ("reason", "extra", "message"),
    [
        ("worktree", {}, "flags.worktree"),
        ("haiku-gather", {}, "model haiku"),
        ("fan-out", {}, "ownership"),
        ("verifier", {"task_spec": {"request_verbatim": REQUEST, "intent": INTENT}}, "acceptance"),
        ("context-budget", {}, "at least 10 existing files"),
    ],
)
def test_each_reason_checks_its_precondition(reason: str, extra: dict, message: str) -> None:
    _receipt()
    with pytest.raises(bd.InputError, match=message):
        _preamble(_decision(execution="dispatch", model="opus", dispatch_reason=reason, **extra))


def test_dispatch_must_hand_over_a_skill_reference() -> None:
    _receipt()
    spec = {"request_verbatim": REQUEST, "intent": INTENT, "ownership": "pkg/api"}
    decision = _decision(execution="dispatch", model="opus", dispatch_reason="fan-out", task_spec=spec)
    with pytest.raises(bd.InputError, match="references"):
        _preamble(decision)
    with pytest.raises(bd.InputError, match="not a file"):
        _preamble({**decision, "references": ["no-such-reference.md"]})


def test_dispatch_with_reason_and_reference_builds_the_worker_preamble() -> None:
    _receipt()
    refs = d_gate.available_references(REPO / "skills" / "programming" / "programming")
    assert "references/golang-general.md" in refs
    spec = {"request_verbatim": REQUEST, "intent": INTENT, "ownership": "pkg/api"}
    decision = _decision(
        execution="dispatch",
        model="opus",
        dispatch_reason="fan-out",
        references=["golang-general"],
        task_spec=spec,
    )
    out = _preamble(decision)
    marker = out.splitlines()[0]
    assert marker.startswith("[do-route] agent=general-purpose skill=programming")
    assert marker.endswith(" reason=fan-out router=d")
    ref = REPO / "skills" / "programming" / "programming" / "references" / "golang-general.md"
    assert f"`{ref.resolve()}`" in out
    assert "## Task Specification" in out or "Request (verbatim)" in out


def test_do_output_carries_no_router_token() -> None:
    out = _preamble({"execution": "main", "skill": "programming", "complexity": "simple"})
    assert "router=" not in out and "reason=" not in out.splitlines()[0]


def test_unknown_router_is_an_input_error() -> None:
    with pytest.raises(bd.InputError, match="router"):
        _preamble(_decision(router="x"))


def test_cli_refusal_exits_2_with_the_instruction_on_stderr(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "build-dispatch.py"), "--json", json.dumps(_decision()), "--no-record"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 2 and proc.stdout == ""
    assert "jev-intent-align.py" in proc.stderr


# ------------------------------------------------------------------ recorder round trip


def test_recorder_reads_router_and_reason_tokens() -> None:
    _receipt()
    spec = {"request_verbatim": REQUEST, "intent": INTENT, "acceptance": "pytest -> pass"}
    decision = _decision(
        execution="dispatch", model="opus", dispatch_reason="verifier", references=["golang-general"], task_spec=spec
    )
    marker = _preamble(decision).splitlines()[0]
    assert recorder.parse_router(marker) == "d"
    assert recorder.parse_dispatch_reason(marker) == "verifier"
    assert recorder.parse_do_route_marker(marker) == ("general-purpose", "programming")
    do_marker = "[do-route] agent=main skill=programming complexity=simple model=inherit health=- exec=main"
    assert recorder.parse_router(do_marker) == "do"
    assert recorder.parse_dispatch_reason(do_marker) is None
    assert recorder.parse_router("[do-route] agent=main skill=x\nprose router=d") == "do"


def test_recorder_reads_d_flags_and_context_budget() -> None:
    marker = "[do-route] agent=main skill=x complexity=medium verify=required router=d exec=main"
    assert recorder.parse_d_flags(marker) == ["verify=required"]
    assert recorder.parse_d_flags("[do-route] agent=main skill=x exec=main") is None
    assert recorder.parse_dispatch_reason("[do-route] agent=general-purpose reason=context-budget router=d") == (
        "context-budget"
    )


def test_router_metrics_counts_verifier_followthrough() -> None:
    metrics = _load(SCRIPTS / "router-metrics.py", "router_metrics_d")
    row = {"session": "s", "router": "d", "agent": "main", "skill": "x", "pipeline": None, "dispatch_reason": None}
    rows = [
        {**row, "ts": 1.0, "d_flags": ["verify=required"]},
        {**row, "ts": 2.0, "agent": "general-purpose", "dispatch_reason": "verifier", "d_flags": []},
        {**row, "ts": 3.0, "session": "t", "d_flags": ["verify=required"]},
    ]
    out = metrics.summarize(rows, {})["d"]
    assert out["verify"] == {"required": 2, "verified": 1, "rate": metrics._rate(1, 2)}
    assert "intent_skipped_rate" not in out


# ------------------------------------------------------------------ verifier findings (PR review of the /d upgrade)


def test_scenario_paths_read_absolute_worktree_and_bare_dir_paths(tmp_path: Path) -> None:
    assert d_gate.scenario_paths("/home/u/vexjoy-agent/.claude/worktrees/x/hooks/a.py", tmp_path) == ["hooks/a.py"]
    assert d_gate.scenario_paths("/srv/other-clone/scripts/vexinstall/plan.py", tmp_path) == [
        "scripts/vexinstall/plan.py"
    ]
    assert d_gate.scenario_paths("hooks scripts/vexinstall", tmp_path) == ["hooks", "scripts/vexinstall"]
    inside = tmp_path / "hooks" / "b.py"
    assert d_gate.scenario_paths(str(inside), tmp_path) == ["hooks/b.py"]
    assert d_gate.scenario_paths("/srv/other/docs/readme.md", tmp_path) == []


def test_context_budget_ignores_paths_outside_the_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    for i in range(12):
        (outside / f"f{i}.md").write_text("x", encoding="utf-8")
    assert d_gate.measure_scope(["~", "/", "../outside", str(outside)], repo) == (0, 0)


def test_context_budget_survives_unreadable_entries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "d").mkdir()

    def boom(*_a, **_k):
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "rglob", boom)
    assert d_gate.measure_scope(["d"], tmp_path) == (0, 0)
