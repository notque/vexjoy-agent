#!/usr/bin/env python3
"""Decision tests for pretool-review-before-push-gate, end to end on real git repos.

Each test builds throwaway repos, points HOME at a temp dir (records and the
fork cache live under it), and puts a fake `gh` first on PATH that logs every
call and answers isFork from a file.

Run with: python3 -m pytest hooks/tests/test_pretool_review_before_push_gate.py -v
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
HOOK = ROOT / "hooks" / "pretool-review-before-push-gate.py"
SCRIPT = ROOT / "scripts" / "review-record.py"
GIT_DIR = str(Path(shutil.which("git") or "/usr/bin/git").parent)

FAKE_GH = """#!/bin/sh
echo "$@" >> "$FAKE_GH_DIR/calls"
if [ "$1 $2" = "repo view" ]; then
  [ -f "$FAKE_GH_DIR/fork" ] || exit 1
  cat "$FAKE_GH_DIR/fork"
  exit 0
fi
exit 0
"""

_spec = importlib.util.spec_from_file_location("review_gate", HOOK)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


def _git(cwd: Path, *args: str) -> str:
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True, env=env).stdout.strip()


def make_repo(path: Path, remotes: dict[str, str]) -> Path:
    path.mkdir(parents=True)
    _git(path, "init", "-q", "-b", "main")
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "t")
    (path / "a.txt").write_text("one\n")
    _git(path, "add", "a.txt")
    _git(path, "commit", "-q", "-m", "one")
    for name, url in remotes.items():
        _git(path, "remote", "add", name, url)
    return path


def commit(path: Path, text: str) -> str:
    (path / "a.txt").write_text(text)
    _git(path, "commit", "-q", "-am", text)
    return _git(path, "rev-parse", "HEAD")


class Env:
    """HOME, fake gh, and helpers to run the hook and the record script."""

    def __init__(self, tmp: Path):
        self.tmp = tmp
        self.home = tmp / "home"
        self.home.mkdir()
        self.ghdir = tmp / "gh"
        self.ghdir.mkdir()
        self.bin = tmp / "bin"
        self.bin.mkdir()
        gh = self.bin / "gh"
        gh.write_text(FAKE_GH)
        gh.chmod(0o755)

    def env(self, *, with_gh: bool = True, extra: dict[str, str] | None = None) -> dict[str, str]:
        path = f"{self.bin}:{GIT_DIR}:/usr/bin:/bin" if with_gh else f"{GIT_DIR}:/usr/bin:/bin"
        env = {
            "HOME": str(self.home),
            "PATH": path,
            "FAKE_GH_DIR": str(self.ghdir),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
        }
        env.update(extra or {})
        return env

    def fork_answer(self, answer: str | None) -> None:
        f = self.ghdir / "fork"
        if answer is None:
            f.unlink(missing_ok=True)
        else:
            f.write_text(answer + "\n")

    def gh_calls(self) -> list[str]:
        f = self.ghdir / "calls"
        return f.read_text().splitlines() if f.exists() else []

    def run(self, command: str, cwd: Path, **kw) -> subprocess.CompletedProcess:
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd)})
        return subprocess.run(
            [sys.executable, str(HOOK)],
            input=payload,
            capture_output=True,
            text=True,
            env=self.env(**kw),
            timeout=30,
        )

    def mark(self, repo: Path, sha: str = "HEAD", critical: int = 0, important: int = 0) -> subprocess.CompletedProcess:
        findings = self.tmp / f"findings-{time.monotonic_ns()}.md"
        findings.write_text("## Critical\nnone\n## Important\nnone\n")
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "mark",
                "--findings-file",
                str(findings),
                "--repo-dir",
                str(repo),
                "--sha",
                sha,
                "--summary",
                "test review clean",
                "--critical",
                str(critical),
                "--important",
                str(important),
            ],
            capture_output=True,
            text=True,
            env=self.env(),
            timeout=30,
        )


def denied(proc: subprocess.CompletedProcess) -> str | None:
    """The deny reason, or None when the hook allowed the command."""
    assert proc.returncode == 0, proc.stderr
    if not proc.stdout.strip():
        return None
    out = json.loads(proc.stdout)
    hso = out["hookSpecificOutput"]
    assert hso["hookEventName"] == "PreToolUse"
    assert hso["permissionDecision"] == "deny"
    return hso["permissionDecisionReason"]


@pytest.fixture
def env(tmp_path: Path) -> Env:
    return Env(tmp_path)


@pytest.fixture
def sapcc(env: Env) -> Path:
    return make_repo(env.tmp / "sapcc-repo", {"origin": "https://github.com/sapcc/limes.git"})


@pytest.fixture
def mine(env: Env) -> Path:
    env.fork_answer("false")
    return make_repo(env.tmp / "mine-repo", {"origin": "git@github.com:notque/vexjoy-agent.git"})


# --------------------------------------------------------------------------
# Classification
# --------------------------------------------------------------------------


class TestClassification:
    def test_sapcc_target_is_denied_without_calling_gh(self, env: Env, sapcc: Path):
        reason = denied(env.run("git push", sapcc))
        assert reason and "not a github.com/notque repo" in reason
        assert env.gh_calls() == []  # no network for clearly non-notque remotes

    def test_notque_non_fork_is_allowed_and_cached(self, env: Env, mine: Path):
        assert denied(env.run("git push", mine)) is None
        assert denied(env.run("git push origin main", mine)) is None
        assert env.gh_calls() == ["repo view notque/vexjoy-agent --json isFork --jq .isFork"]

    def test_fork_detected_from_other_remote_without_gh(self, env: Env):
        repo = make_repo(
            env.tmp / "ceph",
            {"origin": "https://github.com/ceph/ceph.git", "fork": "https://github.com/notque/ceph.git"},
        )
        reason = denied(env.run("git push fork HEAD", repo))
        assert reason and "non-notque remote" in reason and "fork" in reason
        assert env.gh_calls() == []

    def test_fork_detected_by_gh(self, env: Env):
        env.fork_answer("true")
        repo = make_repo(env.tmp / "perses", {"origin": "https://github.com/notque/perses"})
        reason = denied(env.run("git push", repo))
        assert reason and "notque/perses is a fork" in reason

    def test_unknown_fork_status_is_not_mine_and_not_cached(self, env: Env):
        env.fork_answer(None)  # fake gh exits 1
        repo = make_repo(env.tmp / "x", {"origin": "https://github.com/notque/x.git"})
        assert "could not confirm" in denied(env.run("git push", repo))
        denied(env.run("git push", repo))
        assert len(env.gh_calls()) == 2

    def test_missing_gh_binary_is_not_mine(self, env: Env):
        repo = make_repo(env.tmp / "x", {"origin": "https://github.com/notque/x.git"})
        assert "could not confirm" in denied(env.run("git push", repo, with_gh=False))

    def test_disabled_push_url_is_not_mine(self, env: Env, mine: Path):
        _git(mine, "remote", "set-url", "--push", "origin", "DISABLED")
        assert denied(env.run("git push", mine))

    def test_insteadof_rewrite_is_followed(self, env: Env, mine: Path):
        _git(mine, "remote", "set-url", "origin", "gh:sapcc/limes")
        _git(mine, "config", "url.https://github.com/.insteadOf", "gh:")
        assert "not a github.com/notque" in denied(env.run("git push", mine))

    def test_local_path_push_is_allowed(self, env: Env, sapcc: Path):
        bare = env.tmp / "bare.git"
        assert denied(env.run(f"git push {bare} main", sapcc)) is None

    @pytest.mark.parametrize(
        ("url", "slug"),
        [
            ("https://github.com/notque/x.git", ("github.com", "notque", "x")),
            ("git@github.com:notque/x", ("github.com", "notque", "x")),
            ("ssh://git@github.com:22/sapcc/limes.git", ("github.com", "sapcc", "limes")),
            ("git@github.wdf.sap.corp:cc/secrets.git", ("github.wdf.sap.corp", "cc", "secrets")),
            ("github-alias:notque/x", ("github-alias", "notque", "x")),
            ("DISABLED", None),
        ],
    )
    def test_parse_slug(self, url, slug):
        assert gate.parse_slug(url) == slug


# --------------------------------------------------------------------------
# Command forms
# --------------------------------------------------------------------------


class TestPushForms:
    @pytest.mark.parametrize(
        "template",
        [
            "git push",
            "git push -u origin main",
            "git push --force-with-lease origin HEAD:refs/heads/feat",
            "git status && git push origin main",
            "echo start; git push 2>&1 | tail -1",
            "git add a.txt\ngit push",
            "bash -c 'git push origin main'",
            "REVIEW_PUSH_GATE_BYPASS=1 git push",
            "CLAUDE_GATE_BYPASS=1 git push -u origin main",
            "env FOO=1 command git push",
            # a redirect target must not be read as a local-path remote
            "git push > /tmp/push.log 2>&1",
            "git push >/tmp/push.log",
        ],
    )
    def test_push_in_cwd_is_gated(self, env: Env, sapcc: Path, template: str):
        assert denied(env.run(template, sapcc))

    def test_git_dash_c_targets_that_dir(self, env: Env, sapcc: Path):
        assert denied(env.run(f"git -C {sapcc} push", env.tmp))

    def test_cd_then_push_targets_that_dir(self, env: Env, sapcc: Path):
        assert denied(env.run(f"cd {sapcc} && git push origin main", env.tmp))

    def test_subshell_cd_does_not_leak(self, env: Env, sapcc: Path, mine: Path):
        assert denied(env.run(f"(cd {sapcc}) && git push", mine)) is None

    @pytest.mark.parametrize(
        "command",
        [
            'git commit -m "push the fix"',
            "git stash push -m wip",
            "gh pr ready 12",
            "gh pr edit 5 --title t",
            "git log --grep push",
            "echo 'gh pr create'",
            "git status",
            "gh pr view 12",
            "ls -la",
        ],
    )
    def test_non_gated_commands_pass_silently(self, env: Env, sapcc: Path, command: str):
        proc = env.run(command, sapcc)
        assert denied(proc) is None
        assert proc.stderr == ""

    def test_dry_run_and_delete_pass(self, env: Env, sapcc: Path):
        assert denied(env.run("git push --dry-run origin main", sapcc)) is None
        assert denied(env.run("git push origin --delete old-branch", sapcc)) is None

    def test_push_all_is_denied_even_with_record(self, env: Env, sapcc: Path):
        assert env.mark(sapcc).returncode == 0
        assert "push one reviewed ref" in denied(env.run("git push --all origin", sapcc))

    def test_parse_invocations_tracks_cwd(self, tmp_path: Path):
        (tmp_path / "sub").mkdir()
        (tmp_path / "other").mkdir()
        invs = gate.parse_invocations("cd sub && git -C ../other push -u origin x; gh -R a/b pr create", str(tmp_path))
        assert [(i.kind, i.cwd, i.problem) for i in invs] == [
            ("push", str(tmp_path / "other"), ""),
            ("gh-create", str(tmp_path / "sub"), ""),
        ]


class TestGhPr:
    def test_create_with_repo_flag_targets_that_repo(self, env: Env, mine: Path):
        reason = denied(env.run("gh pr create --repo sapcc/limes --title t --body-file b.md", mine))
        assert reason and "gh pr create" in reason and "sapcc/limes" in reason

    def test_create_with_repo_flag_for_mine(self, env: Env, mine: Path):
        assert denied(env.run("gh pr create --repo notque/vexjoy-agent --fill", mine)) is None

    def test_create_head_checks_that_branch(self, env: Env, sapcc: Path):
        assert env.mark(sapcc).returncode == 0
        _git(sapcc, "checkout", "-q", "-b", "feat")
        feat = commit(sapcc, "two")
        _git(sapcc, "checkout", "-q", "main")
        reason = denied(env.run("gh pr create --repo sapcc/limes --head notque:feat --fill", sapcc))
        assert reason and feat[:12] in reason
        assert env.mark(sapcc, sha="feat").returncode == 0
        assert denied(env.run("gh pr create --repo sapcc/limes --head notque:feat --fill", sapcc)) is None

    @pytest.mark.parametrize(
        "command",
        ["gh pr edit 5 --add-label x", "gh pr edit --title t --body-file b.md", "gh pr edit 5 --add-reviewer bob"],
    )
    def test_metadata_only_edit_passes_without_record(self, env: Env, sapcc: Path, command: str):
        assert denied(env.run(command, sapcc)) is None

    @pytest.mark.parametrize(
        "command",
        [
            "gh pr edit 5 --base main",
            "gh pr edit 5 -B main",
            "gh pr edit --base=dev",
            "gh pr create --draft --fill",
        ],
    )
    def test_edit_ready_create_need_record(self, env: Env, sapcc: Path, command: str):
        assert denied(env.run(command, sapcc))
        assert env.mark(sapcc).returncode == 0
        assert denied(env.run(command, sapcc)) is None


# --------------------------------------------------------------------------
# Review records
# --------------------------------------------------------------------------


class TestRecords:
    def test_record_for_head_allows_push(self, env: Env, sapcc: Path):
        assert env.mark(sapcc).returncode == 0
        assert denied(env.run("git push -u origin main", sapcc)) is None
        assert denied(env.run(f"git -C {sapcc} push", env.tmp)) is None

    def test_stale_record_fails_after_fix_commit(self, env: Env, sapcc: Path):
        assert env.mark(sapcc).returncode == 0
        new = commit(sapcc, "fix delta")
        reason = denied(env.run("git push", sapcc))
        assert reason and new[:12] in reason

    def test_record_from_another_repo_fails(self, env: Env, sapcc: Path):
        clone = env.tmp / "clone"
        _git(env.tmp, "clone", "-q", str(sapcc), str(clone))
        _git(clone, "remote", "set-url", "origin", "https://github.com/sapcc/limes.git")
        assert env.mark(sapcc).returncode == 0  # same SHA, other repo
        assert denied(env.run("git push origin main", clone))

    def test_copied_record_file_fails(self, env: Env, sapcc: Path):
        clone = env.tmp / "clone"
        _git(env.tmp, "clone", "-q", str(sapcc), str(clone))
        _git(clone, "remote", "set-url", "origin", "https://github.com/sapcc/limes.git")
        out = json.loads(env.mark(sapcc).stdout)
        src = Path(out["path"])
        import hashlib

        key = hashlib.sha256(os.path.realpath(clone / ".git").encode()).hexdigest()[:16]
        dst = src.parent.parent / key / src.name
        dst.parent.mkdir(parents=True)
        shutil.copy(src, dst)
        assert denied(env.run("git push origin main", clone))

    def test_worktree_shares_records_with_its_clone(self, env: Env, sapcc: Path):
        wt = env.tmp / "wt"
        _git(sapcc, "worktree", "add", "-q", "-b", "feat", str(wt))
        assert env.mark(wt).returncode == 0
        assert denied(env.run("git push -u origin feat", wt)) is None

    def test_record_with_open_findings_is_refused(self, env: Env, sapcc: Path):
        proc = env.mark(sapcc, important=1)
        assert proc.returncode == 1 and "refused" in proc.stderr
        assert denied(env.run("git push", sapcc))

    def test_bypass_env_in_hook_process_allows_and_logs(self, env: Env, sapcc: Path):
        proc = env.run("git push", sapcc, extra={"REVIEW_PUSH_GATE_BYPASS": "1"})
        assert denied(proc) is None
        assert "BYPASSED" in proc.stderr
        log = (env.home / ".claude" / "state" / "review-gate" / "bypass.log").read_text()
        assert "git push" in log


# --------------------------------------------------------------------------
# Output contract and robustness
# --------------------------------------------------------------------------


class TestContract:
    def test_deny_message_says_what_to_do(self, env: Env, sapcc: Path):
        head = _git(sapcc, "rev-parse", "HEAD")
        proc = env.run("git push", sapcc)
        out = json.loads(proc.stdout)
        assert set(out) == {"hookSpecificOutput"}
        reason = out["hookSpecificOutput"]["permissionDecisionReason"]
        assert head[:12] in reason
        for needle in (
            "/pr-review",
            "local commit",
            "Critical and Important",
            "retry the push",
        ):
            assert needle in reason

    def test_deny_message_in_antigravity_runtime(self, env: Env, sapcc: Path):
        head = _git(sapcc, "rev-parse", "HEAD")
        antigravity_env = {**env.env(), "VEXJOY_HOOK_RUNTIME": "antigravity"}
        proc = subprocess.run(
            [sys.executable, str(HOOK)],
            input=json.dumps({"tool_name": "run_command", "tool_input": {"command": "git push"}}),
            capture_output=True,
            text=True,
            env=antigravity_env,
            cwd=str(sapcc),
            timeout=15,
        )
        out = json.loads(proc.stdout)
        reason = out["hookSpecificOutput"]["permissionDecisionReason"]
        assert head[:12] in reason
        assert ".gemini/scripts/review-record.py" in reason
        assert "/do review" in reason
        assert "run /pr-review" not in reason

    @pytest.mark.parametrize("stdin", ["", "not json", "[]", '{"tool_input": "x"}', '{"tool_input": {"command": 5}}'])
    def test_bad_input_exits_zero_silently(self, env: Env, stdin: str):
        proc = subprocess.run(
            [sys.executable, str(HOOK)], input=stdin, capture_output=True, text=True, env=env.env(), timeout=15
        )
        assert proc.returncode == 0 and proc.stdout == ""

    def test_unparseable_push_fails_closed(self, env: Env, sapcc: Path):
        assert "could not parse" in denied(env.run("git push origin 'main", sapcc))

    def test_not_a_repo_fails_closed(self, env: Env):
        plain = env.tmp / "plain"
        plain.mkdir()
        assert denied(env.run("gh pr create --repo sapcc/limes --fill", plain))

    def test_speed_non_gated_and_deny(self, env: Env, sapcc: Path):
        """Non-gated commands return in interpreter-startup time; a deny needs no network."""

        def median(command: str) -> float:
            times = []
            for _ in range(5):
                t = time.perf_counter()
                env.run(command, sapcc)
                times.append(time.perf_counter() - t)
            return sorted(times)[2]

        assert median("ls -la") < 0.5
        assert median("git push") < 1.0
        assert env.gh_calls() == []


# --------------------------------------------------------------------------
# Review of 40127d53: every reviewer case
# --------------------------------------------------------------------------

# C1: shell keywords and wrapper commands in front of a HEAD push.
WRAPPED_PUSHES = [
    "if git push; then echo ok; fi",
    "if ! git push origin main; then echo fail; fi",
    "! git push",
    "until git push; do sleep 1; done",
    "while git push; do break; done",
    "for i in 1; do git push; done",
    "timeout 60 git push",
    "timeout 60s git push origin main",
    "timeout -s KILL 60 git push",
    "nice -n 5 git push",
    "nice -5 git push",
    "sudo -E git push",
    "sudo -u me git push",
    "env -u FOO git push",
    "xargs git push < /dev/null",
    "xargs -I{} git push origin {} < /dev/null",
    "caffeinate -i git push",
    "stdbuf -oL git push",
    "time -p git push",
    "unknownwrapper --flag git push origin main",
]


class TestWrappedPushes:
    @pytest.mark.parametrize("command", WRAPPED_PUSHES)
    def test_wrapped_push_is_gated(self, env: Env, sapcc: Path, command: str):
        assert denied(env.run(command, sapcc))

    @pytest.mark.parametrize("command", WRAPPED_PUSHES)
    def test_wrapped_push_of_reviewed_head_passes(self, env: Env, sapcc: Path, command: str):
        assert env.mark(sapcc).returncode == 0
        assert denied(env.run(command, sapcc)) is None

    def test_wrapper_hiding_an_unjudgeable_push_denies(self, env: Env, sapcc: Path):
        assert env.mark(sapcc).returncode == 0
        reason = denied(env.run('git "$SUB" push', sapcc))
        assert reason and "cannot tell which git command" in reason


class TestMatchingPushes:
    """I1: matching refspecs and config-driven pushes send more than HEAD."""

    @pytest.mark.parametrize(
        "command",
        [
            "git push origin :",
            "git push origin +:",
            "git push origin 'refs/heads/*:refs/heads/*'",
            "git -c push.default=matching push",
            "git -c remote.origin.push=refs/heads/*:refs/heads/* push origin",
            "git -c remote.origin.push=refs/heads/other:refs/heads/other push",
        ],
    )
    def test_denied_even_with_head_reviewed(self, env: Env, sapcc: Path, command: str):
        assert env.mark(sapcc).returncode == 0
        assert "push one reviewed ref by name" in denied(env.run(command, sapcc))

    def test_configured_remote_push_is_denied(self, env: Env, sapcc: Path):
        assert env.mark(sapcc).returncode == 0
        _git(sapcc, "config", "remote.origin.push", "refs/heads/*:refs/heads/*")
        assert denied(env.run("git push", sapcc))
        assert denied(env.run("git push origin main", sapcc)) is None


class TestGitDirEnv:
    """I2: GIT_DIR/GIT_WORK_TREE point the push at another repo."""

    @pytest.mark.parametrize(
        "template",
        [
            "GIT_DIR={git} git push origin main",
            "export GIT_DIR={git}; git push origin main",
            "GIT_DIR={git}; export GIT_DIR; git push origin main",
            "env GIT_DIR={git} git push origin main",
            "GIT_DIR={git} GIT_WORK_TREE={wt} git push origin main",
        ],
    )
    def test_git_dir_targets_that_repo(self, env: Env, sapcc: Path, mine: Path, template: str):
        command = template.format(git=sapcc / ".git", wt=sapcc)
        reason = denied(env.run(command, mine))
        assert reason and "sapcc/limes" in reason

    def test_subshell_export_does_not_leak(self, env: Env, sapcc: Path, mine: Path):
        assert denied(env.run(f"(export GIT_DIR={sapcc / '.git'}); git push", mine)) is None


class TestDeadline:
    """I3: a hanging gh cannot run the hook past its timeout."""

    def test_hanging_gh_is_called_once_and_denies_in_time(self, env: Env, sapcc: Path):
        (env.bin / "gh").write_text('#!/bin/sh\necho "$@" >> "$FAKE_GH_DIR/calls"\nsleep 30\n')
        repo = make_repo(env.tmp / "x", {"origin": "https://github.com/notque/x.git"})
        assert env.mark(repo).returncode == 0  # unknown fork status, so each push needs the record and passes
        command = f"git push origin main; git push origin main; git push origin main; git -C {sapcc} push origin main"
        t = time.monotonic()
        reason = denied(env.run(command, repo))
        assert time.monotonic() - t < 8
        assert reason
        assert len(env.gh_calls()) == 1


class TestRecordProof:
    """I4: records need a findings file; the deny text does not print the mark command."""

    def test_deny_text_does_not_print_mark(self, env: Env, sapcc: Path):
        reason = denied(env.run("git push", sapcc))
        assert "review-record.py" not in reason and " mark" not in reason

    def test_version_1_record_without_findings_hash_fails(self, env: Env, sapcc: Path):
        out = json.loads(env.mark(sapcc).stdout)
        path = Path(out["path"])
        data = json.loads(path.read_text())
        data.pop("findings_sha256")
        data["version"] = 1
        path.write_text(json.dumps(data))
        assert denied(env.run("git push", sapcc))


class TestUnresolvedDirs:
    """I6 and S1: an unknown directory is a plain deny, a crash is a deny."""

    @pytest.mark.parametrize(
        "command",
        [
            'cd "$(git rev-parse --show-toplevel)" && git push origin main',
            "cd $(git rev-parse --show-toplevel) && git push origin main",
            "cd - && git push origin main",
            'cd "$REPO" && git push',
            "cd ~nosuchuser123 && git push",
            "cd no-such-dir && git push",
            "git -C $DIR push",
        ],
    )
    def test_unresolved_cd_denies_with_git_dash_c_advice(self, env: Env, mine: Path, command: str):
        reason = denied(env.run(command, mine))
        assert reason and "git -C <dir> push" in reason and "crashed" not in reason

    def test_crash_after_push_match_denies(self, env: Env, sapcc: Path):
        boom = (
            "import shlex, runpy\n"
            "def _boom(*a, **k):\n    raise RuntimeError('boom')\n"
            f"shlex.shlex = _boom\nrunpy.run_path({str(HOOK)!r}, run_name='__main__')\n"
        )
        payload = json.dumps({"tool_input": {"command": "git push"}, "cwd": str(sapcc)})
        proc = subprocess.run(
            [sys.executable, "-c", boom], input=payload, capture_output=True, text=True, env=env.env(), timeout=15
        )
        assert "crashed" in denied(proc)


class TestSuggestions:
    def test_attached_push_option_is_not_read_as_flags(self, env: Env, sapcc: Path):
        """S2: -oskipdeploy holds d and n but is not --delete or --dry-run."""
        assert denied(env.run("git push -oskipdeploy origin main", sapcc))
        assert denied(env.run("git push -fo ci.skip origin main", sapcc))

    def test_subtree_push_is_gated(self, env: Env, sapcc: Path):
        """S3."""
        assert denied(env.run("git subtree push --prefix=x origin main", sapcc))
        assert env.mark(sapcc).returncode == 0
        assert denied(env.run("git subtree push --prefix=x origin main", sapcc)) is None

    def test_gh_pr_create_follows_insteadof(self, env: Env, mine: Path):
        """S5: gh sees the same rewritten URL as git push."""
        _git(mine, "remote", "set-url", "origin", "gh:notque/vexjoy-agent")
        _git(mine, "config", "url.https://github.com/.insteadOf", "gh:")
        assert denied(env.run("git push", mine)) is None
        assert denied(env.run("gh pr create --fill", mine)) is None

    def test_gh_pr_ready_is_not_gated(self, env: Env, sapcc: Path):
        """S6."""
        assert denied(env.run("gh pr ready 123", sapcc)) is None


class TestSubstitutions:
    @pytest.mark.parametrize("command", ['eval "git push"', 'echo "$(git push)"', 'echo "`git push`"', "eval git push"])
    def test_eval_and_substitution_are_parsed(self, env: Env, sapcc: Path, command: str):
        assert denied(env.run(command, sapcc))
        assert env.mark(sapcc).returncode == 0
        assert denied(env.run(command, sapcc)) is None

    def test_substitution_in_commit_message_is_not_a_push(self, env: Env, sapcc: Path):
        assert denied(env.run('git commit -m "explain $(date) push"', sapcc)) is None
