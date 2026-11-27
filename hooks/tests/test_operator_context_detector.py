#!/usr/bin/env python3
"""Tests for the operator-context-detector SessionStart hook.

The personal profile used to tell every session "Full autonomy. No approval
gates.", which contradicts the approval phrases /home/feedgen/CLAUDE.md
reserves for the owner (B-12 / I-02). It now grants autonomy within branch
safety and the CLAUDE.md approval rules.

Run with: python3 -m pytest hooks/tests/test_operator_context_detector.py -v
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK_PATH = Path(__file__).resolve().parent.parent / "operator-context-detector.py"

spec = importlib.util.spec_from_file_location("operator_context_detector", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

_FALSE_CLAIMS = ("No approval gates", "Full autonomy", "No additional approval steps required")


def test_personal_summary_keeps_the_claude_md_approval_rules() -> None:
    injection = mod.get_profile_injection("personal", "default")
    first_line = injection.splitlines()[0]
    assert first_line.startswith("[operator-context] Profile: personal — ")
    assert "branch safety" in first_line
    assert "CLAUDE.md approval rules" in first_line
    for claim in _FALSE_CLAIMS:
        assert claim not in injection
    assert injection.splitlines()[1] == "[operator-context] Detection: default"


def test_unknown_profile_falls_back_to_the_personal_summary() -> None:
    personal = mod.get_profile_injection("personal", "x").splitlines()[0].split(" — ", 1)[1]
    unknown = mod.get_profile_injection("mystery", "OPERATOR_PROFILE=mystery").splitlines()[0]
    assert unknown == f"[operator-context] Profile: mystery — {personal}"


def test_personal_guidance_names_the_owner_approval_reservation() -> None:
    guidance = mod.PROFILE_GUIDANCE["personal"]
    for claim in _FALSE_CLAIMS:
        assert claim not in guidance
    assert "CLAUDE.md" in guidance
    assert "never commit to main" in guidance


@pytest.mark.skipif(Path("/.dockerenv").exists(), reason="a container is always the ci profile")
def test_hook_injects_the_personal_summary(tmp_path: Path) -> None:
    env = {k: v for k, v in os.environ.items() if k not in ("CI", "GITHUB_ACTIONS", "GITLAB_CI", "PRODUCTION")}
    env.update({"HOME": str(tmp_path), "OPERATOR_PROFILE": "personal", "PROTECTED_ORGS": ""})
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps({"hook_event_name": "SessionStart", "source": "startup"}),
        capture_output=True,
        text=True,
        env=env,
        cwd=tmp_path,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert context.startswith("[operator-context] Profile: personal — ")
    assert "CLAUDE.md approval rules" in context
    assert "No approval gates" not in context


@pytest.mark.parametrize("branch", ["production", "release/2026.11"])
def test_worktree_gitdir_pointer_detects_production_branch(tmp_path: Path, monkeypatch, branch: str) -> None:
    main_git = tmp_path / "main" / ".git"
    wt_gitdir = main_git / "worktrees" / "wt1"
    wt_gitdir.mkdir(parents=True)
    (wt_gitdir / "HEAD").write_text(f"ref: refs/heads/{branch}\n", encoding="utf-8")
    (wt_gitdir / "commondir").write_text("../..\n", encoding="utf-8")

    wt_dir = tmp_path / "wt1"
    wt_dir.mkdir()
    (wt_dir / ".git").write_text(f"gitdir: {wt_gitdir}\n", encoding="utf-8")

    monkeypatch.chdir(wt_dir)
    monkeypatch.delenv("PRODUCTION", raising=False)
    assert mod._read_git_branch() == branch
    assert mod.detect_production_context() == f"branch={branch}"


def test_worktree_commondir_reads_origin_remote_for_protected_org(tmp_path: Path, monkeypatch) -> None:
    main_git = tmp_path / "main" / ".git"
    wt_gitdir = main_git / "worktrees" / "wt-work"
    wt_gitdir.mkdir(parents=True)
    (main_git / "config").write_text(
        '[core]\n\trepositoryformatversion = 0\n[remote "origin"]\n\turl = git@github.com:acme-corp/service.git\n',
        encoding="utf-8",
    )
    (wt_gitdir / "HEAD").write_text("ref: refs/heads/feat/x\n", encoding="utf-8")
    (wt_gitdir / "commondir").write_text("../..\n", encoding="utf-8")

    wt_dir = tmp_path / "wt-work"
    wt_dir.mkdir()
    # Use a relative gitdir pointer to verify relative resolution too.
    (wt_dir / ".git").write_text("gitdir: ../main/.git/worktrees/wt-work\n", encoding="utf-8")

    monkeypatch.chdir(wt_dir)
    monkeypatch.setenv("PROTECTED_ORGS", "acme-corp")
    assert mod._read_git_remote() == "git@github.com:acme-corp/service.git"
    reason = mod.detect_protected_org()
    assert reason is not None
    assert "acme-corp" in reason
