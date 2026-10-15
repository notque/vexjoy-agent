#!/usr/bin/env python3
"""Scoping tests for pretool-private-name-leak-gate, run as a subprocess.

Added from the E2 mutation check. The existing suite patches `_PRIVATE_DIR` and
runs `main()` in-process, so it never proved these end-to-end behaviours:
- every `gh pr` subcommand scans its `--body-file`, in both `--flag file` and
  `--flag=file` form, with a relative file resolved against the event cwd,
- `cd <dir> &&`, `cd "<dir>" &&`, `cd <dir> ;` and `git -C <dir>` choose the repo
  the gate checks,
- a directory with only one of agents/ and skills/ is not a toolkit repo,
- names under four characters and dot-prefixed agent stems never block,
- a public homonym listed in list-form INDEX.json never blocks.

All names are synthetic. HOME points at a tmp dir holding the fake private tree.

Run with: python3 -m pytest hooks/tests/test_pretool_private_name_leak_gate_scoping.py -v
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK_PATH = Path(__file__).parent.parent / "pretool-private-name-leak-gate.py"

PRIVATE_NAME = "secret-example-skill"
HOMONYM = "shared-fixture-name"


class World:
    """A fake home with a private tree, a toolkit repo, and a non-toolkit dir."""

    def __init__(self, root: Path):
        self.home = root / "home"
        private = self.home / "private-skills"
        for name in (PRIVATE_NAME, HOMONYM, "abc"):
            (private / name).mkdir(parents=True)
            (private / name / "SKILL.md").write_text(f"---\nname: {name}\n---\n", encoding="utf-8")
        (private / "agents").mkdir()
        (private / "agents" / ".hidden-fixture.md").write_text("agent\n", encoding="utf-8")
        self.toolkit = root / "toolkit"
        (self.toolkit / "agents").mkdir(parents=True)
        (self.toolkit / "skills").mkdir()
        self.elsewhere = root / "elsewhere"
        self.elsewhere.mkdir()
        self.home.mkdir(exist_ok=True)

    def run(self, command: str, event_cwd: Path | None = None) -> bool:
        env = {k: v for k, v in os.environ.items() if k not in ("PRIVATE_NAME_GATE_BYPASS", "CLAUDE_PROJECT_DIR")}
        env["HOME"] = str(self.home)
        event: dict = {"tool_name": "Bash", "tool_input": {"command": command}}
        if event_cwd is not None:
            event["cwd"] = str(event_cwd)
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
        assert proc.returncode == 0, proc.stderr
        if not proc.stdout.strip():
            return False
        return json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.fixture
def world(tmp_path: Path) -> World:
    return World(tmp_path)


@pytest.mark.parametrize("sub", ["create", "edit", "comment", "merge"])
@pytest.mark.parametrize("flag", ["--body-file", "-F"])
def test_every_pr_subcommand_scans_a_relative_body_file(world, sub, flag):
    (world.toolkit / "body.md").write_text(f"notes about {PRIVATE_NAME}\n", encoding="utf-8")
    assert world.run(f"gh pr {sub} 5 {flag} body.md", world.toolkit) is True


def test_body_file_equals_form_is_scanned(world):
    (world.toolkit / "body.md").write_text(f"notes about {PRIVATE_NAME}\n", encoding="utf-8")
    assert world.run("gh pr edit 5 --body-file=body.md", world.toolkit) is True


def test_only_the_body_file_argument_is_read_as_a_file(world):
    (world.toolkit / "body.md").write_text("bumped a limit to unblock recovery\n", encoding="utf-8")
    (world.toolkit / "other.md").write_text(f"notes about {PRIVATE_NAME}\n", encoding="utf-8")
    assert world.run("gh pr edit 5 --body-file body.md --add-label other.md", world.toolkit) is False


def test_clean_body_file_is_allowed(world):
    (world.toolkit / "body.md").write_text("bumped a limit to unblock recovery\n", encoding="utf-8")
    assert world.run("gh pr edit 5 --body-file body.md", world.toolkit) is False


def test_cd_prefix_unquoted_picks_the_repo(world):
    assert world.run(f"cd {world.toolkit} && git commit -m '{PRIVATE_NAME}'", world.elsewhere) is True


def test_cd_prefix_quoted_picks_the_repo(world):
    assert world.run(f'cd "{world.toolkit}" && git commit -m "{PRIVATE_NAME}"', world.elsewhere) is True


def test_cd_prefix_with_semicolon_picks_the_repo(world):
    assert world.run(f"cd {world.toolkit} ; git commit -m '{PRIVATE_NAME}'", world.elsewhere) is True


@pytest.mark.parametrize("quote", ['"', ""])
def test_git_dash_c_picks_the_repo(world, quote):
    command = f"git -C {quote}{world.toolkit}{quote} status; git commit -m '{PRIVATE_NAME}'"
    assert world.run(command, world.elsewhere) is True


def test_same_command_outside_a_toolkit_repo_is_allowed(world):
    assert world.run(f"git commit -m '{PRIVATE_NAME}'", world.elsewhere) is False


@pytest.mark.parametrize("only", ["agents", "skills"])
def test_directory_with_one_of_agents_or_skills_is_not_a_toolkit(world, only):
    half = world.elsewhere / "half"
    (half / only).mkdir(parents=True)
    assert world.run(f"git commit -m '{PRIVATE_NAME}'", half) is False


def test_short_names_and_dot_prefixed_agent_stems_never_block(world):
    assert world.run("git commit -m 'abc fixed, .hidden-fixture also fine'", world.toolkit) is False
    assert world.run(f"git commit -m '{PRIVATE_NAME}'", world.toolkit) is True


def test_public_homonym_in_list_form_index_is_allowed(world):
    index = {"skills": [{"name": HOMONYM}, {"other": "entry without a name"}, "not-a-dict"]}
    (world.toolkit / "skills" / "INDEX.json").write_text(json.dumps(index), encoding="utf-8")
    assert world.run(f"git commit -m 'uses {HOMONYM}'", world.toolkit) is False
    assert world.run(f"git commit -m '{PRIVATE_NAME}'", world.toolkit) is True
