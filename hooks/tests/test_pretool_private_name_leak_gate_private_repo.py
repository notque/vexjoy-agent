#!/usr/bin/env python3
"""Private-repo exemption tests for pretool-private-name-leak-gate.

The owner (2026-11-08): private name checks don't count for private repos.
The gate allows a matched term only when every repo the text can reach is a
private GitHub repo, as reported by `gh api --hostname HOST repos/OWNER/REPO --jq .visibility`.
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

    def denied(self, command: str, **extra_env: str) -> bool:
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("PRIVATE_NAME_GATE_BYPASS", "CLAUDE_PROJECT_DIR") and not k.startswith(("GIT_", "GH_"))
        }
        env.update(extra_env)
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
    world.answers = {"someone/closed": "private"}
    assert not world.denied(LEAK)
    assert world.gh_calls() == ["api --hostname github.com repos/someone/closed --jq .visibility"]


def test_public_origin_still_blocks(world):
    world.remote("origin", "https://github.com/someone/open.git")
    world.answers = {"someone/open": "public"}
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
    world.answers = {"someone/closed": "private", "someone/open": "public"}
    assert world.denied(LEAK)


def test_push_checks_only_the_named_remote(world):
    world.remote("origin", "git@github.com:someone/closed.git")
    world.remote("upstream", "https://github.com/someone/open")
    world.answers = {"someone/closed": "private", "someone/open": "public"}
    assert not world.denied(f"git push origin main # {PRIVATE_NAME}")
    assert world.denied(f"git push upstream main # {PRIVATE_NAME}")


def test_push_to_unknown_name_blocks(world):
    world.remote("origin", "git@github.com:someone/closed.git")
    world.answers = {"someone/closed": "private"}
    assert world.denied(f"git push elsewhere main # {PRIVATE_NAME}")


def test_commit_and_push_chain_checks_all_remotes(world):
    world.remote("origin", "git@github.com:someone/closed.git")
    world.remote("upstream", "https://github.com/someone/open")
    world.answers = {"someone/closed": "private", "someone/open": "public"}
    assert world.denied(f"{LEAK} && git push origin main")


def test_gh_pr_repo_flag_decides(world):
    world.remote("origin", "https://github.com/someone/open")
    world.answers = {"someone/open": "public", "someone/closed": "private"}
    assert not world.denied(f'gh pr comment 1 -R someone/closed --body "{PRIVATE_NAME}"')
    assert world.denied(f'gh pr comment 1 --repo someone/open --body "{PRIVATE_NAME}"')
    assert world.denied(f'gh pr comment 1 --body "{PRIVATE_NAME}"')


def test_enterprise_host_passes_hostname(world):
    world.remote("origin", "git@ghe.example.com:team/closed.git")
    world.answers = {"team/closed": "private"}
    assert not world.denied(LEAK)
    assert world.gh_calls() == ["api --hostname ghe.example.com repos/team/closed --jq .visibility"]


def test_clean_command_never_calls_gh(world):
    world.remote("origin", "git@github.com:someone/closed.git")
    world.answers = {"someone/closed": "private"}
    assert not world.denied('git commit -m "nothing private here"')
    assert world.gh_calls() == []


@pytest.fixture
def mixed(world, tmp_path):
    """origin is private, pub is public, and /other is a second repo."""
    world.remote("origin", "git@github.com:someone/closed.git")
    world.remote("pub", "https://github.com/someone/open")
    world.answers = {"someone/closed": "private", "someone/open": "public"}
    other = tmp_path / "other"
    (other / "agents").mkdir(parents=True)
    (other / "skills").mkdir()
    _git(other, "init", "-q", "-b", "main")
    _git(other, "remote", "add", "origin", "https://github.com/someone/open")
    world.other = other
    return world


@pytest.mark.parametrize(
    "command",
    [
        f"git push origin & git push pub main # {PRIVATE_NAME}",
        f"git push origin main | git push pub main # {PRIVATE_NAME}",
        f"git push origin main $(git push pub main) # {PRIVATE_NAME}",
        f"git push origin main `git push pub main` # {PRIVATE_NAME}",
        f"git push origin main\rgit push pub main # {PRIVATE_NAME}",
        f"git push origin main\ngit push pub main # {PRIVATE_NAME}",
        f"git push --repo=origin pub main # {PRIVATE_NAME}",
        f"git -c remote.origin.pushurl=https://github.com/someone/open.git push origin main # {PRIVATE_NAME}",
        f"GIT_CONFIG_COUNT=1 git push origin main # {PRIVATE_NAME}",
        f"git --git-dir=/elsewhere/.git push origin main # {PRIVATE_NAME}",
        f"git -C /elsewhere push origin main # {PRIVATE_NAME}",
        f"git commit -m x && (cd /elsewhere && git push) # {PRIVATE_NAME}",
        f"pushd /elsewhere && git push # {PRIVATE_NAME}",
        f"env -C /elsewhere git push # {PRIVATE_NAME}",
        f'gh pr comment https://github.com/someone/open/pull/1 --body "{PRIVATE_NAME}"',
        f'gh pr comment 1 -Rsomeone/open --body "{PRIVATE_NAME}"',
        f'GH_REPO=someone/open gh pr create --body "{PRIVATE_NAME}"',
        f'gh pr comment 1 --body "{PRIVATE_NAME}"',
        f"{{ cd /elsewhere; git push; }} # {PRIVATE_NAME}",
        f"if true; then cd /elsewhere; fi; git push # {PRIVATE_NAME}",
        f"git config remote.origin.pushurl https://github.com/someone/open.git && git push origin main # {PRIVATE_NAME}",
        f"git remote set-url origin https://github.com/someone/open.git && git push # {PRIVATE_NAME}",
        f"git checkout -q feat && git push # {PRIVATE_NAME}",
        f'export GH_REPO=someone/open; gh pr comment 1 --body "{PRIVATE_NAME}"',
        f'git commit -m "x <<EOF"\ncd /elsewhere && git commit -am "{PRIVATE_NAME}" && git push\nEOF',
        f"git push -uo origin https://github.com/someone/open.git main # {PRIVATE_NAME}",
        f"echo x > .git/config && git push origin main # {PRIVATE_NAME}",
        "git" + " -C -x" * 30 + f"; git commit -m '{PRIVATE_NAME}'",
        "git" + ' -C "x"' * 30 + f"; git commit -m '{PRIVATE_NAME}'",
        f"printf x >& .git/config && git push origin main # {PRIVATE_NAME}",
        f"printf x >&.git/config && git push origin main # {PRIVATE_NAME}",
        f"git log -1 --output=.git/config && git push origin main # {PRIVATE_NAME}",
        f"sort -o .git/config /tmp/cfg && git push origin main # {PRIVATE_NAME}",
        f"uniq /tmp/cfg .git/config && git push origin main # {PRIVATE_NAME}",
    ],
)
def test_reviewed_bypass_shapes_still_block(mixed, command):
    assert mixed.denied(command.replace("/elsewhere", str(mixed.other)))


def test_env_redirect_in_hook_environment_blocks(world):
    world.remote("origin", "git@github.com:someone/closed.git")
    world.answers = {"someone/closed": "private"}
    assert world.denied(f"git push origin main # {PRIVATE_NAME}", GH_REPO="someone/open")


def test_internal_visibility_is_not_private(world):
    world.remote("origin", "git@github.com:someone/closed.git")
    world.answers = {"someone/closed": "internal"}
    assert world.denied(LEAK)


def test_pr_url_to_private_repo_allows(mixed):
    assert not mixed.denied(f'gh pr comment https://github.com/someone/closed/pull/1 --body "{PRIVATE_NAME}"')


def test_common_private_shapes_allow(world):
    world.remote("origin", "git@github.com:someone/closed.git")
    world.answers = {"someone/closed": "private"}
    heredoc = f"git commit -F - <<'EOF'\ndon't drop {PRIVATE_NAME} (yet)\nEOF"
    assert not world.denied(heredoc)
    assert not world.denied(f"cd {world.repo} && git push origin main 2>&1 | tail -3 # {PRIVATE_NAME}")
    assert not world.denied(f"git -C {world.repo} commit -m '{PRIVATE_NAME} (a)' && git push origin HEAD")


@pytest.mark.parametrize(
    "command",
    [
        f"git -C {{repo}} commit -m '{PRIVATE_NAME}'",
        f"git -C {{repo}} push origin main # {PRIVATE_NAME}",
        f"git -c core.pager=cat commit -m '{PRIVATE_NAME}'",
        f"git --no-pager commit -m '{PRIVATE_NAME}'",
    ],
)
def test_git_global_options_are_still_gated(world, command):
    """Before 1.4.0 the gate missed `git <global options> commit|push` entirely."""
    world.remote("origin", "https://github.com/someone/open")
    world.answers = {"someone/open": "public"}
    assert world.denied(command.replace("{repo}", str(world.repo)))
