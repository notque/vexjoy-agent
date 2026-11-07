"""Regression tests for the deterministic worktree-capacity guard."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import SimpleNamespace

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "worktree_capacity.py"
TOOLKIT_ROOT = Path(__file__).resolve().parents[5]
WORKTREE_RULES = TOOLKIT_ROOT / "skills" / "meta" / "do" / "references" / "worktree-rules.md"
SPEC = importlib.util.spec_from_file_location("worktree_capacity", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
worktree_capacity = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(worktree_capacity)


def test_dispatcher_command_resolves_in_the_flat_install_layout():
    """The worktree rules call the guard through ~/.claude/skills/<skill>/...

    The installer links each live skill flat under ~/.claude/skills/<name>, so the
    documented path must name a live skill directory that holds this script.
    """
    text = WORKTREE_RULES.read_text(encoding="utf-8")
    match = re.search(r"~/\.claude/skills/([a-z0-9-]+)/(\S*worktree_capacity\.py)", text)
    assert match, "worktree-rules.md no longer calls worktree_capacity.py through ~/.claude/skills/"
    name, rest = match.groups()
    skill_dirs = [p.parent for p in (TOOLKIT_ROOT / "skills").glob(f"*/{name}/SKILL.md")]
    assert len(skill_dirs) == 1, f"~/.claude/skills/{name} names no single repo skill"
    skill_md = (skill_dirs[0] / "SKILL.md").read_text(encoding="utf-8")
    assert "promoted_to:" not in skill_md.split("---", 2)[1], f"{name} is a husk; the installer skips it"
    assert (skill_dirs[0] / rest).resolve() == SCRIPT_PATH


def test_capacity_status_reserves_hard_stop_for_new_worktrees():
    assert worktree_capacity.capacity_status(79, soft_percent=80, hard_percent=85) == "ready"
    assert worktree_capacity.capacity_status(80, soft_percent=80, hard_percent=85) == "cleanup-soon"
    assert worktree_capacity.capacity_status(85, soft_percent=80, hard_percent=85) == "blocked"


def test_usable_disk_percent_counts_filesystem_reserved_space_as_unavailable():
    stats = SimpleNamespace(f_blocks=100, f_bfree=30, f_bavail=20)

    assert worktree_capacity.usable_disk_percent(stats) == 77.8


def test_parse_worktree_porcelain_keeps_only_paths_under_agent_root(tmp_path):
    agent_root = tmp_path / ".claude" / "worktrees"
    kept = agent_root / "active"
    outside = tmp_path / "manual-checkout"
    payload = (
        f"worktree {tmp_path}\nHEAD abc\nbranch refs/heads/main\n\n"
        f"worktree {kept}\nHEAD def\nbranch refs/heads/fix/active\n\n"
        f"worktree {outside}\nHEAD ghi\ndetached\n"
    )

    assert worktree_capacity.agent_worktree_paths(payload, agent_root) == [kept]


def test_capacity_report_marks_clean_checkouts_for_dispatcher_review(tmp_path):
    report = worktree_capacity.capacity_report(
        used_percent=81,
        paths=[tmp_path / "clean", tmp_path / "dirty"],
        clean_paths={tmp_path / "clean"},
        soft_percent=80,
        hard_percent=85,
    )

    assert report["status"] == "cleanup-soon"
    assert report["worktrees"] == {"count": 2, "clean_candidates": [str(tmp_path / "clean")]}
