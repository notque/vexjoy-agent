from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "validate_component_models",
    _SCRIPTS_DIR / "validate_component_models.py",
)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
sys.modules["validate_component_models"] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[attr-defined]


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "agents").mkdir(parents=True)
    (repo / "skills" / "process" / "workflow" / "references").mkdir(parents=True)
    return repo


def _agent(repo: Path, name: str, frontmatter: str) -> None:
    (repo / "agents" / f"{name}.md").write_text(f"---\nname: {name}\n{frontmatter}---\n", encoding="utf-8")


def _flagged(repo: Path, monkeypatch) -> dict[str, str]:
    monkeypatch.setattr(_mod, "REPO_ROOT", repo)
    return {v.component: v.issue for v in _mod.validate_models()}


def test_haiku_skill_is_flagged(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    skill_dir = repo / "skills" / "demo" / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nmodel: haiku\n---\n", encoding="utf-8")
    (repo / "agents").mkdir(parents=True)
    (repo / "skills" / "process" / "workflow" / "references").mkdir(parents=True)

    original_root = _mod.REPO_ROOT
    _mod.REPO_ROOT = repo
    try:
        violations = _mod.validate_models()
    finally:
        _mod.REPO_ROOT = original_root

    assert len(violations) == 1
    assert violations[0].component == "demo-skill"


def test_do_skill_is_exempt(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    do_dir = repo / "skills" / "meta" / "do"
    do_dir.mkdir(parents=True)
    (do_dir / "SKILL.md").write_text("---\nmodel: haiku\n---\n", encoding="utf-8")
    (repo / "agents").mkdir(parents=True)
    (repo / "skills" / "process" / "workflow" / "references").mkdir(parents=True)

    original_root = _mod.REPO_ROOT
    _mod.REPO_ROOT = repo
    try:
        violations = _mod.validate_models()
    finally:
        _mod.REPO_ROOT = original_root

    assert violations == []


def test_opus_and_inherit_are_allowed(tmp_path: Path, monkeypatch) -> None:
    repo = _make_repo(tmp_path)
    _agent(repo, "demo-agent", "model: opus\n")
    skill_dir = repo / "skills" / "demo" / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nmodel: inherit\n---\n", encoding="utf-8")
    workflow_dir = repo / "skills" / "process" / "workflow" / "references"
    (workflow_dir / "demo-pipeline.md").write_text("---\nmodel: opus\n---\n", encoding="utf-8")

    assert _flagged(repo, monkeypatch) == {}


def test_sonnet_is_flagged_everywhere(tmp_path: Path, monkeypatch) -> None:
    # Owner policy 2026-11-01: Sonnet is no task's default, in any component class.
    repo = _make_repo(tmp_path)
    _agent(repo, "demo-agent", "model: sonnet\n")
    skill_dir = repo / "skills" / "demo" / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nmodel: sonnet\n---\n", encoding="utf-8")
    workflow_dir = repo / "skills" / "process" / "workflow" / "references"
    (workflow_dir / "demo-pipeline.md").write_text("---\nmodel: sonnet\n---\n", encoding="utf-8")

    flagged = _flagged(repo, monkeypatch)

    assert set(flagged) == {"demo-agent", "demo-skill", "demo-pipeline"}
    assert all("sonnet" in issue for issue in flagged.values())


def test_haiku_is_allowed_on_a_read_only_agent(tmp_path: Path, monkeypatch) -> None:
    repo = _make_repo(tmp_path)
    _agent(repo, "scout-csv", "model: haiku\ntools: Read, Grep, Glob, WebFetch\n")
    _agent(repo, "scout-list", "model: haiku\ntools:\n  - Read\n  - Grep\n  - WebSearch\n")

    assert _flagged(repo, monkeypatch) == {}


def test_haiku_is_flagged_when_only_allowed_tools_lists_read_only_tools(tmp_path: Path, monkeypatch) -> None:
    # Claude Code ignores allowed-tools on agents and treats it as a grant on skills,
    # so a read-only allowed-tools list leaves Edit, Write, and Bash available.
    repo = _make_repo(tmp_path)
    _agent(repo, "scout-advisory", "model: haiku\nallowed-tools:\n  - Read\n  - Grep\n  - WebSearch\n")
    skill_dir = repo / "skills" / "demo" / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nmodel: haiku\nallowed-tools: Read, Grep\n---\n", encoding="utf-8")

    flagged = _flagged(repo, monkeypatch)

    assert set(flagged) == {"scout-advisory", "demo-skill"}
    assert all("allowed-tools" in issue for issue in flagged.values())


def test_haiku_is_flagged_on_an_agent_that_can_write(tmp_path: Path, monkeypatch) -> None:
    repo = _make_repo(tmp_path)
    _agent(repo, "editor", "model: haiku\ntools: Read, Edit\n")
    _agent(repo, "writer", "model: haiku\ntools:\n  - Read\n  - Write\n")
    _agent(repo, "shell", "model: haiku\ntools: Read, Bash(git diff:*)\n")
    _agent(repo, "notebook", "model: haiku\ntools: [Read, NotebookEdit]\n")
    # A subagent started through Agent or Task can write, so those count too.
    _agent(repo, "delegator", "model: haiku\ntools: Read, Agent\n")
    _agent(repo, "tasker", "model: haiku\ntools: Read, Task\n")

    flagged = _flagged(repo, monkeypatch)

    assert set(flagged) == {"editor", "writer", "shell", "notebook", "delegator", "tasker"}
    assert "read-only" in flagged["editor"]
    assert "Agent" in flagged["delegator"]


def test_haiku_is_flagged_when_no_tool_list_limits_the_agent(tmp_path: Path, monkeypatch) -> None:
    # No tools list means the agent inherits every tool, including Edit and Write.
    repo = _make_repo(tmp_path)
    _agent(repo, "inherits-all", "model: haiku\n")

    assert set(_flagged(repo, monkeypatch)) == {"inherits-all"}


def test_unknown_model_is_flagged(tmp_path: Path, monkeypatch) -> None:
    repo = _make_repo(tmp_path)
    _agent(repo, "odd", "model: gpt-4o\n")

    assert set(_flagged(repo, monkeypatch)) == {"odd"}


def test_exempt_component_may_pin_any_model(tmp_path: Path, monkeypatch) -> None:
    repo = _make_repo(tmp_path)
    _agent(repo, "legacy", "model: sonnet\n")
    monkeypatch.setattr(_mod, "EXEMPT_COMPONENTS", {("agent", "legacy")})

    assert _flagged(repo, monkeypatch) == {}


def test_image_gen_skill_is_exempt(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    skill_dir = repo / "skills" / "content" / "image-gen"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nmodel: gemini-3-pro-image-preview\n---\n", encoding="utf-8")

    original_root = _mod.REPO_ROOT
    _mod.REPO_ROOT = repo
    try:
        violations = _mod.validate_models()
    finally:
        _mod.REPO_ROOT = original_root

    assert violations == []


def test_main_fails_when_a_target_class_finds_no_files(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    (repo / "agents").mkdir(parents=True)
    (repo / "skills").mkdir()
    monkeypatch.setattr(_mod, "REPO_ROOT", repo)
    monkeypatch.setattr(sys, "argv", ["validate_component_models.py"])

    assert _mod.main() == 2
