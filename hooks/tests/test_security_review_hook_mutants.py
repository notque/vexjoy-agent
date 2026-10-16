"""Extra security-review-hook tests: path handling, scanner-less fallback, TTL parsing, truncation.

Fixture code is assembled from fragments so this file holds no scanner pattern.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import time
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pytest

HOOKS_DIR = Path(__file__).resolve().parents[1]
HOOK = HOOKS_DIR / "security-review-hook.py"

HIGH_LINE = "os." + "system(cmd)\n"

_spec = importlib.util.spec_from_file_location("security_review_hook_mutants", HOOK)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def _git(repo: Path, *args: str) -> None:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})
    subprocess.run(["git", *args], cwd=repo, env=env, capture_output=True, text=True, check=True)


def _committed_repo(root: Path, name: str, body: str, *, repo_name: str = "repo") -> Path:
    repo = root / repo_name
    repo.mkdir()
    _git(repo, "init", "--quiet", "-b", "main")
    (repo / name).write_text(body, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "--quiet", "-m", "base")
    return repo


def _hook(
    event: dict,
    *,
    home: Path,
    hook: Path = HOOK,
    proc_cwd: str = "/",
    env_extra: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("VEXJOY_SECURITY_REVIEW") and k not in ("CLAUDE_PROJECT_DIR", "CLAUDE_HOOKS_DEBUG")
    }
    env["HOME"] = str(home)
    env.update(env_extra or {})
    return subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        cwd=proc_cwd,
        env=env,
        timeout=60,
        check=False,
    )


def _context(proc: subprocess.CompletedProcess[str]) -> str:
    assert proc.returncode == 0, proc.stderr
    if not proc.stdout.strip():
        return ""
    return json.loads(proc.stdout).get("hookSpecificOutput", {}).get("additionalContext", "") or ""


def _post(file_path: str | None, cwd: Path | None = None) -> dict:
    tool_input = {} if file_path is None else {"file_path": file_path}
    event: dict = {"hook_event_name": "PostToolUse", "tool_name": "Edit", "tool_input": tool_input}
    if cwd is not None:
        event["cwd"] = str(cwd)
    return event


@pytest.fixture
def scannerless_hook(tmp_path: Path) -> Path:
    """A copy of the hook with no scripts/security-review-scan.py reachable."""
    deploy = tmp_path / "deploy" / "hooks"
    deploy.mkdir(parents=True)
    shutil.copy(HOOK, deploy / HOOK.name)
    (deploy / "lib").symlink_to(HOOKS_DIR / "lib")
    return deploy / HOOK.name


# --- PostToolUse path resolution -------------------------------------------------


def test_relative_edit_path_resolves_against_event_cwd(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "x.py").write_text("import os\n" + HIGH_LINE, encoding="utf-8")
    proc = _hook(_post("x.py", project), home=tmp_path)
    assert "potential security finding" in _context(proc)


def test_custom_rules_load_from_event_cwd_not_process_cwd(tmp_path):
    project = tmp_path / "proj"
    (project / ".claude").mkdir(parents=True)
    rules = {"patterns": [{"rule_name": "zzz-custom", "substrings": ["MARKER_TOKEN"]}]}
    (project / ".claude" / "security-patterns.json").write_text(json.dumps(rules), encoding="utf-8")
    target = project / "x.py"
    target.write_text("value = 'MARKER_TOKEN'\n", encoding="utf-8")
    proc = _hook(_post(str(target), project), home=tmp_path)
    assert "zzz-custom" in _context(proc)


def test_edit_event_without_a_path_is_silent_and_clean(tmp_path):
    proc = _hook(_post(None, tmp_path), home=tmp_path)
    assert _context(proc) == ""
    assert "HOOK-ERROR" not in proc.stderr


def test_edit_without_a_reachable_scanner_is_silent_and_clean(tmp_path, scannerless_hook):
    target = tmp_path / "x.py"
    target.write_text(HIGH_LINE, encoding="utf-8")
    proc = _hook(_post(str(target), tmp_path), home=tmp_path, hook=scannerless_hook)
    assert _context(proc) == ""
    assert "HOOK-ERROR" not in proc.stderr


# --- Stop: real diff, scannable extensions ---------------------------------------


def _stop(repo: Path, tmp_path: Path, hook: Path = HOOK) -> subprocess.CompletedProcess[str]:
    return _hook({"hook_event_name": "Stop", "cwd": str(repo)}, home=tmp_path, hook=hook)


def test_stop_rewakes_on_real_working_tree_change(tmp_path):
    repo = _committed_repo(tmp_path, "app.py", "a = 1\n")
    (repo / "app.py").write_text("a = 1\nb = 2\n", encoding="utf-8")
    proc = _stop(repo, tmp_path)
    assert proc.returncode == 2
    assert "+b = 2" in proc.stderr


def test_stop_rewakes_on_added_line_in_a_yaml_file(tmp_path):
    repo = _committed_repo(tmp_path, "ci.yml", "a: 1\n")
    (repo / "ci.yml").write_text("a: 1\nb: 2\n", encoding="utf-8")
    assert _stop(repo, tmp_path).returncode == 2


def test_stop_without_a_reachable_scanner_still_rewakes_on_python_change(tmp_path, scannerless_hook):
    repo = _committed_repo(tmp_path, "app.py", "a = 1\n")
    (repo / "app.py").write_text("a = 1\nb = 2\n", encoding="utf-8")
    assert _stop(repo, tmp_path, scannerless_hook).returncode == 2


# --- Commit gate and switches -----------------------------------------------------


def test_git_dash_c_with_quoted_path_containing_spaces_selects_that_repo(tmp_path):
    repo = _committed_repo(tmp_path, "ok.py", "a = 1\n", repo_name="my repo")
    (repo / "bad.py").write_text("import os\n" + HIGH_LINE, encoding="utf-8")
    _git(repo, "add", "bad.py")
    event = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": f'git -C "{repo}" status && git ' + "commit -m x"},
        "cwd": str(tmp_path),
    }
    proc = _hook(event, home=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def _commit_event() -> dict:
    return {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "git " + "commit -m x"}}


def test_skip_override_is_quiet_unless_debugging(tmp_path):
    quiet = _hook(_commit_event(), home=tmp_path, env_extra={"VEXJOY_SECURITY_REVIEW_SKIP": "1"})
    assert quiet.returncode == 0
    assert quiet.stderr == ""
    loud = _hook(
        _commit_event(),
        home=tmp_path,
        env_extra={"VEXJOY_SECURITY_REVIEW_SKIP": "1", "CLAUDE_HOOKS_DEBUG": "1"},
    )
    assert "Bypassed" in loud.stderr


def test_disable_switch_is_quiet_unless_debugging(tmp_path):
    quiet = _hook(_commit_event(), home=tmp_path, env_extra={"VEXJOY_SECURITY_REVIEW_DISABLE": "1"})
    assert quiet.returncode == 0
    assert quiet.stderr == ""
    loud = _hook(
        _commit_event(),
        home=tmp_path,
        env_extra={"VEXJOY_SECURITY_REVIEW_DISABLE": "1", "CLAUDE_HOOKS_DEBUG": "1"},
    )
    assert "Disabled" in loud.stderr


def test_unrecognised_event_exits_zero(tmp_path):
    proc = _hook({"hook_event_name": "SessionStart"}, home=tmp_path)
    assert proc.returncode == 0
    assert proc.stdout == ""


# --- Stop: dedup TTL parsing and truncation (in-process) -------------------------


def _src_diff(added: str) -> str:
    return (
        "diff --git a/app.py b/app.py\nindex 1111111..2222222 100644\n--- a/app.py\n+++ b/app.py\n"
        f"@@ -1,1 +1,2 @@\n existing\n+{added}\n"
    )


def _run_stop(diff: str, state_dir: Path, env: dict | None = None) -> tuple[int, str, str]:
    base = {k: v for k, v in os.environ.items() if not k.startswith("VEXJOY_SECURITY_REVIEW")}
    base.update(env or {})
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, base, clear=True))
        stack.enter_context(
            patch.object(mod, "read_stdin", return_value=json.dumps({"hook_event_name": "Stop", "cwd": "/repo"}))
        )
        stack.enter_context(patch.object(mod, "_working_tree_diff", return_value=diff))
        stack.enter_context(patch.object(mod, "_STATE_DIR", state_dir))
        stack.enter_context(patch.object(mod, "_STATE_FILE", state_dir / "last-diff-hash.json"))
        stack.enter_context(redirect_stdout(out))
        stack.enter_context(redirect_stderr(err))
        try:
            mod.main()
        except SystemExit as e:
            code = int(e.code) if e.code is not None else 0
    return code, out.getvalue(), err.getvalue()


def _seed_stale(state_dir: Path, diff: str, iso: str = "2020-01-01T00:00:00+00:00") -> None:
    with (
        patch.object(mod, "_STATE_DIR", state_dir),
        patch.object(mod, "_STATE_FILE", state_dir / "last-diff-hash.json"),
    ):
        sig = mod._dedup().signature("/repo", diff)
    (state_dir / "last-diff-hash.json").write_text(
        json.dumps({"hash": sig, "ts": time.time() - 10_000, "ts_iso": iso, "cwd": "/repo"})
    )


@pytest.mark.parametrize("ttl", ["abc", "0", "-5"])
def test_unusable_ttl_means_no_expiry(tmp_path, ttl):
    diff = _src_diff("payload")
    _seed_stale(tmp_path, diff)
    code, _, err = _run_stop(diff, tmp_path, {"VEXJOY_SECURITY_REVIEW_DEDUP_TTL_SECONDS": ttl})
    assert code == 0
    assert "diff unchanged" in err


def test_one_second_ttl_expires_an_old_record(tmp_path):
    diff = _src_diff("payload")
    _seed_stale(tmp_path, diff)
    code, _, _ = _run_stop(diff, tmp_path, {"VEXJOY_SECURITY_REVIEW_DEDUP_TTL_SECONDS": "1"})
    assert code == 2


def test_duplicate_message_names_when_the_diff_was_last_reviewed(tmp_path):
    diff = _src_diff("payload")
    _seed_stale(tmp_path, diff, iso="1999-12-31T23:59:59+00:00")
    _, _, err = _run_stop(diff, tmp_path)
    assert "since 1999-12-31T23:59:59+00:00" in err


def _diff_of_length(n: int) -> str:
    base = _src_diff("")
    return base + "x" * (n - len(base))


def test_diff_of_exactly_the_cap_plus_one_is_truncated_and_says_so(tmp_path):
    diff = _diff_of_length(60_001)
    assert len(diff) == 60_001
    code, _, err = _run_stop(diff, tmp_path)
    assert code == 2
    assert "(diff truncated to 60000 chars)" in err


def test_diff_at_the_cap_is_not_truncated(tmp_path):
    diff = _diff_of_length(60_000)
    code, _, err = _run_stop(diff, tmp_path)
    assert code == 2
    assert "truncated" not in err
