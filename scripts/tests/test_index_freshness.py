"""Tests for scripts/lib/index_freshness.py: regenerate a missing or stale generated index."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parent.parent / "lib"))

import index_freshness as fresh

OLD = (1_000_000_000, 1_000_000_000)

_GENERATOR = (
    "from pathlib import Path\n"
    "Path('{surface}').mkdir(exist_ok=True)\n"
    "Path('{surface}/INDEX.json').write_text('{{\"{surface}\": {{\"regenerated\": {{}}}}}}')\n"
)


def make_repo(tmp_path: Path, *, generators: bool = True) -> Path:
    """A repo with one skill, one agent, both indexes current, and stub generators."""
    repo = tmp_path / "repo"
    skill = repo / "skills" / "meta" / "one"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: one\n---\n", encoding="utf-8")
    (repo / "agents").mkdir()
    (repo / "agents" / "a.md").write_text("---\nname: a\n---\n", encoding="utf-8")
    (repo / "scripts").mkdir()
    if generators:
        for surface, name in (("skills", "generate-skill-index.py"), ("agents", "generate-agent-index.py")):
            (repo / "scripts" / name).write_text(_GENERATOR.format(surface=surface), encoding="utf-8")
    for path in sorted(repo.rglob("*")):
        os.utime(path, OLD)
    for surface in fresh.SURFACES:
        (repo / surface / "INDEX.json").write_text(f'{{"{surface}": {{"original": {{}}}}}}', encoding="utf-8")
        os.utime(repo / surface, OLD)
    return repo


def index_text(repo: Path, surface: str) -> str:
    return (repo / surface / "INDEX.json").read_text(encoding="utf-8")


def test_current_indexes_are_left_alone(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)

    assert fresh.ensure_fresh_indexes(repo) == []
    assert "original" in index_text(repo, "skills")
    assert "original" in index_text(repo, "agents")


def test_missing_index_is_generated(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    (repo / "agents" / "INDEX.json").unlink()

    assert fresh.ensure_fresh_indexes(repo) == ["agents"]
    assert "regenerated" in index_text(repo, "agents")
    assert "original" in index_text(repo, "skills")


def test_edited_skill_makes_the_skills_index_stale(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    os.utime(repo / "skills" / "INDEX.json", (OLD[0] + 10, OLD[1] + 10))
    os.utime(repo / "skills" / "meta" / "one" / "SKILL.md", (OLD[0] + 20, OLD[1] + 20))

    assert fresh.ensure_fresh_indexes(repo) == ["skills"]
    assert "regenerated" in index_text(repo, "skills")


def test_removed_agent_makes_the_agents_index_stale(tmp_path: Path) -> None:
    """Deleting a component changes only its directory's mtime."""
    repo = make_repo(tmp_path)
    os.utime(repo / "agents" / "INDEX.json", (OLD[0] + 10, OLD[1] + 10))
    (repo / "agents" / "a.md").unlink()

    assert fresh.newer_source(repo, "agents") == repo / "agents"
    assert fresh.ensure_fresh_indexes(repo, ["agents"]) == ["agents"]


def test_changed_generator_makes_the_index_stale(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    os.utime(repo / "skills" / "INDEX.json", (OLD[0] + 10, OLD[1] + 10))
    os.utime(repo / "scripts" / "generate-skill-index.py", (OLD[0] + 20, OLD[1] + 20))

    assert fresh.ensure_fresh_indexes(repo, ["skills"]) == ["skills"]


def test_missing_index_without_generator_raises(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, generators=False)
    (repo / "skills" / "INDEX.json").unlink()

    with pytest.raises(RuntimeError, match="cannot be generated"):
        fresh.ensure_fresh_indexes(repo)


def test_stale_index_without_generator_is_kept(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, generators=False)
    os.utime(repo / "skills" / "INDEX.json", (OLD[0] - 10, OLD[1] - 10))

    assert fresh.ensure_fresh_indexes(repo) == []
    assert "original" in index_text(repo, "skills")


def test_failing_generator_raises_with_its_stderr(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    (repo / "agents" / "INDEX.json").unlink()
    (repo / "scripts" / "generate-agent-index.py").write_text(
        "import sys\nprint('boom', file=sys.stderr)\nsys.exit(3)\n", encoding="utf-8"
    )

    with pytest.raises(RuntimeError, match=r"exited 3: boom"):
        fresh.ensure_fresh_indexes(repo, ["agents"])


def test_generator_that_writes_nothing_raises_when_index_is_missing(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    (repo / "skills" / "INDEX.json").unlink()
    (repo / "scripts" / "generate-skill-index.py").write_text("pass\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="did not create required index"):
        fresh.ensure_fresh_indexes(repo, ["skills"])
