"""B-17: hooks and adapters must not wait forever on a stdin that never closes.

Each case starts the script, writes part of a payload and keeps the pipe open,
the shape of a harness that crashed or wedged mid-write. Before the fix these
scripts blocked in ``sys.stdin.read()`` until the harness killed them; now
each gives up after its bound and exits 0 with its usual fail-safe output.
Normal input (written, then closed) keeps today's behavior; the existing
suites for each script cover that path.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parent.parent

# The hooks read with timeout=2; this is the most a passing case may take.
_MAX_SECONDS = 10.0


def _env(home: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env.update({"HOME": str(home), "CLAUDE_HOOK_ERRORS_PATH": str(home / "hook-errors.jsonl")})
    return env


def _run_with_open_stdin(argv: list[str], *, cwd: Path, env: dict[str, str]) -> tuple[int, str, str, float]:
    """Start argv, send a partial payload, never close stdin; return rc, stdout, stderr, seconds."""
    proc = subprocess.Popen(
        argv,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=cwd,
        env=env,
    )
    started = time.monotonic()
    try:
        proc.stdin.write('{"hook_event_name": "PreToolUse", "tool_name": ')
        proc.stdin.flush()
        try:
            returncode = proc.wait(timeout=_MAX_SECONDS)
        except subprocess.TimeoutExpired:
            pytest.fail(f"{Path(argv[1]).name} still waiting on stdin after {_MAX_SECONDS:g}s")
        elapsed = time.monotonic() - started
        proc.stdin.close()
        return returncode, proc.stdout.read(), proc.stderr.read(), elapsed
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            try:
                stream.close()
            except (OSError, ValueError):
                pass


@pytest.mark.parametrize(
    "hook",
    [
        "pretool-dispatch-spec-gate.py",
        "pending-advisory-injector-userprompt.py",
        "voice-output-gate.py",
    ],
)
def test_hook_gives_up_on_a_stdin_that_never_closes(tmp_path: Path, hook: str) -> None:
    rc, stdout, stderr, elapsed = _run_with_open_stdin(
        [sys.executable, str(HOOKS / hook)], cwd=tmp_path, env=_env(tmp_path)
    )
    assert rc == 0, stderr
    assert elapsed >= 1.0, "the bound is the shared read_stdin(timeout=2)"
    assert "stdin read timed out" in stderr
    if stdout.strip():
        # Silent or an empty, valid result: a half-read event never reaches the checks.
        assert "permissionDecision" not in json.loads(stdout).get("hookSpecificOutput", {})


def test_worktree_edit_guard_fallback_reader_is_bounded_too(tmp_path: Path) -> None:
    """With hooks/lib missing, the guard's own fallback reader used to block forever."""
    install = tmp_path / "install"
    install.mkdir()
    shutil.copy(HOOKS / "pretool-worktree-edit-guard.py", install / "pretool-worktree-edit-guard.py")

    rc, stdout, stderr, elapsed = _run_with_open_stdin(
        [sys.executable, str(install / "pretool-worktree-edit-guard.py")], cwd=tmp_path, env=_env(tmp_path)
    )

    assert rc == 0, stderr
    assert stdout == "", "a timed-out read is a malformed payload: fail open, as with hooks/lib present"
    assert elapsed >= 1.0


def _child_hook(tmp_path: Path) -> Path:
    hook = tmp_path / "child-hook.py"
    hook.write_text("import sys\nsys.stdin.read()\n", encoding="utf-8")
    return hook


@pytest.mark.parametrize(
    ("policy", "expected"),
    [
        ("closed", {"permissionDecision": "deny"}),
        ("open", None),
    ],
)
def test_codex_adapter_applies_its_failure_policy_when_stdin_never_closes(
    tmp_path: Path, policy: str, expected: dict | None
) -> None:
    argv = [
        sys.executable,
        str(HOOKS / "codex-hook-adapter.py"),
        "--hook",
        str(_child_hook(tmp_path)),
        "--event",
        "PreToolUse",
        "--matcher",
        "Bash",
        "--mode",
        "native",
        "--failure-policy",
        policy,
        "--timeout",
        "1",
    ]
    rc, stdout, stderr, elapsed = _run_with_open_stdin(argv, cwd=tmp_path, env=_env(tmp_path))

    assert rc == 0, stderr
    assert elapsed >= 0.9
    output = json.loads(stdout)
    if expected is None:
        assert "stdin was not closed within 1s" in output["systemMessage"]
    else:
        specific = output["hookSpecificOutput"]
        assert specific["permissionDecision"] == expected["permissionDecision"]
        assert "stdin was not closed within 1s" in specific["permissionDecisionReason"]


@pytest.mark.parametrize(
    ("policy", "expected"),
    [
        ("closed", {"decision": "deny"}),
        ("open", {"decision": "allow"}),
    ],
)
def test_agy_adapter_applies_its_failure_policy_when_stdin_never_closes(
    tmp_path: Path, policy: str, expected: dict
) -> None:
    argv = [
        sys.executable,
        str(HOOKS / "agy-hook-adapter.py"),
        "--hook",
        str(_child_hook(tmp_path)),
        "--event",
        "PreToolUse",
        "--failure-policy",
        policy,
        "--timeout",
        "1",
    ]
    env = _env(tmp_path)
    env["VEXJOY_AGY_DEFERRED_DIR"] = str(tmp_path / "deferred")
    rc, stdout, stderr, elapsed = _run_with_open_stdin(argv, cwd=tmp_path, env=env)

    assert rc == 0, stderr
    assert elapsed >= 0.9
    output = json.loads(stdout)
    assert output["decision"] == expected["decision"]
    if policy == "closed":
        assert "stdin was not closed within 1s" in output["reason"]


def test_agy_adapter_still_treats_empty_closed_stdin_as_an_empty_event(tmp_path: Path) -> None:
    """Unchanged: an empty, closed stdin runs the hook with {} instead of failing."""
    hook = tmp_path / "echo-hook.py"
    hook.write_text(
        "import json, sys\n"
        "event = json.loads(sys.stdin.read())\n"
        "print(json.dumps({'hookSpecificOutput': {'hookEventName': 'SessionStart',"
        " 'additionalContext': 'ran with ' + str(sorted(event))}}))\n",
        encoding="utf-8",
    )
    env = _env(tmp_path)
    env["VEXJOY_AGY_DEFERRED_DIR"] = str(tmp_path / "deferred")
    result = subprocess.run(
        [sys.executable, str(HOOKS / "agy-hook-adapter.py"), "--hook", str(hook), "--event", "SessionStart"],
        input="",
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    steps = json.loads(result.stdout)["injectSteps"]
    assert "ran with" in steps[0]["systemMessage"]["systemMessage"]
