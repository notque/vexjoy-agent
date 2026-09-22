"""Tests for routing_index_merge.resolve_index (installer spec 7.2) and its readers.

Resolution order: $VEXJOY_INDEX_DIR -> ~/.<target>/vexjoy/index/<kind>.json ->
repo public index (plus legacy INDEX.local.json, for backward compatibility).
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
ROUTING_MODULES = ["routing-manifest", "pre-route", "index-router"]


@pytest.fixture
def merge(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.syspath_prepend(str(SCRIPTS_DIR))
    return importlib.import_module("routing_index_merge")


def _w(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture
def layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """(home, repo) with a repo public index, a legacy local, and no installed index."""
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    _w(repo / "skills" / "INDEX.json", {"skills": {"pub": {"file": "skills/c/pub/SKILL.md"}}})
    _w(repo / "skills" / "INDEX.local.json", {"skills": {"legacy": {"file": "skills/legacy/SKILL.md"}}})
    monkeypatch.delenv("VEXJOY_INDEX_DIR", raising=False)
    monkeypatch.setenv("HOME", str(home))
    return home, repo


def test_repo_fallback_keeps_legacy_local(merge, layout) -> None:
    home, repo = layout
    path = merge.resolve_index("skills", "claude", repo_root=repo, home=home)
    assert path == repo / "skills" / "INDEX.json"
    items = merge.load_resolved_items("skills", "claude", repo_root=repo, home=home)
    assert set(items) == {"pub", "legacy"}


def test_installed_index_wins_over_repo(merge, layout) -> None:
    home, repo = layout
    installed = _w(home / ".claude" / "vexjoy" / "index" / "skills.json", {"skills": {"inst": {"file": "x"}}})
    assert merge.resolve_index("skills", "claude", repo_root=repo, home=home) == installed
    items = merge.load_resolved_items("skills", "claude", repo_root=repo, home=home)
    assert set(items) == {"inst"}, "installed index is authoritative; no legacy overlay"


def test_target_selects_runtime_dir(merge, layout) -> None:
    home, repo = layout
    _w(home / ".claude" / "vexjoy" / "index" / "skills.json", {"skills": {"c": {}}})
    codex = _w(home / ".codex" / "vexjoy" / "index" / "skills.json", {"skills": {"x": {}}})
    assert merge.resolve_index("skills", "codex", repo_root=repo, home=home) == codex
    path, base, installed = merge.resolve_index_with_base("skills", "codex", repo_root=repo, home=home)
    assert (path, base, installed) == (codex, home / ".codex", True)


def test_empty_installed_index_falls_back(merge, layout) -> None:
    """An installed index with no items never hides the repo catalog."""
    home, repo = layout
    _w(home / ".claude" / "vexjoy" / "index" / "skills.json", {"skills": {}})
    assert merge.resolve_index("skills", "claude", repo_root=repo, home=home) == repo / "skills" / "INDEX.json"


def test_env_dir_first(merge, layout, tmp_path, monkeypatch) -> None:
    home, repo = layout
    _w(home / ".claude" / "vexjoy" / "index" / "skills.json", {"skills": {"inst": {}}})
    env_dir = tmp_path / "envidx"
    envfile = _w(env_dir / "skills.json", {"skills": {"env": {}}})
    monkeypatch.setenv("VEXJOY_INDEX_DIR", str(env_dir))
    assert merge.resolve_index("skills", "claude", repo_root=repo, home=home) == envfile


def test_env_dir_missing_pins_repo(merge, layout, tmp_path, monkeypatch) -> None:
    home, repo = layout
    _w(home / ".claude" / "vexjoy" / "index" / "skills.json", {"skills": {"inst": {}}})
    monkeypatch.setenv("VEXJOY_INDEX_DIR", str(tmp_path / "absent"))
    assert merge.resolve_index("skills", "claude", repo_root=repo, home=home) == repo / "skills" / "INDEX.json"


def test_detect_target(merge, monkeypatch) -> None:
    monkeypatch.delenv("VEXJOY_INDEX_TARGET", raising=False)
    assert merge.detect_target("/home/u/.codex/scripts/routing-manifest.py") == "codex"
    assert merge.detect_target("/home/u/.claude/scripts/x.py") == "claude"
    assert merge.detect_target("/repo/scripts/x.py") == "claude"
    monkeypatch.setenv("VEXJOY_INDEX_TARGET", "hermes")
    assert merge.detect_target("/home/u/.codex/scripts/x.py") == "hermes"


def test_pipelines_bypass_resolution(merge, layout, tmp_path) -> None:
    home, repo = layout
    pipe = _w(tmp_path / "pipeline-index.json", {"pipelines": {"p": {}}})
    assert set(merge.load_items_for("pipelines", pipe, None, "claude", repo)) == {"p"}


def test_readers_use_resolver(monkeypatch, tmp_path) -> None:
    """All three routing readers load skills through load_items_for."""
    monkeypatch.syspath_prepend(str(SCRIPTS_DIR))
    env_dir = tmp_path / "idx"
    _w(env_dir / "skills.json", {"skills": {"only-installed": {"triggers": ["zzq unique trigger"]}}})
    _w(env_dir / "agents.json", {"agents": {}})
    monkeypatch.setenv("VEXJOY_INDEX_DIR", str(env_dir))
    merge_mod = importlib.import_module("routing_index_merge")
    for name in ROUTING_MODULES:
        mod = importlib.import_module(name)
        assert mod._load_items_for is merge_mod.load_items_for, name
    rm = importlib.import_module("routing-manifest")
    names = {e["name"] for e in rm.load_entries()}
    assert "only-installed" in names


def test_codex_manifest_uses_resolver(tmp_path, monkeypatch) -> None:
    """codex-skill-manifest: installed codex index names, mapped back to repo sources."""
    repo = tmp_path / "repo"
    (repo / "skills" / "c" / "pub").mkdir(parents=True)
    (repo / "skills" / "c" / "pub" / "SKILL.md").write_text("---\nname: pub\n---\n")
    (repo / "skills" / "c" / "leaf").mkdir(parents=True)
    (repo / "skills" / "c" / "leaf" / "SKILL.md").write_text("---\nname: leaf\n---\n")
    _w(repo / "skills" / "INDEX.json", {"skills": {"pub": {"file": "skills/c/pub/SKILL.md"}}})
    home = tmp_path / "home"
    # Installed codex index: flat runtime paths (copies), unresolvable into the repo.
    (home / ".codex" / "skills" / "pub").mkdir(parents=True)
    (home / ".codex" / "skills" / "pub" / "SKILL.md").write_text("copy\n")
    _w(home / ".codex" / "vexjoy" / "index" / "skills.json", {"skills": {"pub": {"file": "skills/pub/SKILL.md"}}})
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin"}
    out = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "codex-skill-manifest.py"), "--source", str(repo / "skills")],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    ).stdout
    assert out.strip() == f"pub\t{(repo / 'skills' / 'c' / 'pub').resolve()}"
    assert "leaf" not in out
