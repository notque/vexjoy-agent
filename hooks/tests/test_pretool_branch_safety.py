"""Blocked and allowed cases for the branch-safety gate (B-16).

Each case runs the real hook against a throwaway repository whose current
branch is set with ``git symbolic-ref``, so no commit and no global git
config is needed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parent.parent / "pretool-branch-safety.py"


def _git_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})
    env.pop("BRANCH_SAFETY_BYPASS", None)
    env.pop("CLAUDE_PROJECT_DIR", None)
    return env


def _repo(tmp_path: Path, branch: str) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True, env=_git_env(), timeout=30)
    subprocess.run(
        ["git", "symbolic-ref", "HEAD", f"refs/heads/{branch}"],
        cwd=repo,
        check=True,
        capture_output=True,
        env=_git_env(),
        timeout=30,
    )
    return repo


def _run(command: str, *, cwd: Path, event_cwd: Path | None, env_extra: dict[str, str] | None = None):
    event = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": command}}
    if event_cwd is not None:
        event["cwd"] = str(event_cwd)
    env = _git_env()
    env["HOME"] = str(cwd)
    env.update(env_extra or {})
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
        timeout=30,
    )


def _decision(result: subprocess.CompletedProcess[str]) -> dict | None:
    if not result.stdout.strip():
        return None
    return json.loads(result.stdout)["hookSpecificOutput"]


@pytest.mark.parametrize("branch", ["main", "master"])
def test_commit_on_a_protected_branch_is_denied(tmp_path: Path, branch: str) -> None:
    repo = _repo(tmp_path, branch)

    result = _run('git commit -m "change"', cwd=tmp_path, event_cwd=repo)

    assert result.returncode == 0, result.stderr
    decision = _decision(result)
    assert decision is not None, "a commit on a protected branch must be denied"
    assert decision["hookEventName"] == "PreToolUse"
    assert decision["permissionDecision"] == "deny"
    assert f"Cannot commit directly to {branch}" in decision["permissionDecisionReason"]
    assert f"[branch-safety] BLOCKED: Cannot commit directly to {branch}" in result.stderr


@pytest.mark.parametrize(
    "template",
    [
        "cd {repo} && git commit -am wip",
        pytest.param(
            'git -C "{repo}" commit -m wip',
            marks=pytest.mark.xfail(
                strict=False,
                reason=(
                    "known gap, left for a gate-behavior change: the 'git commit' substring "
                    "pre-check exits before _extract_effective_cwd() handles git -C <path>"
                ),
            ),
        ),
    ],
    ids=["cd-prefix", "git-C"],
)
def test_commit_aimed_at_a_protected_repo_from_elsewhere_is_denied(tmp_path: Path, template: str) -> None:
    repo = _repo(tmp_path, "main")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    result = _run(template.format(repo=repo), cwd=elsewhere, event_cwd=elsewhere)

    assert (_decision(result) or {}).get("permissionDecision") == "deny"


def test_bypass_variable_allows_a_commit_on_main(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "main")

    result = _run("git commit -m wip", cwd=tmp_path, event_cwd=repo, env_extra={"BRANCH_SAFETY_BYPASS": "1"})

    assert result.returncode == 0
    assert result.stdout == ""


@pytest.mark.parametrize("branch", ["feature/audit", "fix/main-typo", "mainline"])
def test_commit_on_a_feature_branch_is_allowed(tmp_path: Path, branch: str) -> None:
    repo = _repo(tmp_path, branch)

    result = _run("git commit -m wip", cwd=tmp_path, event_cwd=repo)

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""


def test_non_commit_command_on_main_is_allowed(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "main")

    result = _run("git status --short", cwd=tmp_path, event_cwd=repo)

    assert result.stdout == ""
