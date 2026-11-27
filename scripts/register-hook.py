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
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.atomic_io import atomic_write_text
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


def _validate_hook_name(name: str) -> str | None:
    """Return an error reason when *name* is not a plain filename, else None."""
    if not name or name in (".", "..") or "/" in name or "\\" in name or ".." in name:
        return f"invalid hook name: {name!r}"
    return None


def _command_hook_name(cmd: str) -> str:
    """Extract the hook script basename from a hook command string."""
    try:
        tokens = shlex.split(cmd)
    except ValueError:
        tokens = cmd.split()
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        norm = tok.replace("\\", "/")
        base = norm.rsplit("/", 1)[-1]
        if i == 0 and (base in ("sh", "bash", "env", "python", "python3") or base.startswith("python3.")):
            i += 1
            continue
        if tok.startswith("-"):
            i += 1
            continue
        if norm.endswith("/hooks/lib/pyrun.sh") and i + 1 < len(tokens):
            i += 1
            continue
        return base
    return _hook_label(cmd)


def _command_matches_hook(cmd: str, name: str) -> bool:
    """True when *cmd* invokes the exact hook basename *name*."""
    return _command_hook_name(cmd) == name


def _iter_event_groups(settings: dict, event: str) -> list[dict]:
    """Return all matcher group dicts for *event* (empty list if missing)."""
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return []
    groups = hooks.get(event)
    if not isinstance(groups, list):
        return []
    return [g for g in groups if isinstance(g, dict)]


def _ensure_hooks_list(settings: dict, event: str, matcher: str | None = None) -> list[dict]:
    """Return the hooks list for *event* (and *matcher*), creating missing dicts in place."""
    hooks = settings.setdefault("hooks", {})
    groups = hooks.setdefault(event, [])
    if matcher is not None:
        for group in groups:
            if isinstance(group, dict) and group.get("matcher") == matcher:
                return group.setdefault("hooks", [])
        new_group: dict = {"matcher": matcher, "hooks": []}
        groups.append(new_group)
        return new_group["hooks"]
    for group in groups:
        if isinstance(group, dict):
            return group.setdefault("hooks", [])
    new_group = {"hooks": []}
    groups.append(new_group)
    return new_group["hooks"]


def _references_in_settings(settings: dict, name: str) -> list[str]:
    """Return event labels for every registration in *settings* referencing *name*."""
    refs: list[str] = []
    hooks = settings.get("hooks", {})
    if not isinstance(hooks, dict):
        return refs
    for event, groups in hooks.items():
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            for h in group.get("hooks", []):
                if isinstance(h, dict) and _command_matches_hook(h.get("command", ""), name):
                    matcher = group.get("matcher")
                    refs.append(f"{event}({matcher})" if matcher else event)
    return refs


def load_settings() -> dict:
    """Load settings.json."""
    if not SETTINGS_PATH.exists():
        print(f"ERROR: {SETTINGS_PATH} not found", file=sys.stderr)
        sys.exit(1)
    return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))


def save_settings(data: dict) -> None:
    """Save settings.json atomically with trailing newline."""
    atomic_write_text(SETTINGS_PATH, json.dumps(data, indent=2) + "\n", encoding="utf-8")


def get_hooks_list(settings: dict, event: str, matcher: str | None = None) -> list[dict]:
    """Get or create the hooks list for a given event type (and optional matcher)."""
    return _ensure_hooks_list(settings, event, matcher)


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

    # Step 2: VERIFY the deployed file compiles cleanly (no -c interpolation)
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(target)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # Roll back deployment
        target.unlink(missing_ok=True)
        print("ERROR: File has syntax errors, rolled back deployment:", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    print(f"[2/3] Verified: {target} compiles cleanly")

    # Step 3: REGISTER in settings.json (only after file is deployed and verified)
    settings = load_settings()
    matcher = getattr(args, "matcher", None)

    # Check for duplicates across ALL matcher groups for this event (exact basename match)
    for group in _iter_event_groups(settings, args.event):
        for h in group.get("hooks", []):
            if isinstance(h, dict) and _command_matches_hook(h.get("command", ""), source.name):
                print(f"Already registered: {source.name} in {args.event}")
                return

    hooks_list = _ensure_hooks_list(settings, args.event, matcher=matcher)

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
    print("\nDone. Hook is live.")


def cmd_remove(args: argparse.Namespace) -> None:
    """Remove a hook: unregister first, then optionally delete file."""
    name_error = _validate_hook_name(args.name)
    if name_error:
        print(f"ERROR: {name_error}", file=sys.stderr)
        sys.exit(1)

    settings = load_settings()
    matcher = getattr(args, "matcher", None)

    # Step 1: UNREGISTER from settings.json FIRST across matching groups (all groups if --matcher omitted)
    removed = 0
    for group in _iter_event_groups(settings, args.event):
        if matcher is not None and group.get("matcher") != matcher:
            continue
        hooks_list = group.get("hooks")
        if not isinstance(hooks_list, list):
            continue
        before = len(hooks_list)
        hooks_list[:] = [
            h
            for h in hooks_list
            if not (isinstance(h, dict) and _command_matches_hook(h.get("command", ""), args.name))
        ]
        removed += before - len(hooks_list)

    if removed == 0:
        print(f"Not found: {args.name} in {args.event}")
    else:
        save_settings(settings)
        print(f"[1/2] Unregistered: {args.name} from {args.event}")

    # Step 2: Optionally delete the file (refuse if still referenced or outside HOOKS_DIR)
    target = HOOKS_DIR / args.name
    if args.delete_file:
        remaining = _references_in_settings(settings, args.name)
        if remaining:
            print(
                f"ERROR: Refusing to delete {target}: still referenced in settings.json ({', '.join(remaining)})",
                file=sys.stderr,
            )
            sys.exit(1)
        if target.exists() or target.is_symlink():
            if target.resolve().parent != HOOKS_DIR.resolve():
                print(f"ERROR: Refusing to delete {target}: resolves outside {HOOKS_DIR}", file=sys.stderr)
                sys.exit(1)
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
    p_add.add_argument("--matcher", default=None, help="Optional tool matcher group (e.g., Bash, Write|Edit)")
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
    p_rm.add_argument("--matcher", default=None, help="Optional tool matcher group to target")
    p_rm.add_argument("--delete-file", action="store_true", help="Also delete the file from ~/.claude/hooks/")

    # list
    sub.add_parser("list", help="List all registered hooks")

    # validate
    sub.add_parser("validate", help="Validate all hooks have backing files and timeouts in seconds")

    args = parser.parse_args()
    {"add": cmd_add, "remove": cmd_remove, "list": cmd_list, "validate": cmd_validate}[args.command](args)


if __name__ == "__main__":
    main()
