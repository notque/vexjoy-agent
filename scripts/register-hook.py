#!/usr/bin/env python3
"""Safe hook registration: deploy file THEN register in settings.json.

Enforces the correct order: file must exist at ~/.claude/hooks/ BEFORE
it gets registered in settings.json. Prevents the deadlock scenario
where a missing hook file causes Python exit code 2, which Claude Code
interprets as an intentional BLOCK on every tool call.

Usage:
    # Register a hook (copies to ~/.claude/hooks/ first, then registers)
    python3 scripts/register-hook.py add \
        --file hooks/pretool-synthesis-gate.py \
        --event PreToolUse \
        --description "Consultation synthesis gate" \
        --timeout 10

    # Unregister a hook (removes from settings.json first, then optionally deletes file)
    python3 scripts/register-hook.py remove \
        --name pretool-synthesis-gate.py \
        --event PreToolUse

    # List all registered hooks
    python3 scripts/register-hook.py list

    # Validate all registered hooks have backing files and timeouts in seconds
    python3 scripts/register-hook.py validate

Timeouts are seconds, as Claude Code reads them. A timed-out gate fails open, so
the default is 10 s for PreToolUse, PermissionRequest and UserPromptSubmit hooks
and 5 s for the rest. A timeout over 600 s, or one that is not a positive number,
is rejected (a millisecond value such as 3000 would hold a session for 50 minutes);
one over 120 s gets a warning.

Exit codes:
    0 - Success
    1 - Error (file not found, invalid JSON, rejected timeout, etc.)
    2 - Validation failure (registered hook has no backing file, or a rejected timeout)
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vexinstall.interp import hook_command as launcher_command

SETTINGS_PATH = Path.home() / ".claude" / "settings.json"
HOOKS_DIR = Path.home() / ".claude" / "hooks"

# Hook timeouts, in seconds (the unit Claude Code reads).
GATE_EVENTS = frozenset({"PreToolUse", "PermissionRequest", "UserPromptSubmit"})
GATE_TIMEOUT_S = 10
DEFAULT_TIMEOUT_S = 5
MAX_TIMEOUT_S = 600
WARN_TIMEOUT_S = 120


def default_timeout(event: str) -> int:
    """Default timeout for a new hook on *event*: gates fail open on timeout, so they get more."""
    return GATE_TIMEOUT_S if event in GATE_EVENTS else DEFAULT_TIMEOUT_S


def timeout_problem(value: object) -> tuple[str, str] | None:
    """("FAIL" or "WARN", reason) for a timeout that is not sane in seconds; None when it is."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        return "FAIL", f"timeout {value!r} is not a positive number of seconds"
    if value > MAX_TIMEOUT_S:
        return "FAIL", (
            f"timeout {value:g} is over {MAX_TIMEOUT_S} s; Claude Code reads seconds, "
            f"so a millisecond value lets a hung hook hold the session"
        )
    if value > WARN_TIMEOUT_S:
        return "WARN", f"timeout {value:g} s is over {WARN_TIMEOUT_S} s; a hung hook holds the session that long"
    return None


def _hook_label(cmd: str) -> str:
    """The hook's filename as written in its command (the whole command when it has no path)."""
    return cmd.split("/")[-1].rstrip('"') if "/" in cmd else cmd


def load_settings() -> dict:
    """Load settings.json."""
    if not SETTINGS_PATH.exists():
        print(f"ERROR: {SETTINGS_PATH} not found", file=sys.stderr)
        sys.exit(1)
    return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))


def save_settings(data: dict) -> None:
    """Save settings.json with trailing newline."""
    SETTINGS_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def get_hooks_list(settings: dict, event: str) -> list[dict]:
    """Get the hooks list for a given event type."""
    hooks = settings.get("hooks", {})
    event_groups = hooks.get(event, [])
    if not event_groups:
        return []
    # Settings uses array of groups, each with a "hooks" array
    if isinstance(event_groups, list) and event_groups:
        first = event_groups[0]
        if isinstance(first, dict) and "hooks" in first:
            return first["hooks"]
    return []


def guard_problems(source: Path) -> list[str]:
    """Why *source* lacks the python version guard (scripts/hook-pyguard.py); empty when guarded."""
    spec = importlib.util.spec_from_file_location("hook_pyguard", Path(__file__).resolve().parent / "hook-pyguard.py")
    if spec is None or spec.loader is None:
        return ["scripts/hook-pyguard.py not importable"]
    pyguard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pyguard)
    return pyguard.problems(source.name, source.read_text(encoding="utf-8"))


def cmd_add(args: argparse.Namespace) -> None:
    """Add a hook: deploy file first, then register."""
    source = Path(args.file)
    if not source.exists():
        print(f"ERROR: Source file not found: {source}", file=sys.stderr)
        sys.exit(1)
    problems = guard_problems(source)
    if problems:
        # An unguarded hook crashes with exit 1 under python <3.10, and a gate then fails open.
        print("ERROR: hook lacks the python version guard: " + "; ".join(problems), file=sys.stderr)
        print(f"Fix: python3 scripts/hook-pyguard.py --apply --file {source}", file=sys.stderr)
        sys.exit(1)
    timeout = args.timeout if args.timeout is not None else default_timeout(args.event)
    problem = timeout_problem(timeout)
    if problem and problem[0] == "FAIL":
        print(f"ERROR: {problem[1]}", file=sys.stderr)
        sys.exit(1)
    if problem:
        print(f"WARNING: {problem[1]}", file=sys.stderr)

    target = HOOKS_DIR / source.name
    hook_command = launcher_command(source.name)

    # Step 1: DEPLOY file to ~/.claude/hooks/ FIRST
    HOOKS_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    print(f"[1/3] Deployed: {source} -> {target}")

    # Step 2: VERIFY the deployed file is importable
    import subprocess

    result = subprocess.run(
        [sys.executable, "-c", f"import py_compile; py_compile.compile('{target}', doraise=True)"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # Roll back deployment
        target.unlink(missing_ok=True)
        print(f"ERROR: File has syntax errors, rolled back deployment:", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    print(f"[2/3] Verified: {target} compiles cleanly")

    # Step 3: REGISTER in settings.json (only after file is deployed and verified)
    settings = load_settings()
    hooks_list = get_hooks_list(settings, args.event)

    # Check for duplicates
    for h in hooks_list:
        if source.name in h.get("command", ""):
            print(f"Already registered: {source.name} in {args.event}")
            return

    new_hook = {
        "type": "command",
        "command": hook_command,
        "description": args.description,
        "timeout": timeout,
    }

    # Insert after first hook (unified gate stays first)
    insert_pos = min(1, len(hooks_list))
    hooks_list.insert(insert_pos, new_hook)
    save_settings(settings)
    print(f"[3/3] Registered: {source.name} in {args.event} at position {insert_pos}")
    print(f"\nDone. Hook is live.")


def cmd_remove(args: argparse.Namespace) -> None:
    """Remove a hook: unregister first, then optionally delete file."""
    settings = load_settings()
    hooks_list = get_hooks_list(settings, args.event)

    # Step 1: UNREGISTER from settings.json FIRST
    original_len = len(hooks_list)
    hooks_list[:] = [h for h in hooks_list if args.name not in h.get("command", "")]

    if len(hooks_list) == original_len:
        print(f"Not found: {args.name} in {args.event}")
    else:
        save_settings(settings)
        print(f"[1/2] Unregistered: {args.name} from {args.event}")

    # Step 2: Optionally delete the file
    target = HOOKS_DIR / args.name
    if target.exists() and args.delete_file:
        target.unlink()
        print(f"[2/2] Deleted: {target}")
    elif target.exists():
        print(f"[2/2] Kept file: {target} (use --delete-file to remove)")


def cmd_list(args: argparse.Namespace) -> None:
    """List all registered hooks."""
    settings = load_settings()
    hooks = settings.get("hooks", {})
    for event, groups in hooks.items():
        if not groups:
            continue
        print(f"\n{event}:")
        for group in groups:
            for h in group.get("hooks", []):
                cmd = h.get("command", "")
                desc = h.get("description", "")
                timeout = h.get("timeout", "?")
                print(f"  {_hook_label(cmd):45s} timeout={timeout}s")
                if desc:
                    print(f"    {desc}")


def cmd_validate(args: argparse.Namespace) -> None:
    """Validate all registered hooks have backing files and timeouts in seconds.

    Emits one [PASS]/[FAIL] line per hook so CI and cron wrappers can
    detect problems by grepping for '[FAIL]'. A timeout over WARN_TIMEOUT_S
    adds a [WARN] line and does not fail.
    """
    settings = load_settings()
    hooks = settings.get("hooks", {})
    issues = []

    for event, groups in hooks.items():
        if not groups:
            continue
        for group in groups:
            for h in group.get("hooks", []):
                cmd = h.get("command", "")
                problem = timeout_problem(h["timeout"]) if "timeout" in h else None
                timeout_failed = problem is not None and problem[0] == "FAIL"
                if problem:
                    print(f"[{problem[0]}] {event}/{_hook_label(cmd)}: {problem[1]}")
                if timeout_failed:
                    issues.append((event, _hook_label(cmd), "TIMEOUT"))
                if "$HOME/.claude/hooks/" not in cmd:
                    # Flag hooks using relative paths — they break in non-toolkit repos
                    if "python3 hooks/" in cmd or 'python3 "hooks/' in cmd:
                        hook_file = cmd.split("hooks/")[-1].rstrip('"').rstrip("'")
                        issues.append((event, hook_file, "RELATIVE PATH"))
                        print(f"[FAIL] {event}/{hook_file}: uses relative path (breaks outside toolkit repo)")
                    continue
                # Extract filename
                name = cmd.split("$HOME/.claude/hooks/")[-1].rstrip('"')
                target = HOOKS_DIR / name
                if not target.exists():
                    issues.append((event, name, "FILE MISSING"))
                    print(f"[FAIL] {event}/{name}: file does not exist at {target}")
                elif not timeout_failed:
                    print(f"[PASS] {event}/{name}")

    missing = [i for i in issues if i[2] != "TIMEOUT"]
    bad_timeouts = [i for i in issues if i[2] == "TIMEOUT"]
    if missing:
        print(f"\n{len(missing)} hook(s) registered without backing files!", file=sys.stderr)
        print("This WILL deadlock Claude Code (Python exit 2 = BLOCK).", file=sys.stderr)
        print("Fix: create the missing files or unregister the hooks.", file=sys.stderr)
    if bad_timeouts:
        print(f"\n{len(bad_timeouts)} hook(s) with a rejected timeout.", file=sys.stderr)
        print(f"Fix: give each a positive timeout in seconds, at most {MAX_TIMEOUT_S}.", file=sys.stderr)
    if issues:
        sys.exit(2)
    print("\nAll registered hooks have backing files and timeouts in seconds.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Safe hook registration (deploy-before-register)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # add
    p_add = sub.add_parser("add", help="Deploy and register a hook")
    p_add.add_argument("--file", required=True, help="Path to hook .py file in repo")
    p_add.add_argument("--event", required=True, help="Hook event type (PreToolUse, PostToolUse, etc.)")
    p_add.add_argument("--description", required=True, help="Hook description for settings.json")
    p_add.add_argument(
        "--timeout",
        type=int,
        default=None,
        help=(
            f"Timeout in seconds (default: {GATE_TIMEOUT_S} for PreToolUse, PermissionRequest and "
            f"UserPromptSubmit, {DEFAULT_TIMEOUT_S} otherwise; at most {MAX_TIMEOUT_S})"
        ),
    )

    # remove
    p_rm = sub.add_parser("remove", help="Unregister (and optionally delete) a hook")
    p_rm.add_argument("--name", required=True, help="Hook filename (e.g., pretool-synthesis-gate.py)")
    p_rm.add_argument("--event", required=True, help="Hook event type")
    p_rm.add_argument("--delete-file", action="store_true", help="Also delete the file from ~/.claude/hooks/")

    # list
    sub.add_parser("list", help="List all registered hooks")

    # validate
    sub.add_parser("validate", help="Validate all hooks have backing files and timeouts in seconds")

    args = parser.parse_args()
    {"add": cmd_add, "remove": cmd_remove, "list": cmd_list, "validate": cmd_validate}[args.command](args)


if __name__ == "__main__":
    main()
