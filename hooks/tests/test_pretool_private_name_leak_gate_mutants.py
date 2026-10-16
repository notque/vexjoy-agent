#!/usr/bin/env python3
"""Mutation-killing tests for pretool-private-name-leak-gate.

All names are synthetic placeholders. HOME points at a tmp dir holding a fake
private tree; the real ~/private-skills is never read.

Run with: python3 -m pytest hooks/tests/test_pretool_private_name_leak_gate_mutants.py -v
"""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

HOOK_PATH = Path(__file__).parent.parent / "pretool-private-name-leak-gate.py"

LEAK = "zorblax"
COMMIT = "git " + "commit"


class World:
    """A fake home with a private tree, a toolkit repo, and a non-toolkit dir."""

    def __init__(self, root: Path, names=(LEAK,), owner_terms=None, nested_no_frontmatter=None):
        self.home = root / "home"
        self.private = self.home / "private-skills"
        self.private.mkdir(parents=True)
        for name in names:
            (self.private / name).mkdir(parents=True)
            (self.private / name / "SKILL.md").write_text(f"---\nname: {name}\n---\n", encoding="utf-8")
        if nested_no_frontmatter:
            pkg = self.private / nested_no_frontmatter / "skill"
            pkg.mkdir(parents=True)
            (pkg / "SKILL.md").write_text("no frontmatter here\n", encoding="utf-8")
        if owner_terms:
            (self.private / ".private-terms").write_text("\n".join(owner_terms) + "\n", encoding="utf-8")
        self.toolkit = root / "toolkit"
        (self.toolkit / "agents").mkdir(parents=True)
        (self.toolkit / "skills").mkdir()
        self.elsewhere = root / "elsewhere"
        self.elsewhere.mkdir()

    def run(self, command, cwd=None, env_extra=None):
        """Return (returncode, denied, stderr)."""
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("PRIVATE_NAME_GATE_BYPASS", "CLAUDE_PROJECT_DIR", "CLAUDE_HOOKS_DEBUG")
        }
        env["HOME"] = str(self.home)
        env.update(env_extra or {})
        event = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd or self.toolkit)}
        proc = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input=json.dumps(event),
            capture_output=True,
            text=True,
            env=env,
            cwd=self.elsewhere,
            timeout=60,
            check=False,
        )
        denied = bool(proc.stdout.strip()) and (
            json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
        )
        return proc.returncode, denied, proc.stderr


def test_leak_in_commit_message_is_denied_baseline(tmp_path):
    rc, denied, _ = World(tmp_path).run(f'{COMMIT} -m "add {LEAK} notes"')
    assert rc == 0
    assert denied is True


def test_bypass_prefix_after_semicolon_is_honored(tmp_path):
    cmd = f'echo hi; PRIVATE_NAME_GATE_BYPASS=1 {COMMIT} -m "{LEAK}"'
    rc, denied, _ = World(tmp_path).run(cmd)
    assert rc == 0
    assert denied is False


def test_bypass_prefix_after_or_is_honored(tmp_path):
    cmd = f'false || PRIVATE_NAME_GATE_BYPASS=1 {COMMIT} -m "{LEAK}"'
    rc, denied, _ = World(tmp_path).run(cmd)
    assert rc == 0
    assert denied is False


def test_bypass_word_as_trailing_argument_does_not_bypass(tmp_path):
    cmd = f"{COMMIT} -m {LEAK} PRIVATE_NAME_GATE_BYPASS=1"
    _, denied, _ = World(tmp_path).run(cmd)
    assert denied is True


def test_four_char_private_name_blocks(tmp_path):
    _, denied, _ = World(tmp_path, names=("zorb",)).run(f'{COMMIT} -m "zorb is here"')
    assert denied is True


def test_private_dir_without_usable_names_allows_everything(tmp_path):
    """Only a too-short name exists, so the term set is empty and nothing blocks."""
    _, denied, _ = World(tmp_path, names=("abc",)).run(f'{COMMIT} -m "ordinary change"')
    assert denied is False


def test_cwd_in_nested_subdir_of_toolkit_is_still_gated(tmp_path):
    world = World(tmp_path)
    deep = world.toolkit / "scripts" / "sub"
    deep.mkdir(parents=True)
    _, denied, _ = world.run(f'{COMMIT} -m "{LEAK}"', cwd=deep)
    assert denied is True


def test_nested_package_without_frontmatter_blocks_under_package_dir_name(tmp_path):
    world = World(tmp_path, names=(), nested_no_frontmatter="zorbpkg-tool")
    _, denied, _ = world.run(f'{COMMIT} -m "mention zorbpkg-tool"')
    assert denied is True


def test_longer_owner_term_wins_over_its_shorter_prefix_in_redaction(tmp_path):
    world = World(tmp_path, names=(), owner_terms=["zorb", "zorb-extra"])
    _, denied, err = world.run(f'{COMMIT} -m "ship zorb-extra"')
    assert denied is True
    assert "z…a" in err


def test_filename_fragment_inside_message_is_not_read_as_message_file(tmp_path):
    """-m text that merely ends in a file's name must not pull that file into the scan."""
    world = World(tmp_path)
    (world.toolkit / "leak.txt").write_text(f"{LEAK}\n", encoding="utf-8")
    _, denied, _ = world.run(f'{COMMIT} -m "1234567leak.txt"')
    assert denied is False


def test_commit_message_file_flag_is_still_scanned(tmp_path):
    world = World(tmp_path)
    (world.toolkit / "msg.txt").write_text(f"{LEAK}\n", encoding="utf-8")
    _, denied, _ = world.run(f"{COMMIT} -F msg.txt")
    assert denied is True


def test_commits_inside_the_private_repo_itself_are_allowed(tmp_path):
    world = World(tmp_path)
    (world.private / "agents").mkdir(exist_ok=True)
    (world.private / "skills").mkdir(exist_ok=True)
    rc, denied, _ = world.run(f'{COMMIT} -m "{LEAK}"', cwd=world.private)
    assert rc == 0
    assert denied is False


def test_no_private_tree_is_silent_unless_debug(tmp_path):
    world = World(tmp_path)
    for p in sorted(world.private.rglob("*"), reverse=True):
        p.unlink() if p.is_file() else p.rmdir()
    world.private.rmdir()
    _, denied, err = world.run(f'{COMMIT} -m "{LEAK}"')
    assert denied is False
    assert err == ""
    _, _, err_debug = world.run(f'{COMMIT} -m "{LEAK}"', env_extra={"CLAUDE_HOOKS_DEBUG": "1"})
    assert err_debug.strip() != ""


def test_clean_commit_says_so_only_in_debug(tmp_path):
    world = World(tmp_path)
    _, denied, err = world.run(f'{COMMIT} -m "plain change"')
    assert denied is False
    assert err == ""
    _, _, err_debug = world.run(f'{COMMIT} -m "plain change"', env_extra={"CLAUDE_HOOKS_DEBUG": "1"})
    assert err_debug.strip() != ""


def test_block_records_blocked_governance_event(tmp_path):
    world = World(tmp_path)
    spec = importlib.util.spec_from_file_location("pn_gate_mutants_mod", HOOK_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    calls = []
    event = {"tool_input": {"command": f'{COMMIT} -m "{LEAK}"'}, "cwd": str(world.toolkit)}
    env = {k: v for k, v in os.environ.items() if k not in ("PRIVATE_NAME_GATE_BYPASS", "CLAUDE_PROJECT_DIR")}
    with (
        patch.dict(os.environ, env, clear=True),
        patch.object(mod, "_PRIVATE_DIR", world.private),
        patch.object(mod, "_USER_INDEX", tmp_path / "none.json"),
        patch.object(mod, "read_stdin", return_value=json.dumps(event)),
        patch.object(mod, "record_governance", lambda *_a, **kw: calls.append(kw)),
        patch.object(mod, "deny_tool_use", lambda *_a, **_kw: None),
    ):
        try:
            mod.main()
        except SystemExit:
            pass
    assert len(calls) == 1
    assert calls[0]["blocked"] is True
