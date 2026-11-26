#!/usr/bin/env python3
"""Time the hooks Claude Code runs on each tool call and prompt.

Reads the registrations in ``.claude/settings.json`` and, for each case below
(a PreToolUse or PostToolUse tool call, or a UserPromptSubmit prompt), runs
every matching registered command the way Claude Code does: ``sh -c
<command>`` with the event payload on stdin. Claude Code runs an event's hooks
in parallel, so a case's slowest hook is the delay a call sees and the sum is
the CPU it costs.

Every run happens in a throwaway sandbox: a scratch HOME whose ``.claude``
links the checkout's hooks, scripts, and skills, an empty learning store, a
scratch git repo as the project, and an environment built from scratch (no
API keys, no live session ids, sync disabled). The real ``~/.claude`` is never
touched. Lifecycle events (SessionStart, Stop, SubagentStop, PreCompact, ...)
are never run: several of those hooks sync installs or start background jobs.

Usage:
    python3 scripts/benchmark-hooks.py                      # all cases, 5 runs each
    python3 scripts/benchmark-hooks.py --event PreToolUse   # one event
    python3 scripts/benchmark-hooks.py --ci --threshold 50  # exit 1 on a median over 50 ms
    python3 scripts/benchmark-hooks.py --verbose            # every hook row
    python3 scripts/benchmark-hooks.py --json               # machine-readable
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SETTINGS = REPO_ROOT / ".claude" / "settings.json"
DEFAULT_THRESHOLD_MS = 50  # CONTRIBUTING.md hook budget
ITERATIONS = 5
EVENTS = ("PreToolUse", "PostToolUse", "UserPromptSubmit")  # per-call events only
TIMEOUT_S = 30
TOP_ROWS = 5

# (event, tool, tool_input); "{work}" is replaced with the scratch repo path.
CASES = [
    ("PreToolUse", "Bash", {"command": "ls -la", "description": "List files"}),
    ("PreToolUse", "Bash", {"command": "git status --short", "description": "Show status"}),
    ("PreToolUse", "Write", {"file_path": "{work}/new_mod.py", "content": "x = 1\n"}),
    ("PreToolUse", "Edit", {"file_path": "{work}/app.py", "old_string": "return 1", "new_string": "return 2"}),
    ("PreToolUse", "Read", {"file_path": "{work}/app.py"}),
    ("PreToolUse", "Grep", {"pattern": "return", "path": "{work}"}),
    ("PostToolUse", "Bash", {"command": "ls -la", "description": "List files"}),
    ("PostToolUse", "Write", {"file_path": "{work}/new_mod.py", "content": "x = 1\n"}),
    ("PostToolUse", "Edit", {"file_path": "{work}/app.py", "old_string": "return 1", "new_string": "return 2"}),
    ("PostToolUse", "Read", {"file_path": "{work}/app.py"}),
    ("UserPromptSubmit", None, None),
]
PROMPT = "fix the failing parser test and add a regression case"  # never "/d ...": that path calls Jev

_SAFE_SESSION_ID = re.compile(r"bench-[0-9a-z]+")


def matches(matcher: str, tool: str | None) -> bool:
    """Return True when a registration's matcher selects ``tool``, as Claude Code does."""
    if tool is None or matcher in ("", "*"):
        return True
    return re.fullmatch(matcher, tool) is not None


def registered(settings: dict, event: str, tool: str | None) -> list[str]:
    """Return every registered command for ``event`` whose matcher selects ``tool``, in file order."""
    commands: list[str] = []
    for group in settings.get("hooks", {}).get(event, []):
        if not matches(group.get("matcher", "") or "", tool):
            continue
        for hook in group.get("hooks", []):
            command = hook.get("command")
            if command:
                commands.append(command)
    return commands


def make_sandbox(root: Path, settings: Path = SETTINGS) -> tuple[Path, Path]:
    """Build the scratch HOME and project repo under ``root``; return ``(home, work)``."""
    home = root / "home"
    claude = home / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    for name in ("hooks", "scripts", "skills"):
        link = claude / name
        if not link.exists() and not link.is_symlink():
            link.symlink_to(REPO_ROOT / name, target_is_directory=True)
    (claude / "learning").mkdir(exist_ok=True)
    shutil.copyfile(settings, claude / "settings.json")
    (root / "tmp").mkdir(exist_ok=True)

    work = root / "work"
    work.mkdir(exist_ok=True)
    git_env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(home), "GIT_CONFIG_NOSYSTEM": "1"}
    subprocess.run(["git", "init", "-q", "-b", "feature/bench"], cwd=work, env=git_env, check=True)
    (work / "app.py").write_text("def f():\n    return 1\n")
    subprocess.run(["git", "add", "app.py"], cwd=work, env=git_env, check=True)
    subprocess.run(
        ["git", "-c", "user.name=bench", "-c", "user.email=bench@example.invalid", "commit", "-qm", "init"],
        cwd=work,
        env=git_env,
        check=True,
    )
    return home, work


def build_env(root: Path, *, home: Path, work: Path, session_id: str) -> dict[str, str]:
    """Build the hook environment from scratch: no caller keys, no live session ids."""
    env = {
        "PATH": os.pathsep.join([str(Path(sys.executable).resolve().parent), "/usr/local/bin", "/usr/bin", "/bin"]),
        "HOME": str(home),
        "USER": os.environ.get("USER", "bench"),
        "SHELL": "/bin/sh",
        "TMPDIR": str(root / "tmp"),
        "CLAUDE_PROJECT_DIR": str(work),
        "CLAUDE_LEARNING_DIR": str(home / ".claude" / "learning"),
        "CLAUDE_HOOK_ERRORS_PATH": str(root / "hook-errors.jsonl"),
        "CLAUDE_SESSION_ID": session_id,
        "VEXJOY_SYNC_DISABLED": "1",
        "RULES_DISTILL_TRIGGER_BYPASS": "1",
    }
    for key in ("LANG", "LC_ALL"):
        value = os.environ.get(key)
        if value:
            env[key] = value
    return env


def _fill(value, work: Path):
    """Replace ``{work}`` in every string of a tool input."""
    if isinstance(value, str):
        return value.replace("{work}", str(work))
    if isinstance(value, dict):
        return {k: _fill(v, work) for k, v in value.items()}
    return value


def payload(event, tool, tool_input, *, work: Path, session_id: str, transcript: Path) -> str:
    """Return the JSON event Claude Code would send on stdin."""
    data: dict = {
        "session_id": session_id,
        "transcript_path": str(transcript),
        "cwd": str(work),
        "hook_event_name": event,
    }
    if tool is not None:
        data["tool_name"] = tool
        data["tool_input"] = _fill(tool_input or {}, work)
    if event == "PostToolUse":
        data["tool_response"] = {"stdout": "ok", "stderr": "", "success": True}
    if event == "UserPromptSubmit":
        data["prompt"] = PROMPT
    return json.dumps(data)


def _run_once(command: str, data: str, env: dict, cwd: Path) -> tuple[float, int, int]:
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            ["sh", "-c", command],
            input=data,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_S,
            env=env,
            cwd=str(cwd),
        )
    except subprocess.TimeoutExpired:
        return TIMEOUT_S * 1000.0, -1, 0
    return (time.perf_counter() - start) * 1000, proc.returncode, len(proc.stdout)


def time_command(command: str, data: str, env: dict, cwd: Path, runs: int) -> dict:
    """Run a registered command once untimed, then ``runs`` timed; return median, p90, rc, output size."""
    _run_once(command, data, env, cwd)
    times: list[float] = []
    rc, out_bytes = 0, 0
    for _ in range(max(runs, 1)):
        elapsed, rc, out_bytes = _run_once(command, data, env, cwd)
        times.append(elapsed)
    ordered = sorted(times)
    p90 = ordered[min(len(ordered) - 1, round(0.9 * (len(ordered) - 1)))]
    return {
        "median_ms": round(statistics.median(times), 1),
        "p90_ms": round(p90, 1),
        "rc": rc,
        "out_bytes": out_bytes,
    }


def cleanup_tmp(session_id: str, base: Path = Path("/tmp")) -> None:
    """Remove the files hooks left in ``base`` for this bench session, and nothing else."""
    if not _SAFE_SESSION_ID.fullmatch(session_id):
        raise ValueError(f"refusing to clean up for session id {session_id!r}")
    targets = [base / ".claude-backups" / session_id, *base.glob(f"*{session_id}*")]
    for path in targets:
        if session_id not in path.name:
            continue
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path, ignore_errors=True)
        elif path.exists() or path.is_symlink():
            path.unlink(missing_ok=True)


def hook_name(command: str) -> str:
    """Return the last path component of a command, without the closing quote."""
    return command.rstrip().split("/")[-1].rstrip('"')


def case_label(event: str, tool: str | None, tool_input: dict | None) -> str:
    label = event if tool is None else f"{event}:{tool}"
    if tool_input and isinstance(tool_input.get("command"), str):
        label += f" ({tool_input['command'].split()[0]})"
    return label


def main(argv: list[str] | None = None) -> int:
    """Benchmark registered per-call hooks in an isolated sandbox."""
    parser = argparse.ArgumentParser(description="Time registered per-call Claude Code hooks in an isolated HOME")
    parser.add_argument("--iterations", type=int, default=ITERATIONS, help="timed runs per hook (default 5)")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD_MS, help="budget per hook median, ms")
    parser.add_argument("--event", choices=EVENTS, help="run only this event's cases")
    parser.add_argument("--json", action="store_true", help="print JSON instead of a table")
    parser.add_argument("--verbose", action="store_true", help=f"print every hook row (default: slowest {TOP_ROWS})")
    parser.add_argument("--ci", action="store_true", help="exit 1 when any hook median exceeds the threshold")
    parser.add_argument("--settings", type=Path, default=SETTINGS, help="settings file to read registrations from")
    parser.add_argument("--sandbox-root", type=Path, help="sandbox directory to use and keep (default: temp, removed)")
    args = parser.parse_args(argv)

    settings = json.loads(args.settings.read_text())
    session_id = f"bench-{uuid.uuid4().hex[:12]}"
    keep = args.sandbox_root is not None
    root = args.sandbox_root if keep else Path(tempfile.mkdtemp(prefix="vexjoy-hookbench-"))
    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve()

    results = []
    over = 0
    try:
        home, work = make_sandbox(root, args.settings)
        env = build_env(root, home=home, work=work, session_id=session_id)
        transcript = root / "transcript.jsonl"
        transcript.touch()
        for event, tool, tool_input in CASES:
            if args.event and event != args.event:
                continue
            data = payload(event, tool, tool_input, work=work, session_id=session_id, transcript=transcript)
            hooks = []
            for command in registered(settings, event, tool):
                row = {"name": hook_name(command), **time_command(command, data, env, work, args.iterations)}
                row["over"] = row["median_ms"] > args.threshold
                over += row["over"]
                hooks.append(row)
            hooks.sort(key=lambda r: r["median_ms"], reverse=True)
            results.append(
                {
                    "case": case_label(event, tool, tool_input),
                    "hooks": hooks,
                    "sum_ms": round(sum(r["median_ms"] for r in hooks), 1),
                    "max_ms": hooks[0]["median_ms"] if hooks else 0.0,
                }
            )
    finally:
        cleanup_tmp(session_id)
        if not keep:
            shutil.rmtree(root, ignore_errors=True)

    if args.json:
        print(json.dumps({"threshold_ms": args.threshold, "iterations": args.iterations, "cases": results}, indent=2))
    else:
        for case in results:
            hooks = case["hooks"]
            slowest = f" ({hooks[0]['name']})" if hooks else ""
            print(
                f"## {case['case']}: {len(hooks)} hooks, sum {case['sum_ms']} ms, slowest {case['max_ms']} ms{slowest}"
            )
            for r in hooks if args.verbose else hooks[:TOP_ROWS]:
                flag = " OVER" if r["over"] else ""
                print(f"{r['name']} median {r['median_ms']} p90 {r['p90_ms']} rc={r['rc']}{flag}")
            print()
        print(f"Threshold: {args.threshold} ms | iterations: {args.iterations} | hooks over: {over}")

    if args.ci and over:
        print(f"CI FAILURE: {over} hook median(s) over {args.threshold} ms", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
