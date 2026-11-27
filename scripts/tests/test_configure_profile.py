"""Tests for scripts/configure-profile.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "configure-profile.py"


def _load_mod():
    spec = importlib.util.spec_from_file_location("configure_profile", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_list_skills_scans_nested_category_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_mod()
    skills = tmp_path / "skills"
    (skills / "meta" / "alpha").mkdir(parents=True)
    (skills / "meta" / "alpha" / "SKILL.md").write_text("---\nname: alpha\n---\n", encoding="utf-8")
    (skills / "process" / "beta").mkdir(parents=True)
    (skills / "process" / "beta" / "SKILL.md").write_text("---\nname: beta\n---\n", encoding="utf-8")
    # Support and data dirs without real skills must not appear
    (skills / "shared-patterns").mkdir(parents=True)
    (skills / "shared-patterns" / "notes.md").write_text("# notes\n", encoding="utf-8")
    (skills / "reddit-data" / "sub").mkdir(parents=True)
    (skills / "reddit-data" / "sub" / "SKILL.md").write_text("# ignored\n", encoding="utf-8")
    # Empty category dir with no SKILL.md
    (skills / "empty-cat" / "not-a-skill").mkdir(parents=True)

    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
    assert mod.list_skills() == ["alpha", "beta"]


def test_list_skills_on_real_repo_matches_vexinstall_public() -> None:
    import sys

    mod = _load_mod()
    scripts_dir = str(REPO_ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from vexinstall.sources import load_public

    expected = sorted({s.name for s in load_public(REPO_ROOT).skills})
    found = mod.list_skills()
    assert found == expected
    assert len(found) > 0


def test_profile_header_omits_nonexistent_non_interactive_flag() -> None:
    mod = _load_mod()
    assert "--non-interactive" not in mod.PROFILE_HEADER


def test_plain_prompts_and_write_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    mod = _load_mod()
    answers = iter(["beta, unknown-skill", "", "h1.py"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    disabled = mod.run_plain_prompts(["alpha", "beta"], ["eng"], ["h1.py", "h2.py"])
    assert disabled == {"skills": ["beta"], "agents": [], "hooks": ["h1.py"]}
    err = capsys.readouterr().err
    assert "unknown-skill" in err

    out_path = tmp_path / ".local" / "profile.yaml"
    mod.write_profile(out_path, disabled)
    text = out_path.read_text(encoding="utf-8")
    assert "--non-interactive" not in text
    parsed = yaml.safe_load(text)
    assert parsed == {"disabled": disabled}
