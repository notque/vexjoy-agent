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
    # Nested category structure: skills/meta/install/, skills/meta/do/
    meta_dir = skills_dir / "meta"
    meta_dir.mkdir()
    for name in ("install", "do"):
        skill_dir = meta_dir / name
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")


def test_get_toolkit_repo_root_uses_ledger_source_when_installed_copy(tmp_path, monkeypatch) -> None:
    repo_root = tmp_path / "toolkit"
    _make_repo(repo_root)
    claude_dir = tmp_path / ".claude"
    (claude_dir / "vexjoy").mkdir(parents=True)
    ledger = {"schema": 1, "source_root": str(repo_root), "entries": []}
    (claude_dir / "vexjoy" / "ledger.json").write_text(json.dumps(ledger), encoding="utf-8")
    monkeypatch.setattr(install_doctor, "CLAUDE_DIR", claude_dir)
    monkeypatch.setattr(install_doctor, "__file__", str(tmp_path / "copy" / "scripts" / "install-doctor.py"))

    assert install_doctor.get_toolkit_repo_root() == repo_root


def _fake_doctor(findings: list[dict], warnings: int = 0):
    class Proc:
        stdout = json.dumps({"exit": 0, "data": {"findings": findings, "warnings": warnings}})

    return lambda *_a, **_k: Proc()


def test_check_install_layout_passes_without_engine_errors(monkeypatch) -> None:
    import subprocess

    monkeypatch.setattr(subprocess, "run", _fake_doctor([{"level": "warn", "check": "unowned"}], warnings=1))
    results = install_doctor.check_install_layout()
    assert [r["passed"] for r in results] == [True]
    assert "1 warnings" in results[0]["detail"]


def test_check_install_layout_fails_per_engine_error(monkeypatch) -> None:
    import subprocess

    findings = [
        {"level": "error", "check": "dangling-link", "target": "codex", "path": "/h/.codex/skills/x", "detail": ""},
        {"level": "warn", "check": "unowned", "target": "claude", "path": "/h/.claude/skills/y", "detail": ""},
    ]
    monkeypatch.setattr(subprocess, "run", _fake_doctor(findings))
    results = install_doctor.check_install_layout()
    assert len(results) == 1 and results[0]["passed"] is False
    assert results[0]["name"] == "install_layout_dangling-link"


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


def test_python_runtime_files_only_require_read_permission(tmp_path, monkeypatch) -> None:
    claude_dir = tmp_path / ".claude"
    for subdir in ("hooks", "scripts"):
        path = claude_dir / subdir
        path.mkdir(parents=True)
        script = path / "runtime.py"
        script.write_text("print('ok')\n", encoding="utf-8")
        script.chmod(0o644)
    monkeypatch.setattr(install_doctor, "CLAUDE_DIR", claude_dir)

    results = install_doctor.check_permissions()

    assert all(result["passed"] for result in results)
    assert all("readable" in result["label"] for result in results)


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
