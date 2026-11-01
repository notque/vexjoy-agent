"""vexinstall cline target: adapter fields, auto-discovery, layout, idempotency."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from vexinstall.adapters import resolve_targets

from scripts.tests.vexinstall_support import ADAPTERS, Env, expected_skill_names, world

MODES = ("symlink", "copy")
SUPPORT_DIRS = ("shared-patterns", "kb", "voice-shared")


def _ok(res) -> None:
    assert res.code == 0, f"exit {res.code}\nout={res.out}\nerr={res.err}"


# ---------------------------------------------------------------------------
# 1. Adapter fields
# ---------------------------------------------------------------------------


def test_cline_adapter_fields() -> None:
    adapter = ADAPTERS["cline"]
    assert adapter.name == "cline"
    assert adapter.root == ".cline"
    assert adapter.skills == "skills"
    assert adapter.no_support is True
    assert adapter.agents is None
    assert adapter.commands is None
    assert adapter.hooks is None
    assert adapter.scripts is None
    assert adapter.settings is False


# ---------------------------------------------------------------------------
# 2. Auto-discovery via resolve_targets
# ---------------------------------------------------------------------------


def test_resolve_targets_includes_cline_when_dir_exists(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / ".cline").mkdir()
    result = resolve_targets("all", home)
    assert "cline" in result


def test_resolve_targets_excludes_cline_when_dir_absent(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    result = resolve_targets("all", home)
    assert "cline" not in result


# ---------------------------------------------------------------------------
# 3. Skills land under skills/ subdir; no support dirs installed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mode", MODES)
def test_cline_skills_land_in_skills_subdir(world: Env, mode: str) -> None:
    _ok(world.run("apply", "--target", "cline", "--mode", mode))

    root = world.root("cline")
    assert root.is_dir() and not root.is_symlink()

    # skills/ subdir must exist — Cline loads from ~/.cline/skills/<name>/
    skills = root / "skills"
    assert skills.is_dir() and not skills.is_symlink()

    # every expected skill name sits directly under skills/
    expected = expected_skill_names("cline")
    installed = {p for p in os.listdir(skills) if not p.startswith(".")}
    assert expected <= installed, f"missing: {expected - installed}"

    # support dirs must NOT be installed — cline ignores dirs without SKILL.md
    for name in SUPPORT_DIRS:
        assert not (skills / name).exists(), f"support dir {name!r} must not be installed for cline"

    # spot-check one public skill
    alpha = skills / "alpha"
    assert alpha.exists(), "alpha not installed"
    assert (alpha / "SKILL.md").is_file(), "alpha/SKILL.md missing"

    # mode-specific link/copy assertion
    if mode == "symlink":
        assert alpha.is_symlink(), "alpha should be a symlink in symlink mode"
    else:
        assert alpha.is_dir() and not alpha.is_symlink(), "alpha should be a real dir in copy mode"


# ---------------------------------------------------------------------------
# 4. No agents / commands / hooks / scripts
# ---------------------------------------------------------------------------


def test_cline_no_agents_commands_hooks(world: Env) -> None:
    _ok(world.run("apply", "--target", "cline", "--mode", "symlink"))

    root = world.root("cline")
    assert not (root / "agents").exists(), "agents must not be installed for cline"
    assert not (root / "commands").exists(), "commands must not be installed for cline"
    assert not (root / "hooks").exists(), "hooks must not be installed for cline"
    assert not (root / "scripts").exists(), "scripts must not be installed for cline"


# ---------------------------------------------------------------------------
# 5. Idempotency
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mode", MODES)
def test_cline_apply_is_idempotent(world: Env, mode: str) -> None:
    _ok(world.run("apply", "--target", "cline", "--mode", mode))
    second = world.run("apply", "--target", "cline", "--mode", mode)
    _ok(second)
    assert second.out[0].startswith("[apply] cline: +0 ~0 -0,"), second.out[0]
