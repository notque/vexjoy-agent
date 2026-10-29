"""Tests for taste-harvest.py and taste-judge.py."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), _SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


harvest = _load("taste-harvest")
judge = _load("taste-judge")


def _rec(kind: str, content, ts: str = "2026-10-01T00:00:00Z", **extra) -> str:
    return json.dumps({"type": kind, "message": {"content": content}, "timestamp": ts, "sessionId": "s1", **extra})


def test_harvest_pairs_question_with_owner_reply(tmp_path: Path) -> None:
    f = tmp_path / "proj" / "s1.jsonl"
    f.parent.mkdir()
    lines = [
        _rec("user", "build the thing"),
        _rec("assistant", [{"type": "text", "text": "Done. Want me to add tests too?"}]),
        _rec("user", "yes, add them"),
        _rec("assistant", [{"type": "text", "text": "Added the tests."}]),
        _rec("user", "thanks"),
    ]
    f.write_text("\n".join(lines), encoding="utf-8")
    pairs = harvest.harvest_file(str(f))
    assert [p["owner"] for p in pairs] == ["yes, add them"]
    assert pairs[0]["cue"] == "approval"


def test_harvest_keeps_corrections_without_question(tmp_path: Path) -> None:
    f = tmp_path / "proj" / "s1.jsonl"
    f.parent.mkdir()
    lines = [
        _rec("assistant", [{"type": "text", "text": "I disabled the feature."}]),
        _rec("user", "no, revert that"),
    ]
    f.write_text("\n".join(lines), encoding="utf-8")
    assert [p["cue"] for p in harvest.harvest_file(str(f))] == ["correction"]


def test_harvest_skips_tool_results_sidechains_and_skill_bodies(tmp_path: Path) -> None:
    f = tmp_path / "proj" / "s1.jsonl"
    f.parent.mkdir()
    lines = [
        _rec("assistant", [{"type": "text", "text": "Proceed?"}]),
        _rec("user", [{"type": "tool_result", "content": "ok"}]),
        _rec("user", "no from a subagent", isSidechain=True),
        _rec("user", "# /do\n\nRead and follow the full skill file at x"),
        _rec("user", "<task-notification>done</task-notification>"),
    ]
    f.write_text("\n".join(lines), encoding="utf-8")
    assert harvest.harvest_file(str(f)) == []


def test_split_is_chronological_and_drops_undecidable() -> None:
    pairs = [{"ts": f"2026-10-0{i}", "assistant": f"a{i}?", "owner": "o"} for i in range(1, 6)]
    labels = [
        {"id": 4, "decidable": True, "label": "approve"},
        {"id": 0, "decidable": True, "label": "send_back"},
        {"id": 1, "decidable": False},
        {"id": 2, "decidable": True, "label": "pick_other"},
        {"id": 3, "decidable": True, "label": "bogus"},
    ]
    train, test = judge.split(pairs, labels, 0.67)
    assert [r["id"] for r in train] == [0, 2]
    assert [r["id"] for r in test] == [4]


def test_split_drops_duplicate_pairs() -> None:
    pairs = [{"ts": "2026-10-01", "assistant": "a?", "owner": "o"}] * 2 + [
        {"ts": "2026-10-02", "assistant": "b?", "owner": "p"}
    ]
    labels = [{"id": i, "decidable": True, "label": "approve"} for i in range(3)]
    train, test = judge.split(pairs, labels, 0.5)
    assert [r["id"] for r in train + test] == [0, 2]


def test_build_case_is_blind() -> None:
    row = {"id": 7, "assistant": "Want X?", "owner": "SECRET", "label": "approve", "options": ["X"], "domain": "d"}
    case = judge.build_case(row, [{"id": "p1", "rule": "r"}])
    blob = json.dumps(case)
    assert "SECRET" not in blob
    assert '"approve"' in blob  # option name in criteria only
    assert "label" not in case["state"]["case"]
    assert set(case["questions"]["verdict"]["criteria"]) == {"approve", "pick_other", "send_back", "hold"}
    assert "owner_principles" not in judge.build_case(row, None)["state"]


def test_score_separates_hold_from_errors() -> None:
    truth = {1: "approve", 2: "send_back", 3: "approve", 4: "pick_other"}
    answers = [
        {"id": 1, "choice": "approve"},
        {"id": 2, "choice": "approve"},
        {"id": 3, "choice": "hold"},
        {"id": 4, "choice": "pick_other"},
        {"id": 99, "choice": "approve"},
    ]
    s = judge.score(answers, truth)
    assert s["cases"] == 4
    assert s["decided"] == 3
    assert s["accuracy_on_decided"] == round(2 / 3, 3)
    assert s["forced_accuracy"] == 0.5
    assert s["hold_rate"] == 0.25
    assert s["majority_class_rate"] == 0.5
