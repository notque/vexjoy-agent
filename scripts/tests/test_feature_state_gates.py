"""Tests for feature-state.py approval gates, state writes, and agent topic matching.

- A human gate never switches to automatic over an explicit override, and an
  automatic switch is never saved to the state file. Every switch is logged.
- save_state replaces the state file atomically, so a failed write leaves the
  previous state readable.
- retro-candidates matches agents by the ``retro-topics`` frontmatter key and
  by the ``process-topics`` spelling some agents still carry.
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

feature_state = importlib.import_module("feature-state")


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "repo"
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.chdir(path)
    for key in ("CLAUDE_RETRO_GATE_L2_CONTEXT", "CLAUDE_RETRO_GATE_L3_RECORDS"):
        monkeypatch.delenv(key, raising=False)
    return path


def _main(monkeypatch: pytest.MonkeyPatch, *argv: str) -> int:
    monkeypatch.setattr(sys, "argv", ["feature-state.py", *argv])
    return feature_state.main()


def _init(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], gates: dict[str, str]) -> Path:
    assert _main(monkeypatch, "init", "demo") == 0
    capsys.readouterr()
    state_file = Path.cwd() / ".feature" / "state" / "demo.json"
    data = json.loads(state_file.read_text())
    data["gates"].update(gates)
    state_file.write_text(json.dumps(data))
    return state_file


def _gate(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], gate_id: str) -> tuple[int, dict]:
    rc = _main(monkeypatch, "gate", "demo", gate_id)
    return rc, json.loads(capsys.readouterr().out)


def _switch_log(repo: Path) -> list[dict]:
    log = repo / ".feature" / "state" / "gate-switches.jsonl"
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


def test_explicit_human_override_beats_confidence_flip(repo, monkeypatch, capsys):
    state_file = _init(monkeypatch, capsys, {"retro.l2-context": "auto"})
    monkeypatch.setattr(feature_state, "_get_gate_confidence", lambda _gate_id: 0.95)
    monkeypatch.setenv("CLAUDE_RETRO_GATE_L2_CONTEXT", "human")

    rc, out = _gate(monkeypatch, capsys, "retro.l2-context")

    assert rc == 2
    assert out["mode"] == "human"
    assert out["requires_human"] is True
    assert out["auto_flipped"] is False
    assert json.loads(state_file.read_text())["gates"]["retro.l2-context"] == "auto"


def test_confidence_flip_is_not_saved(repo, monkeypatch, capsys):
    state_file = _init(monkeypatch, capsys, {})
    monkeypatch.setattr(feature_state, "_get_gate_confidence", lambda _gate_id: 0.95)

    rc, out = _gate(monkeypatch, capsys, "design.approach-selection")

    assert rc == 0
    assert out["mode"] == "auto"
    assert out["auto_flipped"] is True
    assert json.loads(state_file.read_text())["gates"]["design.approach-selection"] == "human"
    # The next call with no confidence is human again: nothing stuck.
    monkeypatch.setattr(feature_state, "_get_gate_confidence", lambda _gate_id: 0.0)
    rc, out = _gate(monkeypatch, capsys, "design.approach-selection")
    assert rc == 2
    assert out["mode"] == "human"


def test_every_switch_is_logged(repo, monkeypatch, capsys):
    _init(monkeypatch, capsys, {"retro.l3-records": "auto"})
    monkeypatch.setattr(feature_state, "_get_gate_confidence", lambda _gate_id: 0.95)
    _gate(monkeypatch, capsys, "design.design-approval")
    monkeypatch.setenv("CLAUDE_RETRO_GATE_L3_RECORDS", "human")
    _gate(monkeypatch, capsys, "retro.l3-records")
    monkeypatch.setattr(feature_state, "_get_gate_confidence", lambda _gate_id: 0.0)
    _gate(monkeypatch, capsys, "plan.plan-approval")  # no switch: nothing logged

    entries = _switch_log(repo)
    assert [(e["gate_id"], e["from"], e["to"], e["reason"]) for e in entries] == [
        ("design.design-approval", "human", "auto", "confidence"),
        ("retro.l3-records", "auto", "human", "override"),
    ]
    assert all(e["feature"] == "demo" and e["timestamp"] for e in entries)


def test_no_switch_below_threshold(repo, monkeypatch, capsys):
    state_file = _init(monkeypatch, capsys, {})
    monkeypatch.setattr(feature_state, "_get_gate_confidence", lambda _gate_id: 0.5)

    rc, out = _gate(monkeypatch, capsys, "design.approach-selection")

    assert (rc, out["mode"], out["auto_flipped"]) == (2, "human", False)
    assert json.loads(state_file.read_text())["gates"]["design.approach-selection"] == "human"
    assert _switch_log(repo) == []


def test_save_state_failure_keeps_previous_state(repo, monkeypatch, capsys):
    state_file = _init(monkeypatch, capsys, {})
    before = state_file.read_text()
    feature_dir = repo / ".feature"
    state = feature_state.load_state(feature_dir, "demo")
    state.current_phase = "plan"

    def broken_dump(obj, fp, **kwargs):
        fp.write('{"name": "de')
        raise OSError("disk full")

    monkeypatch.setattr(feature_state.json, "dump", broken_dump)
    with pytest.raises(OSError):
        feature_state.save_state(feature_dir, state)

    assert state_file.read_text() == before
    assert sorted(p.name for p in state_file.parent.iterdir() if p.is_file()) == ["demo.json"]


def test_save_state_round_trips(repo, monkeypatch, capsys):
    _init(monkeypatch, capsys, {})
    feature_dir = repo / ".feature"
    state = feature_state.load_state(feature_dir, "demo")
    state.current_phase = "plan"
    feature_state.save_state(feature_dir, state)
    assert feature_state.load_state(feature_dir, "demo").current_phase == "plan"


@pytest.mark.parametrize("key", ["retro-topics", "process-topics"])
def test_retro_candidates_matches_agent_topics(repo, monkeypatch, capsys, key):
    l2 = repo / "retro" / "L2"
    l2.mkdir(parents=True)
    (l2 / "concurrency.md").write_text("**Confidence**: HIGH\n**Tags**: go\n\n### Use errgroup [4x]\nprefer errgroup\n")
    agents = repo / "agents"
    agents.mkdir()
    (agents / "go-agent.md").write_text(
        f"---\nname: go-agent\nrouting:\n  {key}:\n    - concurrency\n    - debugging\n---\nbody\n"
    )

    assert _main(monkeypatch, "retro-candidates") == 0
    out = json.loads(capsys.readouterr().out)

    assert out["agent_topic_map"] == {"concurrency": ["go-agent"], "debugging": ["go-agent"]}
    assert out["candidates"][0]["matching_agents"] == ["go-agent"]
