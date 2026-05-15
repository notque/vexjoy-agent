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
import json
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
        "tool_result": "File written successfully",
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


def load_registered_hooks(event_filter: str | None = None) -> list[dict]:
    """Extract hook entries from settings.json, optionally filtered by event."""
    if not SETTINGS_PATH.exists():
        print(f"ERROR: settings.json not found at {SETTINGS_PATH}", file=sys.stderr)
        return []

    with open(SETTINGS_PATH) as f:
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
                import re

                m = re.search(r'python3\s+"?([^"\s]+\.py)"?', cmd)
                if not m:
                    continue
                script_path = m.group(1).replace("$HOME", str(Path.home()))
                results.append(
                    {
                        "event": event,
                        "matcher": matcher,
                        "script": Path(script_path),
                        "description": entry.get("description", ""),
                        "timeout_ms": entry.get("timeout", 5000),
                        "command": cmd,
                    }
                )

    return results


def run_hook(hook: dict, verbose: bool = False) -> dict:
    """Run a single hook with mock stdin. Return result dict."""
    script = hook["script"]
    event = hook["event"]
    timeout_s = (hook["timeout_ms"] + 500) / 1000  # Add 500ms buffer

    if not script.exists():
        return {**hook, "status": "MISSING", "exit_code": -1, "stdout": "", "stderr": ""}

    mock_input = json.dumps(MOCK_INPUTS.get(event, MOCK_INPUTS["PostToolUse"]))

    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            input=mock_input,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=str(REPO_ROOT),
            env={
                **__import__("os").environ,
                "CLAUDE_HOOKS_DEBUG": "",
                "REF_GATE_BYPASS": "1",  # Prevent advisory hooks from cluttering output
            },
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
    args = parser.parse_args()

    hooks = load_registered_hooks(event_filter=args.event)
    if not hooks:
        print("No registered hooks found.")
        return 0

    compact = args.compact or (len(hooks) > 20 and not args.verbose)

    results = []
    for hook in hooks:
        r = run_hook(hook, verbose=args.verbose)
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
