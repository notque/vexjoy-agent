"""Runtime index readers go through routing_index_merge (installer spec 7.2).

Covers list-capabilities.py, build-dispatch.py, and pre-route.py ``_ensure_index``:
installed index first ($VEXJOY_INDEX_DIR here), repo index fallback otherwise.
No test reads the real HOME: the conftest pins VEXJOY_INDEX_DIR to a missing
dir, and tests that want an installed index point it at a tmp dir.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]


def _load(filename: str, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    with patch("sys.exit"):
        spec.loader.exec_module(mod)
    return mod


def _w(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture
def installed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An installed index dir with one skill and one agent unknown to the repo."""
    index_dir = tmp_path / "installed"
    _w(index_dir / "skills.json", {"generated": "2026-01-01T00:00:00Z", "skills": {"inst-skill": {"file": "x"}}})
    _w(index_dir / "agents.json", {"agents": {"inst-agent": {"file": "agents/inst-agent.md"}}})
    monkeypatch.setenv("VEXJOY_INDEX_DIR", str(index_dir))
    return index_dir


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    _w(repo / "skills" / "INDEX.json", {"skills": {"repo-skill": {"file": "skills/c/repo-skill/SKILL.md"}}})
    _w(repo / "skills" / "INDEX.local.json", {"skills": {"legacy-skill": {"file": "y"}}})
    _w(repo / "agents" / "INDEX.json", {"agents": {"repo-agent": {"file": "agents/repo-agent.md"}}})
    return repo


# --------------------------------------------------------------------------- list-capabilities


def test_list_capabilities_prefers_installed_index(installed: Path) -> None:
    lc = _load("list-capabilities.py", "lc_installed")
    skills, generated = lc.load_skills_index()
    agents, _ = lc.load_agents_index()
    assert set(skills) == {"inst-skill"}
    assert generated == "2026-01-01T00:00:00Z"
    assert set(agents) == {"inst-agent"}
    assert lc.resolved_index_path("skills") == installed / "skills.json"


def test_list_capabilities_falls_back_to_repo_index(fake_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lc = _load("list-capabilities.py", "lc_fallback")
    monkeypatch.setattr(lc, "REPO_ROOT", fake_repo)
    skills, _ = lc.load_skills_index()
    agents, _ = lc.load_agents_index()
    assert set(skills) == {"repo-skill", "legacy-skill"}
    assert set(agents) == {"repo-agent"}


def test_list_capabilities_staleness_message_handles_installed_path(installed: Path) -> None:
    lc = _load("list-capabilities.py", "lc_display")
    assert lc._display(installed / "skills.json") == str(installed / "skills.json")


# --------------------------------------------------------------------------- build-dispatch


def test_build_dispatch_default_reads_installed_index(installed: Path) -> None:
    bd = _load("build-dispatch.py", "bd_installed")
    assert "inst-agent" in bd.load_known_agents()
    assert "general-purpose" in bd.load_known_agents()
    assert bd.load_known_skills() == frozenset({"inst-skill"})


def test_build_dispatch_falls_back_to_deploy_dir_index(fake_repo: Path) -> None:
    bd = _load("build-dispatch.py", "bd_fallback")
    tracked = fake_repo / "skills" / "INDEX.json"
    assert bd._resolved_source("skills", tracked, "INDEX.local.json") == (tracked, "INDEX.local.json")
    assert bd.load_known_skills(tracked) == frozenset({"repo-skill", "legacy-skill"})


def test_build_dispatch_explicit_missing_index_fails_open(tmp_path: Path, installed: Path) -> None:
    bd = _load("build-dispatch.py", "bd_explicit")
    assert bd.load_known_agents(tmp_path / "nope.json") == frozenset()


# --------------------------------------------------------------------------- pre-route _ensure_index


def test_ensure_index_skips_regeneration_when_installed_index_exists(installed: Path, tmp_path: Path) -> None:
    pr = _load("pre-route.py", "pr_installed")
    with patch.object(pr.subprocess, "run") as run:
        pr._ensure_index("skills", tmp_path / "missing" / "INDEX.json")
    run.assert_not_called()


def test_ensure_index_regenerates_without_installed_index(tmp_path: Path) -> None:
    pr = _load("pre-route.py", "pr_fallback")
    with patch.object(pr.subprocess, "run") as run:
        pr._ensure_index("skills", tmp_path / "missing" / "INDEX.json")
    run.assert_called_once()
