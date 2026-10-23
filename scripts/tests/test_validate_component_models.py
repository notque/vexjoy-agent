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


def test_sonnet_and_opus_are_allowed(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    agents_dir = repo / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "demo-agent.md").write_text("---\nmodel: opus\n---\n", encoding="utf-8")
    skill_dir = repo / "skills" / "demo" / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nmodel: sonnet\n---\n", encoding="utf-8")
    workflow_dir = repo / "skills" / "process" / "workflow" / "references"
    workflow_dir.mkdir(parents=True)
    (workflow_dir / "demo-pipeline.md").write_text("---\nmodel: sonnet\n---\n", encoding="utf-8")

    original_root = _mod.REPO_ROOT
    _mod.REPO_ROOT = repo
    try:
        violations = _mod.validate_models()
    finally:
        _mod.REPO_ROOT = original_root

    assert violations == []


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
