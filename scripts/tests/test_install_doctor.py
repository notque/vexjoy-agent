import importlib.util
import json
import sqlite3
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


def test_check_hook_files_expands_tilde_paths(tmp_path, monkeypatch) -> None:
    claude_dir = tmp_path / ".claude"
    hooks_dir = claude_dir / "hooks"
    hooks_dir.mkdir(parents=True)
    (hooks_dir / "sql-injection-detector.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    (claude_dir / "settings.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "PostToolUse": [
                        {
                            "hooks": [
                                {
                                    "command": "python3 ~/.claude/hooks/sql-injection-detector.py",
                                }
                            ]
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(install_doctor, "CLAUDE_DIR", claude_dir)

    results = install_doctor.check_hook_files()

    assert results[0]["passed"] is True
    assert "sql-injection-detector.py" not in results[0]["detail"]


def test_check_learning_db_uses_learning_subdir_v2_schema(tmp_path, monkeypatch) -> None:
    claude_dir = tmp_path / ".claude"
    db_dir = claude_dir / "learning"
    db_dir.mkdir(parents=True)
    db_path = db_dir / "learning.db"

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE learnings (id INTEGER PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO learnings (value) VALUES ('entry')")
        conn.execute("PRAGMA user_version = 3")
        conn.commit()
    finally:
        conn.close()

    monkeypatch.delenv("CLAUDE_LEARNING_DIR", raising=False)
    monkeypatch.setattr(install_doctor, "CLAUDE_DIR", claude_dir)

    result = install_doctor.check_learning_db()

    assert result["passed"] is True
    assert str(db_path) in result["detail"]
    assert "1 entries" in result["detail"]
