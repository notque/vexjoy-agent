#!/usr/bin/env python3
"""
Smoke-test all registered hooks against mock stdin inputs.

Validates exit codes and crash-free execution for hooks wired in settings.json.
Complements benchmark-hooks.py (timing) with correctness checks (exit codes).

Valid hook exit codes:
  0 — advisory output or no action (always OK)
  2 — block action (OK for blocking hooks; advisory hooks should not emit 2)
  Any other — unexpected, flag as WARN
  Crash / exception — FAIL

Usage:
    python scripts/smoke-test-hooks.py                # All registered hooks
    python scripts/smoke-test-hooks.py --event PostToolUse  # Filter by event
    python scripts/smoke-test-hooks.py --verbose      # Show stdout/stderr
    python scripts/smoke-test-hooks.py --ci           # Exit 1 on any FAIL
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SETTINGS_PATH = REPO_ROOT / ".claude" / "settings.json"
HOOKS_DIR = Path.home() / ".claude" / "hooks"

# Minimal mock inputs per event type
MOCK_INPUTS: dict[str, dict] = {
    "SessionStart": {"type": "SessionStart", "session_id": "smoke-test-session"},
    "UserPromptSubmit": {
        "type": "UserPromptSubmit",
        "prompt": "implement a feature with testing",
        "session_id": "smoke-test-session",
    },
    "PreToolUse": {
        "type": "PreToolUse",
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": "/tmp/smoke-test.py"},
        "session_id": "smoke-test-session",
    },
    "PostToolUse": {
        "type": "PostToolUse",
        "hook_event_name": "PostToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": "/tmp/smoke-test.py"},
        "tool_result": {"output": "File written successfully", "is_error": False},
        "session_id": "smoke-test-session",
    },
    "PreCompact": {"type": "PreCompact", "summary": "Working on feature"},
    "PostCompact": {"type": "PostCompact"},
    "Stop": {"type": "Stop", "stop_hook_active": False, "session_id": "smoke-test-session"},
    "StopFailure": {"type": "StopFailure"},
    "SubagentStop": {
        "type": "SubagentStop",
        "hook_event_name": "SubagentStop",
        "tool_name": "Agent",
        "tool_input": {"prompt": "smoke test subagent"},
        "tool_result": "OK",
        "session_id": "smoke-test-session",
    },
    "TaskCompleted": {
        "type": "TaskCompleted",
        "task": "smoke test task",
        "session_id": "smoke-test-session",
    },
}

VALID_EXIT_CODES = {0, 2}
_SAFE_PATH = os.pathsep.join((str(Path(sys.executable).resolve().parent), "/usr/local/bin", "/usr/bin", "/bin"))


def load_registered_hooks(
    event_filter: str | None = None,
    *,
    settings_path: Path = SETTINGS_PATH,
    trusted_hooks_dir: Path | None = None,
) -> list[dict]:
    """Extract hook entries, optionally mapping commands to trusted basenames."""
    if not settings_path.exists():
        print(f"ERROR: settings.json not found at {settings_path}", file=sys.stderr)
        return []

    with open(settings_path) as f:
        settings = json.load(f)

    hooks_config = settings.get("hooks", {})
    results = []

    for event, groups in hooks_config.items():
        if event_filter and event != event_filter:
            continue
        if not isinstance(groups, list):
            groups = [groups]
        for group in groups:
            matcher = group.get("matcher", "") if isinstance(group, dict) else ""
            entries = group.get("hooks", []) if isinstance(group, dict) else [group]
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                cmd = entry.get("command", "")
                # Extract python3 script path
                m = re.search(r'python3\s+"?([^"\s]+\.py)"?', cmd)
                if not m:
                    continue
                script_path = Path(m.group(1).replace("$HOME", str(Path.home())))
                if trusted_hooks_dir is not None:
                    basename = script_path.name
                    if re.fullmatch(r"[A-Za-z0-9_-]+\.py", basename) is None:
                        continue
                    script_path = trusted_hooks_dir / basename
                results.append(
                    {
                        "event": event,
                        "matcher": matcher,
                        "script": script_path,
                        "description": entry.get("description", ""),
                        "timeout_ms": 5000 if trusted_hooks_dir is not None else entry.get("timeout", 5000),
                        "command": cmd,
                    }
                )

    return results


def _safe_execution_environment(trusted_root: Path, untrusted_root: Path) -> dict[str, str]:
    """Build an environment with no target-derived or interpreter injection state."""
    trusted = str(trusted_root.resolve())
    untrusted = str(untrusted_root.resolve())
    env = {
        "HOME": trusted,
        "PATH": _SAFE_PATH,
        "PWD": trusted,
        "TMPDIR": "/tmp",
        "SHELL": "/bin/sh",
        "CLAUDE_PROJECT_DIR": trusted,
        "CLAUDE_HOOKS_DEBUG": "",
        "REF_GATE_BYPASS": "1",
        "PYTHONNOUSERSITE": "1",
        "PYTHONSAFEPATH": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    for key in ("LANG", "LC_ALL", "LC_CTYPE", "TERM", "TZ"):
        value = os.environ.get(key)
        if value and untrusted not in value:
            env[key] = value
    return env


def _safe_mock_input(event: str, trusted_root: Path) -> str:
    """Build a synthetic event whose paths are confined to the trusted root."""
    root = str(trusted_root.resolve())
    payload = copy.deepcopy(MOCK_INPUTS.get(event, MOCK_INPUTS["PostToolUse"]))
    payload["cwd"] = root
    payload["project_dir"] = root
    payload["project_root"] = root
    payload["repo_root"] = root
    for field in ("tool_input", "input"):
        value = payload.get(field)
        if isinstance(value, dict) and "file_path" in value:
            value["file_path"] = str(trusted_root.resolve() / ".vexjoy-smoke-test.py")
    return json.dumps(payload)


def run_hook(
    hook: dict,
    verbose: bool = False,
    *,
    trusted_root: Path | None = None,
    untrusted_root: Path | None = None,
) -> dict:
    """Run a single hook with mock stdin. Return result dict."""
    script = hook["script"]
    event = hook["event"]
    timeout_s = (hook["timeout_ms"] + 500) / 1000  # Add 500ms buffer

    if not script.exists():
        return {**hook, "status": "MISSING", "exit_code": -1, "stdout": "", "stderr": ""}

    safe_mode = trusted_root is not None and untrusted_root is not None
    mock_input = (
        _safe_mock_input(event, trusted_root)
        if safe_mode
        else json.dumps(MOCK_INPUTS.get(event, MOCK_INPUTS["PostToolUse"]))
    )
    child_env = (
        _safe_execution_environment(trusted_root, untrusted_root)
        if safe_mode
        else {
            **os.environ,
            "CLAUDE_HOOKS_DEBUG": "",
            "REF_GATE_BYPASS": "1",
        }
    )
    child_cwd = str(trusted_root.resolve()) if safe_mode else str(REPO_ROOT)
    child_command = [sys.executable, "-I", str(script)] if safe_mode else [sys.executable, str(script)]

    try:
        result = subprocess.run(
            child_command,
            input=mock_input,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=child_cwd,
            env=child_env,
        )
        exit_code = result.returncode
        status = "PASS" if exit_code in VALID_EXIT_CODES else "WARN"
        return {
            **hook,
            "status": status,
            "exit_code": exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired:
        return {**hook, "status": "TIMEOUT", "exit_code": -1, "stdout": "", "stderr": ""}
    except Exception as e:
        return {**hook, "status": "FAIL", "exit_code": -1, "stdout": "", "stderr": str(e)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test registered Claude Code hooks")
    parser.add_argument("--event", help="Filter to a specific event type")
    parser.add_argument("--verbose", action="store_true", help="Show stdout/stderr output")
    parser.add_argument("--ci", action="store_true", help="Exit 1 on any FAIL or MISSING")
    parser.add_argument("--compact", action="store_true", help="One line per hook (default for >20 hooks)")
    parser.add_argument("--repo-root", type=Path, help="Repository whose .claude/settings.json should be inspected")
    parser.add_argument("--hooks-dir", type=Path, help="Trusted hooks directory used with --repo-root")
    args = parser.parse_args()

    if (args.repo_root is None) != (args.hooks_dir is None):
        parser.error("--repo-root and --hooks-dir must be provided together")
    settings_path = SETTINGS_PATH
    trusted_hooks_dir = None
    untrusted_root = None
    if args.repo_root is not None:
        untrusted_root = args.repo_root.resolve()
        settings_path = untrusted_root / ".claude" / "settings.json"
        trusted_hooks_dir = args.hooks_dir.resolve()
    trusted_root = trusted_hooks_dir.parent if trusted_hooks_dir is not None else None

    hooks = load_registered_hooks(
        event_filter=args.event,
        settings_path=settings_path,
        trusted_hooks_dir=trusted_hooks_dir,
    )
    if not hooks:
        print("No registered hooks found.")
        return 1 if args.ci and args.repo_root is not None else 0

    compact = args.compact or (len(hooks) > 20 and not args.verbose)

    results = []
    for hook in hooks:
        r = run_hook(
            hook,
            verbose=args.verbose,
            trusted_root=trusted_root,
            untrusted_root=untrusted_root,
        )
        results.append(r)

    # Print results
    fails = 0
    statuses = {"PASS": 0, "WARN": 0, "FAIL": 0, "MISSING": 0, "TIMEOUT": 0}

    for r in results:
        status = r["status"]
        statuses[status] = statuses.get(status, 0) + 1
        if status in {"FAIL", "MISSING"}:
            fails += 1

        name = r["script"].name
        desc = r["description"][:50] if r["description"] else ""
        line = f"  [{r['event']}] {name:<45} {status}"
        if r["exit_code"] not in VALID_EXIT_CODES and r["exit_code"] != -1:
            line += f" (exit {r['exit_code']})"

        if compact and status == "PASS":
            continue  # Suppress passing hooks in compact mode

        print(line)
        if args.verbose and (r["stdout"] or r["stderr"]):
            if r["stdout"]:
                print(f"    stdout: {r['stdout'][:200]}")
            if r["stderr"]:
                print(f"    stderr: {r['stderr'][:200]}")

    total = len(results)
    print()
    print(
        f"Hooks: {total} | PASS: {statuses['PASS']} | WARN: {statuses['WARN']} | "
        f"FAIL: {statuses['FAIL']} | MISSING: {statuses['MISSING']} | TIMEOUT: {statuses['TIMEOUT']}"
    )

    if args.ci and fails > 0:
        print(f"\nCI FAILURE: {fails} hook(s) failed smoke test")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
