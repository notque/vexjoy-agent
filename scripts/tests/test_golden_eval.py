"""Tests for scripts/golden_eval: task labels, routing scorer, e2e helpers (offline, no model or Jev calls)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
GOLDEN = REPO / "scripts" / "golden_eval"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"golden_{name}", GOLDEN / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rr = _load("run_routing")
e2e = _load("run_e2e")
PATTERNS = frozenset(p.stem for p in (REPO / "skills" / "shared-patterns").glob("*.md"))
# Private overlay skills (INDEX.local.json) appear only in the owner's manifest.
PRIVATE_OK: frozenset[str] = frozenset()


@pytest.fixture(scope="module")
def catalog(public_index_dir):
    import os

    env = dict(os.environ, VEXJOY_INDEX_DIR=str(public_index_dir))
    out = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "routing-manifest.py"), "--json"],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    ).stdout
    entries = json.loads(out)
    return {
        "skills": {e["name"] for e in entries if e["type"] == "skill"},
        "pipelines": {e["name"] for e in entries if e["type"] == "pipeline"},
    }


def test_tasks_are_unique_and_name_only_real_components(catalog) -> None:
    tasks = rr.load_tasks()
    assert 10 <= len(tasks) <= 16
    assert len({t["id"] for t in tasks}) == len(tasks)
    for t in tasks:
        names = set(t["skill"]) | set(t["forbid"]) | {s for g in t["required"] for s in g}
        for name in names:
            assert name in catalog["skills"] or name in PRIVATE_OK, (t["id"], name)
        for pipe in t["pipeline"]:
            assert pipe is None or pipe in catalog["pipelines"], (t["id"], pipe)
        assert set(t["d_exec"]["reasons"]) <= set(rr.d_gate.DISPATCH_REASONS), t["id"]
        assert t["rubric"], t["id"]
        if t["e2e"]:
            assert t.get("acceptance"), t["id"]


def test_fixture_test_file_is_not_collected_by_the_repo_suite() -> None:
    assert not list((GOLDEN / "fixture").rglob("test_*.py"))


TASK = {
    "id": "x",
    "skill": ["debugging", "workflow"],
    "pipeline": ["systematic-debugging", None],
    "required": [["testing"]],
    "forbid": ["pr-workflow"],
    "d_exec": {"main": True, "reasons": ["verifier"], "expect_dispatch": False},
}


def test_score_row_route_and_exec() -> None:
    decision = {
        "skill": "workflow",
        "pipeline": "systematic-debugging",
        "stack": ["testing", "anti-rationalization-core"],
        "complexity": "medium",
        "execution": [{"part": "primary", "mode": "main", "dispatch_reason": None}],
    }
    s = rr.score_row(TASK, "do", decision, None, PATTERNS)
    assert s["route_ok"] and s["exec_ok_d"] and s["main_parts"] == 1
    bad = {**decision, "execution": [{"part": "primary", "mode": "dispatch", "dispatch_reason": "convenience"}]}
    s = rr.score_row(TASK, "d", bad, {**decision, "attach": ["testing"]}, PATTERNS)
    assert s["route_ok"] and not s["plan_valid_d"] and not s["exec_ok_d"]
    forbidden = rr.score_row(TASK, "do", {**decision, "stack": ["pr-workflow", "testing"]}, None, PATTERNS)
    assert not forbidden["route_ok"] and forbidden["forbidden"] == ["pr-workflow"]


def test_trivial_task_scores_on_complexity() -> None:
    task = {**TASK, "expect_trivial": True, "skill": [], "pipeline": [None], "required": []}
    assert rr.score_row(task, "d", {"complexity": "trivial", "execution": []}, {"skill": "workflow"}, PATTERNS)[
        "route_ok"
    ]
    assert not rr.score_row(task, "do", {"complexity": "simple", "skill": "quick"}, None, PATTERNS)["route_ok"]


def test_aggregate_counts_per_run_and_all_runs() -> None:
    rows = []
    for run, ok in ((1, True), (2, False)):
        s = rr.score_row(TASK, "d", {"skill": "workflow" if ok else "review", "stack": ["testing"]}, None, PATTERNS)
        s["run"] = run
        rows.append(s)
    agg = rr.aggregate(rows, 2)["d"]
    assert agg["route_ok_per_run"] == {"1": 1, "2": 0}
    assert agg["route_ok_all_runs"] == 0 and agg["changed_between_runs"] == ["x"]


def test_jev_tokens_reads_known_usage_shapes() -> None:
    assert rr.jev_tokens({"input_tokens": 799, "output_tokens": 210}) == 1009
    assert rr.jev_tokens({"total_tokens": 5}) == 5
    assert rr.jev_tokens(None) == 0


def test_e2e_refuses_without_launch(capsys) -> None:
    with pytest.raises(SystemExit):
        e2e.main(["--out-dir", "/nonexistent-golden-e2e"])
    assert e2e.main(["--estimate"]) == 0
    est = json.loads(capsys.readouterr().out)
    assert est["sessions"] == len(e2e.load_tasks()) * 2 * 2


def test_e2e_workdir_and_acceptance(tmp_path: Path) -> None:
    task = next(t for t in e2e.load_tasks() if t["id"] == "g03-review-diff")
    work = e2e.make_workdir(task, tmp_path)
    log = subprocess.run(["git", "log", "--oneline"], cwd=work, capture_output=True, text=True, check=True).stdout
    assert len(log.splitlines()) == 2 and (work / "simsim" / "scoring.py").is_file()
    results = e2e.check_acceptance(task, work, "A draw scores 3 points here; it should be 1.")
    assert all(r["ok"] for r in results)
    assert not e2e.check_acceptance(task, work, "looks good")[1]["ok"]


def test_e2e_tool_use_parsing() -> None:
    events = [
        {
            "t": "t1",
            "e": {
                "type": "assistant",
                "message": {"content": [{"type": "tool_use", "name": "Skill", "input": {"skill": "d"}}]},
            },
        },
        {
            "t": "t2",
            "e": {
                "type": "assistant",
                "message": {
                    "content": [{"type": "tool_use", "name": "Agent", "input": {"subagent_type": "general-purpose"}}]
                },
            },
        },
        {"t": "t3", "e": {"type": "result", "result": "done", "total_cost_usd": 1.0}},
    ]
    uses = e2e.tool_uses(events)
    assert [u["name"] for u in uses] == ["Skill", "Agent"]
    assert e2e.final_result(events)["result"] == "done"


def test_verdict_is_numbers_per_router(tmp_path: Path) -> None:
    rows = []
    for router in ("d", "do"):
        for run in (1, 2):
            decision = {"skill": "workflow", "stack": ["testing"], "complexity": "medium"}
            decision["execution"] = [{"part": "p", "mode": "main" if router == "d" else "dispatch"}]
            rows.append(
                {
                    "id": "g01-debug-truncation",
                    "router": router,
                    "run": run,
                    "started": "2026-11-17T00:00:00+00:00",
                    "ended": "2026-11-17T00:01:00+00:00",
                    "decision": decision,
                    "final": {"skill": "workflow", "attach": ["testing"]} if router == "d" else None,
                    "cost_usd": 0.1,
                    "jev_tokens": 1000 if router == "d" else 0,
                    "prepared": {"usage": {"input_tokens": 800, "output_tokens": 200}} if router == "d" else None,
                    "model": "opus",
                }
            )
    (tmp_path / "rows.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    tasks = [t for t in rr.load_tasks() if t["id"] == "g01-debug-truncation"]
    summary = rr.score_dir(tmp_path, tasks, PATTERNS)
    verdict = (tmp_path / "VERDICT.md").read_text(encoding="utf-8")
    assert "| Route correct per run (of 1) | 1 / 1 | 1 / 1 |" in verdict
    assert "Jev: 2 calls, 0 of them served from the Jev cache, 2000 tokens" in verdict
    assert summary["routers"]["d"]["main_part_share"] == 1.0
    for word in ("better", "winner", "wins"):
        assert word not in verdict.lower()


def test_run_session_kills_silent_hung_subprocess(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A silent hung subprocess with no stdout output is killed by the daemon timeout timer."""
    real_popen = subprocess.Popen

    def fake_popen(_cmd, **kwargs):
        return real_popen([sys.executable, "-c", "import time; time.sleep(30)"], **kwargs)

    monkeypatch.setattr(e2e, "SESSION_TIMEOUT_S", 0.2)
    monkeypatch.setattr(e2e.subprocess, "Popen", fake_popen)

    result = e2e.run_session("d", "hang test", tmp_path, {}, "opus")
    assert result["events"] == []
    assert result["exit"] != 0
    assert result["seconds"] < 5.0
