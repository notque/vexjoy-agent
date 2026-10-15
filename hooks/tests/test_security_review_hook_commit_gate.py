"""End-to-end commit-gate tests for security-review-hook.

Added from the E2 mutation check. The existing suite patches `_run_scanner`, so
nothing exercised the real scanner call, the staged-only scan, the working
directory choice, the findings cap, or the missing-scanner fail-open. These tests
run the hook as a subprocess against a real tmp git repo and the real scanner.

Fixture code is assembled from fragments so this file holds no scanner pattern.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[1]
HOOK = HOOKS_DIR / "security-review-hook.py"

HIGH_LINE = "os." + "system(cmd)\n"
MEDIUM_LINE = "# TODO: secu" + "rity review this later\n"
COMMIT = "git " + "commit -m change"


def _git(repo: Path, *args: str) -> None:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})
    subprocess.run(["git", *args], cwd=repo, env=env, capture_output=True, text=True, check=True)


def _repo(root: Path, name: str = "repo") -> Path:
    repo = root / name
    repo.mkdir()
    _git(repo, "init", "--quiet", "-b", "main")
    return repo


def _stage(repo: Path, name: str, body: str) -> None:
    (repo / name).write_text(body, encoding="utf-8")
    _git(repo, "add", name)


def _run(command: str, cwd: Path, *, hook: Path = HOOK, home: Path | None = None) -> tuple[bool, str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("VEXJOY_SECURITY_REVIEW")}
    env["HOME"] = str(home or cwd.parent)
    event = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd)}
    proc = subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    if not proc.stdout.strip():
        return False, "", proc.stderr
    out = json.loads(proc.stdout)["hookSpecificOutput"]
    return out["permissionDecision"] == "deny", out["permissionDecisionReason"], proc.stderr


def test_staged_high_finding_denies_the_commit_and_names_the_file(tmp_path):
    repo = _repo(tmp_path)
    _stage(repo, "app.py", "import os\n" + HIGH_LINE)
    denied, reason, _ = _run(COMMIT, repo)
    assert denied is True
    assert "app.py:2" in reason
    assert "1 high" in reason


def test_bare_commit_with_nothing_after_it_is_still_gated(tmp_path):
    repo = _repo(tmp_path)
    _stage(repo, "app.py", "import os\n" + HIGH_LINE)
    assert _run("git " + "commit", repo)[0] is True


def test_finding_that_is_not_staged_does_not_block(tmp_path):
    repo = _repo(tmp_path)
    _stage(repo, "ok.py", "x = 1\n")
    (repo / "later.py").write_text("import os\n" + HIGH_LINE, encoding="utf-8")
    assert _run(COMMIT, repo)[0] is False


def test_medium_finding_alone_does_not_block(tmp_path):
    repo = _repo(tmp_path)
    _stage(repo, "app.py", MEDIUM_LINE)
    assert _run(COMMIT, repo)[0] is False


def test_cd_prefix_selects_the_repository_to_scan(tmp_path):
    repo = _repo(tmp_path)
    elsewhere = _repo(tmp_path, "elsewhere")
    _stage(repo, "app.py", "import os\n" + HIGH_LINE)
    assert _run(f"cd {repo} && {COMMIT}", elsewhere)[0] is True
    assert _run(f"cd {elsewhere} && {COMMIT}", repo)[0] is False


@pytest.mark.parametrize("form", ['cd "{repo}" && {commit}', "cd {repo} ; {commit}", "cd {repo};{commit}"])
def test_other_cd_prefix_forms_select_the_repository(tmp_path, form):
    repo = _repo(tmp_path)
    elsewhere = _repo(tmp_path, "elsewhere")
    _stage(repo, "app.py", "import os\n" + HIGH_LINE)
    assert _run(form.format(repo=repo, commit=COMMIT), elsewhere)[0] is True


def test_findings_list_is_capped_at_twenty(tmp_path):
    repo = _repo(tmp_path)
    _stage(repo, "app.py", "import os\n" + HIGH_LINE * 25)
    denied, reason, _ = _run(COMMIT, repo)
    assert denied is True
    listed = [line for line in reason.splitlines() if line.startswith("  [HIGH]")]
    assert len(listed) == 20
    assert "... and 5 more" in reason


def test_ten_findings_are_all_listed_without_a_more_line(tmp_path):
    repo = _repo(tmp_path)
    _stage(repo, "app.py", "import os\n" + HIGH_LINE * 10)
    denied, reason, _ = _run(COMMIT, repo)
    assert denied is True
    assert len([line for line in reason.splitlines() if line.startswith("  [HIGH]")]) == 10
    assert "more" not in reason


def test_missing_scanner_allows_the_commit_with_a_warning(tmp_path):
    hooks_copy = tmp_path / "copy" / "hooks"
    hooks_copy.mkdir(parents=True)
    shutil.copy(HOOK, hooks_copy / HOOK.name)
    shutil.copytree(HOOKS_DIR / "lib", hooks_copy / "lib")
    home = tmp_path / "empty-home"
    home.mkdir()
    repo = _repo(tmp_path)
    _stage(repo, "app.py", "import os\n" + HIGH_LINE)
    denied, _, stderr = _run(COMMIT, repo, hook=hooks_copy / HOOK.name, home=home)
    assert denied is False
    assert "scanner unavailable" in stderr


@pytest.mark.parametrize("command", ["echo git commitment", "git status"])
def test_other_commands_are_ignored(tmp_path, command):
    repo = _repo(tmp_path)
    _stage(repo, "app.py", "import os\n" + HIGH_LINE)
    assert _run(command, repo)[0] is False
