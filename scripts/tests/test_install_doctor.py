import importlib.util
import json
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parent.parent / "install-doctor.py"
SPEC = importlib.util.spec_from_file_location("install_doctor", MODULE_PATH)
install_doctor = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(install_doctor)


def _make_repo(repo_root: Path) -> None:
    for dirname in ("agents", "hooks"):
        (repo_root / dirname).mkdir(parents=True, exist_ok=True)
    skills_dir = repo_root / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    (skills_dir / "INDEX.json").write_text("{}\n", encoding="utf-8")
    for name in ("install", "do"):
        skill_dir = skills_dir / name
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")


def test_get_toolkit_repo_root_uses_manifest_when_installed_copy(tmp_path, monkeypatch) -> None:
    repo_root = tmp_path / "toolkit"
    _make_repo(repo_root)

    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    manifest = {"toolkit_path": str(repo_root)}
    (claude_dir / ".install-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    fake_runtime_script = tmp_path / "runtime" / "scripts" / "install-doctor.py"
    monkeypatch.setattr(install_doctor, "CLAUDE_DIR", claude_dir)
    monkeypatch.setattr(install_doctor, "__file__", str(fake_runtime_script))

    assert install_doctor.get_toolkit_repo_root() == repo_root


def test_check_codex_skills_reports_missing_entries(tmp_path, monkeypatch) -> None:
    repo_root = tmp_path / "toolkit"
    _make_repo(repo_root)

    codex_dir = tmp_path / ".codex"
    mirrored_skill = codex_dir / "skills" / "install"
    mirrored_skill.mkdir(parents=True)
    (mirrored_skill / "SKILL.md").write_text("# install\n", encoding="utf-8")

    monkeypatch.setattr(install_doctor, "CODEX_DIR", codex_dir)
    monkeypatch.setattr(install_doctor, "get_toolkit_repo_root", lambda: repo_root)

    result = install_doctor.check_codex_skills()

    assert result["passed"] is False
    assert result["name"] == "codex_skills"
    assert "missing" in result["detail"]
    assert "do" in result["detail"]


def test_inventory_counts_codex_skills(tmp_path, monkeypatch) -> None:
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()

    codex_dir = tmp_path / ".codex"
    for name in ("install", "do"):
        skill_dir = codex_dir / "skills" / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")

    monkeypatch.setattr(install_doctor, "CLAUDE_DIR", claude_dir)
    monkeypatch.setattr(install_doctor, "CODEX_DIR", codex_dir)
    monkeypatch.setattr(install_doctor, "check_mcp_servers", lambda: [])

    counts = install_doctor.inventory()

    assert counts["codex_skills"] == 2
