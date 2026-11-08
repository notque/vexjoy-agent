#!/usr/bin/env python3
"""Private-repo exemption tests for pretool-private-name-leak-gate.

The owner (2026-11-08): private name checks don't count for private repos.
The gate allows a matched term only when every repo the text can reach is a
private GitHub repo, as reported by `gh api repos/OWNER/REPO --jq .private`.
A fake `gh` on PATH answers from a JSON map and logs each call, so no test
touches the network. All names are synthetic.

Run with: python3 -m pytest hooks/tests/test_pretool_private_name_leak_gate_private_repo.py -v
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK_PATH = Path(__file__).parent.parent / "pretool-private-name-leak-gate.py"
PRIVATE_NAME = "secret-example-skill"
LEAK = f'git commit -m "mention {PRIVATE_NAME}"'

FAKE_GH = r"""#!/usr/bin/env python3
import json, os, sys
with open(os.environ["FAKE_GH_LOG"], "a") as log:
    log.write(" ".join(sys.argv[1:]) + "\n")
answers = json.loads(os.environ.get("FAKE_GH_MAP", "{}"))
slug = next((a[len("repos/"):] for a in sys.argv if a.startswith("repos/")), "")
if slug not in answers:
    sys.exit(1)
print(answers[slug])
"""


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


class World:
    def __init__(self, root: Path):
        self.home = root / "home"
        skill = self.home / "private-skills" / PRIVATE_NAME
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(f"---\nname: {PRIVATE_NAME}\n---\n", encoding="utf-8")
        self.repo = root / "toolkit"
        (self.repo / "agents").mkdir(parents=True)
        (self.repo / "skills").mkdir()
        _git(self.repo, "init", "-q", "-b", "main")
        bindir = root / "bin"
        bindir.mkdir()
        gh = bindir / "gh"
        gh.write_text(FAKE_GH, encoding="utf-8")
        gh.chmod(0o755)
        self.bindir = bindir
        self.log = root / "gh.log"
        self.answers: dict[str, str] = {}

    def remote(self, name: str, url: str) -> None:
        _git(self.repo, "remote", "add", name, url)

    def gh_calls(self) -> list[str]:
        return self.log.read_text().splitlines() if self.log.exists() else []

    def denied(self, command: str) -> bool:
        env = {k: v for k, v in os.environ.items() if k not in ("PRIVATE_NAME_GATE_BYPASS", "CLAUDE_PROJECT_DIR")}
        env.update(
            HOME=str(self.home),
            PATH=f"{self.bindir}{os.pathsep}{env.get('PATH', '')}",
            FAKE_GH_LOG=str(self.log),
            FAKE_GH_MAP=json.dumps(self.answers),
        )
        event = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(self.repo)}
        proc = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input=json.dumps(event),
            capture_output=True,
            text=True,
            env=env,
            cwd=self.repo,
            timeout=60,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        assert PRIVATE_NAME not in proc.stderr + proc.stdout
        if not proc.stdout.strip():
            return False
        return json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.fixture
def world(tmp_path: Path) -> World:
    return World(tmp_path)


def test_private_origin_allows_commit(world):
    world.remote("origin", "git@github.com:someone/closed.git")
    world.answers = {"someone/closed": "true"}
    assert not world.denied(LEAK)
    assert world.gh_calls() == ["api repos/someone/closed --jq .private"]


def test_public_origin_still_blocks(world):
    world.remote("origin", "https://github.com/someone/open.git")
    world.answers = {"someone/open": "false"}
    assert world.denied(LEAK)


def test_no_remote_blocks_without_calling_gh(world):
    assert world.denied(LEAK)
    assert world.gh_calls() == []


def test_gh_error_blocks(world):
    world.remote("origin", "git@github.com:someone/unknown.git")
    assert world.denied(LEAK)


def test_non_github_remote_blocks(world, tmp_path):
    world.remote("origin", str(tmp_path / "bare.git"))
    assert world.denied(LEAK)
    assert world.gh_calls() == []


def test_commit_needs_every_remote_private(world):
    world.remote("origin", "git@github.com:someone/closed.git")
    world.remote("upstream", "https://github.com/someone/open")
    world.answers = {"someone/closed": "true", "someone/open": "false"}
    assert world.denied(LEAK)


def test_push_checks_only_the_named_remote(world):
    world.remote("origin", "git@github.com:someone/closed.git")
    world.remote("upstream", "https://github.com/someone/open")
    world.answers = {"someone/closed": "true", "someone/open": "false"}
    assert not world.denied(f"git push origin main # {PRIVATE_NAME}")
    assert world.denied(f"git push upstream main # {PRIVATE_NAME}")


def test_push_to_unknown_name_blocks(world):
    world.remote("origin", "git@github.com:someone/closed.git")
    world.answers = {"someone/closed": "true"}
    assert world.denied(f"git push elsewhere main # {PRIVATE_NAME}")


def test_commit_and_push_chain_checks_all_remotes(world):
    world.remote("origin", "git@github.com:someone/closed.git")
    world.remote("upstream", "https://github.com/someone/open")
    world.answers = {"someone/closed": "true", "someone/open": "false"}
    assert world.denied(f"{LEAK} && git push origin main")


def test_gh_pr_repo_flag_decides(world):
    world.remote("origin", "https://github.com/someone/open")
    world.answers = {"someone/open": "false", "someone/closed": "true"}
    assert not world.denied(f'gh pr comment 1 -R someone/closed --body "{PRIVATE_NAME}"')
    assert world.denied(f'gh pr comment 1 --repo someone/open --body "{PRIVATE_NAME}"')
    assert world.denied(f'gh pr comment 1 --body "{PRIVATE_NAME}"')


def test_enterprise_host_passes_hostname(world):
    world.remote("origin", "git@ghe.example.com:team/closed.git")
    world.answers = {"team/closed": "true"}
    assert not world.denied(LEAK)
    assert world.gh_calls() == ["api --hostname ghe.example.com repos/team/closed --jq .private"]


def test_clean_command_never_calls_gh(world):
    world.remote("origin", "git@github.com:someone/closed.git")
    world.answers = {"someone/closed": "true"}
    assert not world.denied('git commit -m "nothing private here"')
    assert world.gh_calls() == []
