"""Negative-control tests for scripts/validate-doc-commands.py.

Proves the validator rejects bad input (missing script references) and
accepts good input (existing script references, external paths).

Run with: python3 -m pytest scripts/tests/test_validate_doc_commands.py -v
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "validate-doc-commands.py"


def _setup_repo(tmp_path: Path, doc_content: str, scripts: list[str] | None = None) -> Path:
    """Build a minimal repo tree with a docs/ markdown file and optional script stubs."""
    repo = tmp_path / "repo"
    scripts_dir = repo / "scripts"
    scripts_dir.mkdir(parents=True)
    docs = repo / "docs"
    docs.mkdir()
    docs.joinpath("test.md").write_text(doc_content, encoding="utf-8")

    # Copy the validator into repo/scripts/ so REPO_ROOT resolves to repo/
    shutil.copy2(SCRIPT, scripts_dir / "validate-doc-commands.py")

    for s in scripts or []:
        p = repo / s
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("#!/bin/bash\n", encoding="utf-8")
    return repo


def _run(repo: Path) -> subprocess.CompletedProcess[str]:
    script = repo / "scripts" / "validate-doc-commands.py"
    return subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        cwd=str(repo),
    )


# ---------------------------------------------------------------------------
# Positive: all referenced scripts exist -> exit 0
# ---------------------------------------------------------------------------


def test_clean_references_pass(tmp_path: Path) -> None:
    content = "# Guide\n\n```bash\npython3 scripts/deploy.py --dry-run\n```\n"
    repo = _setup_repo(tmp_path, content, scripts=["scripts/deploy.py"])
    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr


# ---------------------------------------------------------------------------
# NEGATIVE: referenced script does not exist -> exit 1
# ---------------------------------------------------------------------------


def test_missing_script_exits_one(tmp_path: Path) -> None:
    content = "# Guide\n\n```bash\npython3 scripts/missing-script.py\n```\n"
    repo = _setup_repo(tmp_path, content)
    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "missing-script.py" in result.stdout, result.stdout


def test_missing_sh_script_exits_one(tmp_path: Path) -> None:
    content = "# Guide\n\n```bash\n./scripts/missing.sh\n```\n"
    repo = _setup_repo(tmp_path, content)
    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "missing.sh" in result.stdout, result.stdout


# ---------------------------------------------------------------------------
# Edge case: external/home paths are skipped, not flagged
# ---------------------------------------------------------------------------


def test_external_paths_skipped(tmp_path: Path) -> None:
    content = "# Guide\n\n```bash\npython3 ~/tools/setup.py\npython3 /tmp/scratch.py\n```\n"
    repo = _setup_repo(tmp_path, content)
    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr


def test_variable_paths_skipped(tmp_path: Path) -> None:
    content = "# Guide\n\n```bash\npython3 $HOME/tools/setup.py\n```\n"
    repo = _setup_repo(tmp_path, content)
    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr


# ---------------------------------------------------------------------------
# Installed paths map back to the repo; inline code and root guides are scanned
# ---------------------------------------------------------------------------


def test_installed_script_path_must_exist_in_repo(tmp_path: Path) -> None:
    """~/.claude/scripts is the repo's scripts/ dir after install, so a missing script is drift."""
    content = "# Guide\n\n```bash\npython3 ~/.claude/scripts/gone-doctor.py check\n```\n"
    repo = _setup_repo(tmp_path, content)
    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "~/.claude/scripts/gone-doctor.py" in result.stdout, result.stdout


def test_installed_paths_that_exist_in_repo_pass(tmp_path: Path) -> None:
    content = (
        "# Guide\n\n```bash\npython3 ~/.claude/scripts/install-doctor.py check\n"
        "python3 $HOME/.codex/hooks/sync-to-user-claude.py\n```\n"
    )
    repo = _setup_repo(tmp_path, content, scripts=["scripts/install-doctor.py", "hooks/sync-to-user-claude.py"])
    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr


def test_installed_hook_path_must_exist_in_repo(tmp_path: Path) -> None:
    content = "Run `python3 ~/.claude/hooks/retired-hook.py` to resync.\n"
    repo = _setup_repo(tmp_path, content)
    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "~/.claude/hooks/retired-hook.py" in result.stdout, result.stdout


def test_inline_code_invocation_is_checked(tmp_path: Path) -> None:
    content = "Validate with `python3 scripts/removed-validator.py --all` before pushing.\n"
    repo = _setup_repo(tmp_path, content)
    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "scripts/removed-validator.py" in result.stdout, result.stdout


def test_inline_path_outside_the_repo_is_skipped(tmp_path: Path) -> None:
    content = "Use another worktree: `python3 ../other-wt/scripts/routing-manifest.py --tiered`.\n"
    repo = _setup_repo(tmp_path, content)
    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr


def test_agents_md_invocations_are_checked(tmp_path: Path) -> None:
    repo = _setup_repo(tmp_path, "# Guide\n")
    (repo / "AGENTS.md").write_text("```bash\npython3 scripts/gone.py\n```\n", encoding="utf-8")
    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "AGENTS.md: scripts/gone.py" in result.stdout, result.stdout
