"""ADR lookup and toolkit-scope tests for pretool-adr-creation-gate.

Added from the E2 mutation check. The existing suite only used a project-root
`adr/` directory and tmp dirs with no git remote. It never proved that:
- the centralized ADR at `~/.vexjoy-agent/<repo>/adrs/<name>.md` unlocks a new
  component, with `<repo>` read from the `origin` URL in every URL shape,
- the denial names that same repo directory,
- a hook is gated only in a repo that has BOTH agents/ and skills/.

Each test runs the hook as a subprocess with HOME set to a tmp dir.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / "pretool-adr-creation-gate.py"


def _git(repo: Path, *args: str) -> None:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    subprocess.run(["git", *args], cwd=repo, env=env, capture_output=True, text=True, check=True)


def _repo(tmp_path: Path, name: str = "checkout", *, origin: str | None = None) -> Path:
    repo = tmp_path / name
    repo.mkdir()
    _git(repo, "init", "--quiet")
    if origin is not None:
        _git(repo, "remote", "add", "origin", origin)
    return repo


def _write_event(tmp_path: Path, repo: Path, file_path: Path) -> tuple[bool, str]:
    env = {k: v for k, v in os.environ.items() if k not in ("ADR_CREATION_GATE_BYPASS", "CLAUDE_PROJECT_DIR")}
    env["HOME"] = str(tmp_path / "home")
    event = {"tool_name": "Write", "tool_input": {"file_path": str(file_path)}, "cwd": str(repo)}
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    if not proc.stdout.strip():
        return False, ""
    out = json.loads(proc.stdout)["hookSpecificOutput"]
    return out["permissionDecision"] == "deny", out["permissionDecisionReason"]


def _centralized_adr(tmp_path: Path, repo_dir: str, component: str) -> None:
    adr = tmp_path / "home" / ".vexjoy-agent" / repo_dir / "adrs" / f"{component}.md"
    adr.parent.mkdir(parents=True)
    adr.write_text("# ADR\n", encoding="utf-8")


ORIGINS = [
    ("https://github.com/acme/widget-kit.git", "widget-kit"),
    ("https://github.com/acme/plain-name", "plain-name"),
    ("https://github.com/acme/slashed/", "slashed"),
    ("git@github.com:acme/ssh-kit.git", "ssh-kit"),
]


@pytest.mark.parametrize(("origin", "repo_dir"), ORIGINS)
def test_centralized_adr_named_by_the_origin_repo_allows_a_new_skill(tmp_path, origin, repo_dir):
    repo = _repo(tmp_path, origin=origin)
    _centralized_adr(tmp_path, repo_dir, "fresh-skill")
    denied, _ = _write_event(tmp_path, repo, repo / "skills" / "fresh-skill" / "SKILL.md")
    assert denied is False


@pytest.mark.parametrize(("origin", "repo_dir"), ORIGINS)
def test_denial_names_the_origin_repo_directory(tmp_path, origin, repo_dir):
    repo = _repo(tmp_path, origin=origin)
    denied, reason = _write_event(tmp_path, repo, repo / "skills" / "fresh-skill" / "SKILL.md")
    assert denied is True
    assert f"~/.vexjoy-agent/{repo_dir}/adrs/fresh-skill.md" in reason


def test_without_an_origin_the_checkout_directory_name_is_the_repo(tmp_path):
    repo = _repo(tmp_path, name="local-only")
    denied, reason = _write_event(tmp_path, repo, repo / "skills" / "fresh-skill" / "SKILL.md")
    assert denied is True
    assert "~/.vexjoy-agent/local-only/adrs/fresh-skill.md" in reason
    _centralized_adr(tmp_path, "local-only", "fresh-skill")
    denied, _ = _write_event(tmp_path, repo, repo / "skills" / "fresh-skill" / "SKILL.md")
    assert denied is False


@pytest.mark.parametrize("present", [["agents"], ["skills"]])
def test_new_hook_is_not_gated_unless_the_repo_has_agents_and_skills(tmp_path, present):
    repo = _repo(tmp_path)
    for name in present:
        (repo / name).mkdir()
    denied, _ = _write_event(tmp_path, repo, repo / "hooks" / "brand-new.py")
    assert denied is False


def test_new_hook_is_gated_in_a_repo_with_agents_and_skills(tmp_path):
    repo = _repo(tmp_path)
    (repo / "agents").mkdir()
    (repo / "skills").mkdir()
    denied, _ = _write_event(tmp_path, repo, repo / "hooks" / "brand-new.py")
    assert denied is True
