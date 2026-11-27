"""Regression tests for skills/process/pr-workflow/scripts/miner.py and validate.py."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
MINER_PATH = SCRIPTS_DIR / "miner.py"
VALIDATE_PATH = SCRIPTS_DIR / "validate.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_miner_check_auth_does_not_require_positional_args(tmp_path: Path) -> None:
    env = {**os.environ, "HOME": str(tmp_path), "USERPROFILE": str(tmp_path)}
    env.pop("GITHUB_TOKEN", None)
    proc = subprocess.run(
        [sys.executable, str(MINER_PATH), "--check-auth"],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    # Must NOT fail argparse with exit 2 for missing repos/output; exits 1 on missing token.
    assert proc.returncode == 1
    assert "GitHub token not found" in proc.stdout


def test_miner_without_check_auth_requires_positional_args() -> None:
    proc = subprocess.run(
        [sys.executable, str(MINER_PATH)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 2
    assert "required unless --check-auth" in proc.stderr


def test_miner_guards_null_user_and_body() -> None:
    miner_mod = _load("pr_workflow_miner", MINER_PATH)
    assert miner_mod._comment_user_login({"user": None}) is None
    assert miner_mod._comment_user_login({"user": {"login": "alice"}}) == "alice"
    assert miner_mod._comment_user_login(SimpleNamespace(user=None)) is None
    assert miner_mod._comment_body({"body": None}) == ""
    assert miner_mod._comment_body(SimpleNamespace(body=None)) == ""

    instance = miner_mod.PRMiner.__new__(miner_mod.PRMiner)
    assert instance._has_imperative(None) is False
    assert instance._has_imperative("You should always validate input.") is True

    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    pr = SimpleNamespace(
        number=42,
        title="Test PR",
        html_url="https://example.invalid/pr/42",
        user=None,
        merged=True,
        merged_at=now,
    )
    comment = SimpleNamespace(
        user=None,
        path="app.py",
        original_line=10,
        line=10,
        body=None,
        diff_hunk="",
        html_url="https://example.invalid/pr/42#c1",
        created_at=now,
    )
    interaction = instance._extract_interaction(pr, comment)
    assert interaction is not None
    assert interaction["author"] == "ghost"
    assert interaction["reviewer"] == "ghost"
    assert interaction["comment_text"] == ""


def test_validate_propagates_missing_file_exit_code(tmp_path: Path, monkeypatch) -> None:
    fake_skill = tmp_path / "pr-workflow"
    scripts_dir = fake_skill / "scripts"
    scripts_dir.mkdir(parents=True)
    validate_copy = scripts_dir / "validate.py"
    shutil.copy2(VALIDATE_PATH, validate_copy)
    # Intentionally omit SKILL.md, miner.py, and references/

    mod = _load("pr_workflow_validate_copy", validate_copy)
    monkeypatch.setattr(mod, "check_command", lambda _cmd: True)
    monkeypatch.setattr(mod, "check_python_package", lambda _pkg: True)
    monkeypatch.setattr(mod, "check_github_token", lambda: True)

    assert mod.main() == 1
