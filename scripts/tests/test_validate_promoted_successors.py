#!/usr/bin/env python3
"""Tests for scripts/validate-promoted-successors.py.

Contract under test: ``promoted_to`` retires a skill by removing it from
skills/INDEX.json, so both ways the tag can lie must fail.

P1 catches a successor that names nothing on disk — the husk is retired into
a void, which is how /do left the skill catalogue (promoted_to: native-router).
P2 catches a husk that still advertises ``user-invocable: true`` while the
index no longer carries it.

Run with: python3 -m pytest scripts/tests/test_validate_promoted_successors.py -v
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "validate-promoted-successors.py"

_spec = importlib.util.spec_from_file_location("validate_promoted_successors", SCRIPT)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

check = _mod.check


def _make_skill(
    repo_root: Path,
    category: str,
    name: str,
    promoted_to: str | None = None,
    user_invocable: bool | None = None,
) -> None:
    """Write a fixture SKILL.md carrying the frontmatter this validator reads."""
    lines = ["---", f"name: {name}", 'description: "fixture"']
    if promoted_to is not None:
        lines.append(f"promoted_to: {promoted_to}")
    if user_invocable is not None:
        lines.append(f"user-invocable: {str(user_invocable).lower()}")
    lines += ["---", "body", ""]
    skill_dir = repo_root / "skills" / category / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("\n".join(lines), encoding="utf-8")


def test_untagged_skill_is_ignored(tmp_path: Path) -> None:
    """A skill with no promoted_to is outside this validator's scope."""
    _make_skill(tmp_path, "meta", "plain-skill")
    assert check(tmp_path) == []


def test_resolving_successor_passes(tmp_path: Path) -> None:
    """A husk pointing at a real skill on disk is a clean retirement."""
    _make_skill(tmp_path, "meta", "umbrella")
    _make_skill(tmp_path, "meta", "husk", promoted_to="umbrella", user_invocable=False)
    assert check(tmp_path) == []


def test_phantom_successor_fails(tmp_path: Path) -> None:
    """P1: a successor that exists nowhere retires the skill into nothing."""
    _make_skill(tmp_path, "meta", "husk", promoted_to="native-router", user_invocable=False)
    failures = check(tmp_path)
    assert len(failures) == 1
    assert "P1 PHANTOM-SUCCESSOR" in failures[0]
    assert "skills/meta/husk/SKILL.md" in failures[0]
    assert "native-router" in failures[0]


def test_user_invocable_husk_fails(tmp_path: Path) -> None:
    """P2: an excluded skill that still advertises a user entry point."""
    _make_skill(tmp_path, "meta", "umbrella")
    _make_skill(tmp_path, "meta", "husk", promoted_to="umbrella", user_invocable=True)
    failures = check(tmp_path)
    assert len(failures) == 1
    assert "P2 INVOCABLE-EXCLUDED" in failures[0]
    assert "skills/meta/husk/SKILL.md" in failures[0]


def test_both_failures_report_together(tmp_path: Path) -> None:
    """The live /do shape: phantom successor on a user-invocable skill."""
    _make_skill(tmp_path, "meta", "do", promoted_to="native-router", user_invocable=True)
    failures = check(tmp_path)
    assert len(failures) == 2
    assert any("P1 PHANTOM-SUCCESSOR" in f for f in failures)
    assert any("P2 INVOCABLE-EXCLUDED" in f for f in failures)


def test_flat_layout_successor_resolves(tmp_path: Path) -> None:
    """Successors resolve in the flat skills/<name>/ layout too (skills/workflow)."""
    flat = tmp_path / "skills" / "workflow"
    flat.mkdir(parents=True)
    (flat / "SKILL.md").write_text('---\nname: workflow\ndescription: "fixture"\n---\nbody\n', encoding="utf-8")
    _make_skill(tmp_path, "meta", "husk", promoted_to="workflow", user_invocable=False)
    assert check(tmp_path) == []


def _write(repo_root: Path, rel: str, text: str) -> None:
    path = repo_root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Keep successor resolution off the real ~/.claude and ~/private-skills."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))  # Path.home() reads $HOME on POSIX
    return home


@pytest.mark.usefixtures("isolated_home")
def test_live_file_calling_a_husk_script_fails(tmp_path: Path) -> None:
    """P3: the installer skips husks, so a live caller of a husk asset breaks."""
    _make_skill(tmp_path, "meta", "umbrella")
    _make_skill(tmp_path, "meta", "husk", promoted_to="umbrella", user_invocable=False)
    _write(tmp_path, "skills/meta/husk/scripts/tool.py", "print('hi')\n")
    _write(
        tmp_path,
        "skills/meta/umbrella/references/use.md",
        "Run `python3 skills/meta/husk/scripts/tool.py` first.\n",
    )
    failures = check(tmp_path)
    assert len(failures) == 1
    assert "P3 HUSK-ASSET-REFERENCED" in failures[0]
    assert "skills/meta/umbrella/references/use.md:1" in failures[0]
    assert "skills/meta/husk/" in failures[0]


@pytest.mark.usefixtures("isolated_home")
def test_installed_path_into_a_husk_fails(tmp_path: Path) -> None:
    """P3: ~/.claude/skills/<husk> never exists, flat or under a category."""
    _make_skill(tmp_path, "meta", "umbrella")
    _make_skill(tmp_path, "meta", "husk", promoted_to="umbrella", user_invocable=False)
    _write(
        tmp_path,
        "agents/helper.md",
        "cd ~/.claude/skills/husk\npython3 ~/.claude/skills/meta/husk/scripts/tool.py\n",
    )
    failures = check(tmp_path)
    assert [f for f in failures if "P3 HUSK-ASSET-REFERENCED" in f] == failures
    assert len(failures) == 2


@pytest.mark.usefixtures("isolated_home")
def test_husk_may_reference_itself_and_live_paths_pass(tmp_path: Path) -> None:
    """A husk's own files are inert, and paths into live skills are fine."""
    _make_skill(tmp_path, "meta", "umbrella")
    _make_skill(tmp_path, "meta", "husk", promoted_to="umbrella", user_invocable=False)
    _write(tmp_path, "skills/meta/husk/notes.md", "See `skills/meta/husk/scripts/tool.py`.\n")
    _write(
        tmp_path,
        "skills/meta/umbrella/references/use.md",
        "Run `python3 ~/.claude/skills/umbrella/scripts/tool.py` (moved out of the husk skill).\n",
    )
    _write(tmp_path, "scripts/tests/test_tool.py", "PATH = 'skills/meta/husk/scripts/tool.py'\n")
    assert check(tmp_path) == []


def test_indexed_successor_resolves(tmp_path: Path) -> None:
    """A successor present only in the merged index still counts as real."""
    (tmp_path / "skills").mkdir(parents=True, exist_ok=True)
    (tmp_path / "skills" / "INDEX.local.json").write_text(
        '{"skills": {"private-umbrella": {"file": "skills/private/private-umbrella/SKILL.md"}}}',
        encoding="utf-8",
    )
    _make_skill(tmp_path, "meta", "husk", promoted_to="private-umbrella", user_invocable=False)
    assert check(tmp_path) == []
