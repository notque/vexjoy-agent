"""Private overlay agents after the agent retirement (plans/009).

The public agents are retired, but private overlay agents still route: the
manifest lists them in an overlay-only AGENTS: section when the request names
their domain, /do and /d may pick one as the worker, and the /d gate accepts
the `overlay-agent` dispatch reason for a live one. Retired names never come
back, even from a stale installed index. Synthetic `quuxcorp-*` names stand in
for real private agents.

Run with: python3 -m pytest scripts/tests/test_overlay_agents.py -v
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))

import d_gate
import routing_index_merge as rim


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    with patch("sys.exit"):
        spec.loader.exec_module(mod)
    return mod


bd = _load(SCRIPTS / "build-dispatch.py", "build_dispatch_overlay")
jev_route = _load(SCRIPTS / "jev-route.py", "jev_route_overlay")
recorder = _load(REPO / "hooks" / "routing-decision-recorder.py", "routing_decision_recorder_overlay")

OVERLAY = "quuxcorp-ops-engineer"
# The real installed index stamps no `owner` on agent items: this is that shape.
AGENTS = {
    OVERLAY: {
        "file": "agents/quuxcorp-ops-engineer.md",
        "short_description": "Specialist in the Quuxcorp ops board:\ndebugging its schedulers.",
        "triggers": ["quuxcorp", "ops board"],
    },
    # Same name as an overlay skill below: both sections list it.
    "quuxcorp-modding": {"file": "agents/quuxcorp-modding.md", "short_description": "Quuxcorp UI mods."},
    # A stale install still lists retired public agents and may list a built-in.
    "golang-general-engineer": {"file": "agents/golang-general-engineer.md", "short_description": "Go."},
    "claude": {"file": "agents/claude.md", "short_description": "Catch-all."},
}
SKILLS = {
    "research": {"description": "Research: gather sources and compare findings.", "triggers": ["research"]},
    "programming": {"description": "Programming in Go, Python, and more.", "triggers": ["golang", "go"]},
    "quuxcorp-modding": {
        "description": "Quuxcorp UI modding.",
        "triggers": ["quuxcorp"],
        "owner": "overlay:synthetic",
    },
}

REQUEST = "why is the quuxcorp ops board scheduler not firing"
INTENT = "Find why the Quuxcorp ops board scheduler does not fire."


@pytest.fixture
def overlay_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    index = tmp_path / "index"
    index.mkdir()
    (index / "skills.json").write_text(json.dumps({"skills": SKILLS}), encoding="utf-8")
    (index / "agents.json").write_text(json.dumps({"agents": AGENTS}), encoding="utf-8")
    monkeypatch.setenv("VEXJOY_INDEX_DIR", str(index))
    return index


@pytest.fixture
def dispatch_index(public_index_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The public skills index plus the synthetic agents index, for build-dispatch."""
    index = tmp_path / "dispatch-index"
    index.mkdir()
    shutil.copy(public_index_dir / "skills.json", index / "skills.json")
    (index / "agents.json").write_text(json.dumps({"agents": AGENTS}), encoding="utf-8")
    monkeypatch.setenv("VEXJOY_INDEX_DIR", str(index))
    return index


def _manifest(cwd: Path, *args: str) -> str:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "routing-manifest.py"), *args],
        capture_output=True,
        text=True,
        env=dict(os.environ),
        cwd=str(cwd),
        check=True,
        timeout=60,
    ).stdout


def _section(manifest: str, header: str, end: str) -> set[str]:
    if header not in manifest:
        return set()
    body = manifest.split(header, 1)[1].split(end, 1)[0]
    return {line.split()[0] for line in body.splitlines() if line.startswith("  ")}


# ------------------------------------------------------------------ the overlay set


def test_overlay_set_is_the_index_minus_retired_and_builtins(overlay_index: Path) -> None:
    names = set(rim.overlay_agent_items())
    assert names == {OVERLAY, "quuxcorp-modding"}


def test_every_reader_uses_the_same_overlay_set(overlay_index: Path) -> None:
    assert jev_route._load_overlay_agents() - jev_route.BUILTIN_AGENTS == {OVERLAY, "quuxcorp-modding"}
    assert bd.load_known_agents() - bd.BUILTIN_AGENTS == {OVERLAY, "quuxcorp-modding"}


# ------------------------------------------------------------------ routing-manifest.py


def test_gated_overlay_agent_renders_first_in_agents(overlay_index: Path, tmp_path: Path) -> None:
    out = _manifest(tmp_path, "--request", REQUEST)
    assert out.startswith("AGENTS:\n")
    assert out.index("AGENTS:") < out.index("SKILLS:") < out.index("PIPELINES:")
    assert _section(out, "AGENTS:", "SKILLS:") == {OVERLAY, "quuxcorp-modding"}
    line = next(ln for ln in out.splitlines() if ln.startswith(f"  {OVERLAY} "))
    assert "debugging its schedulers" in line  # a multi-line description renders on one line


def test_name_collision_lists_the_name_in_both_sections(overlay_index: Path, tmp_path: Path) -> None:
    out = _manifest(tmp_path, "--request", REQUEST)
    assert "quuxcorp-modding" in _section(out, "AGENTS:", "SKILLS:")
    assert "quuxcorp-modding" in _section(out, "SKILLS:", "PIPELINES:")


@pytest.mark.parametrize("flag", ["--compact", "--tiered", None])
def test_every_format_renders_the_agents_section(overlay_index: Path, tmp_path: Path, flag: str | None) -> None:
    args = [flag] if flag else []
    out = _manifest(tmp_path, *args, "--request", REQUEST)
    assert OVERLAY in _section(out, "AGENTS:", "SKILLS:")


@pytest.mark.parametrize(
    "request_text",
    [
        "fix the flaky golang test in pkg/api",
        "ask an engineer to compact the tree",
        "use golang-general-engineer on this",  # names a retired agent literally
        "",
    ],
)
def test_ungated_request_has_no_agents_section(overlay_index: Path, tmp_path: Path, request_text: str) -> None:
    out = _manifest(tmp_path, "--request", request_text)
    assert "AGENTS:" not in out
    assert "golang-general-engineer" not in out


def test_retired_and_builtin_names_never_render(overlay_index: Path, tmp_path: Path) -> None:
    out = _manifest(tmp_path, "--request", f"{REQUEST} with golang-general-engineer and claude")
    agents = _section(out, "AGENTS:", "SKILLS:")
    assert agents == {OVERLAY, "quuxcorp-modding"}
    entries = json.loads(_manifest(tmp_path, "--json", "--request", f"{REQUEST} golang-general-engineer"))
    agent_names = {e["name"] for e in entries if e["type"] == "agent"}
    assert agent_names == {OVERLAY, "quuxcorp-modding"}
    assert not agent_names & rim.RETIRED_AGENTS


def test_no_request_lists_no_agents(overlay_index: Path, tmp_path: Path) -> None:
    """The request-less manifest is the session cache: no private agent goes there."""
    out = _manifest(tmp_path)
    assert "AGENTS:" not in out
    assert all(e["type"] != "agent" for e in json.loads(_manifest(tmp_path, "--json")))


def test_get_routing_manifest_takes_the_generator_path_for_agents(overlay_index: Path, tmp_path: Path) -> None:
    """An agents index that lists agents bypasses the cache when a request is given."""
    home = tmp_path / "home"
    cache = home / ".claude" / "cache"
    cache.mkdir(parents=True)
    (cache / "routing-manifest.txt").write_text("SKILLS:\n  stale\n", encoding="utf-8")
    (cache / "routing-manifest.hash").write_text("x", encoding="utf-8")
    request = tmp_path / "request.txt"
    request.write_text(REQUEST, encoding="utf-8")
    proc = subprocess.run(
        ["bash", str(SCRIPTS / "get-routing-manifest.sh"), "--request-file", str(request)],
        capture_output=True,
        text=True,
        env=dict(os.environ, HOME=str(home)),
        cwd=str(tmp_path),
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert OVERLAY in _section(proc.stdout, "AGENTS:", "SKILLS:")


# ------------------------------------------------------------------ /do build-dispatch


def _do_decision(agent: str) -> dict:
    return {
        "agent": agent,
        "skill": "programming",
        "complexity": "medium",
        "model": "opus",
        "task_spec": {"request_verbatim": REQUEST, "intent": INTENT},
    }


def test_do_dispatch_keeps_an_overlay_agent(dispatch_index: Path) -> None:
    marker = bd.build_marker(_do_decision(OVERLAY))
    assert marker.startswith(f"[do-route] agent={OVERLAY} skill=programming")
    assert "fallback=" not in marker


def test_do_dispatch_coerces_a_retired_agent_from_a_stale_index(dispatch_index: Path) -> None:
    marker = bd.build_marker(_do_decision("golang-general-engineer"))
    assert marker.startswith("[do-route] agent=general-purpose")
    assert "fallback=invalid-agent:golang-general-engineer" in marker


# ------------------------------------------------------------------ /d finalize, gate, build-dispatch


def _receipt() -> None:
    d_gate.write_receipt(REQUEST, INTENT, {"alignment": "aligned", "issues": []}, "proposed")


def _d_decision(agent: str | None, **overrides) -> dict:
    decision = {
        "router": "d",
        "execution": "dispatch",
        "skill": "programming",
        "complexity": "medium",
        "model": "opus",
        "dispatch_reason": "overlay-agent",
        "task_spec": {"request_verbatim": REQUEST, "intent": INTENT},
    }
    if agent is not None:
        decision["agent"] = agent
    decision.update(overrides)
    return decision


def test_check_dispatch_overlay_reason_needs_a_live_overlay_agent() -> None:
    live = frozenset({OVERLAY})
    assert d_gate.check_dispatch(_d_decision(OVERLAY), "opus", live) is None
    assert d_gate.check_dispatch(_d_decision(OVERLAY.upper()), "opus", live) is None
    for agent in (None, "general-purpose", "golang-general-engineer", "quuxcorp-ghost"):
        problem = d_gate.check_dispatch(_d_decision(agent), "opus", live)
        assert problem and "overlay-agent" in problem, agent
    # No overlay set given: the reason never holds.
    assert d_gate.check_dispatch(_d_decision(OVERLAY), "opus")


def test_dispatch_reason_enum_stays_small() -> None:
    assert set(d_gate.DISPATCH_REASONS) == {"fan-out", "worktree", "haiku-gather", "verifier", "overlay-agent"}
    assert {"overlay-agent"} == d_gate.REFERENCES_OPTIONAL_REASONS


def test_finalized_overlay_route_passes_the_d_gate(dispatch_index: Path) -> None:
    """jev-route --finalize keeps the overlay agent; build-dispatch /d dispatches it."""
    entries = [{"name": "programming", "type": "skill"}, {"name": "workflow", "type": "skill"}]
    route = jev_route.finalize(
        {}, {"agent": OVERLAY, "skill": "programming"}, entries, jev_route._load_overlay_agents()
    )
    assert route["agent"] == OVERLAY and route["problems"] == []
    retired = jev_route.finalize(
        {}, {"agent": "golang-general-engineer", "skill": "programming"}, entries, jev_route._load_overlay_agents()
    )
    assert retired["agent"] == "general-purpose"

    _receipt()
    out = bd.build_preamble(_d_decision(route["agent"]), gather=False)
    marker = out.splitlines()[0]
    assert marker.startswith(f"[do-route] agent={OVERLAY} skill=programming")
    assert marker.endswith(" reason=overlay-agent router=d")
    assert recorder.parse_dispatch_reason(marker) == "overlay-agent"
    assert recorder.parse_router(marker) == "d"


def test_d_gate_refuses_overlay_reason_for_a_non_overlay_worker(dispatch_index: Path) -> None:
    _receipt()
    for agent in ("general-purpose", "golang-general-engineer", None):
        with pytest.raises(bd.InputError, match="overlay-agent"):
            bd.build_preamble(_d_decision(agent), gather=False)


def test_overlay_reason_still_validates_given_references(dispatch_index: Path) -> None:
    _receipt()
    with pytest.raises(bd.InputError, match="not a file"):
        bd.build_preamble(_d_decision(OVERLAY, references=["no-such-reference.md"]), gather=False)
