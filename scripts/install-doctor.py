#!/usr/bin/env python3
"""
install-doctor.py — Deterministic health checks for Claude Code Toolkit installation.

Usage:
    python3 scripts/install-doctor.py check          # Run all checks
    python3 scripts/install-doctor.py check --json    # Machine-readable output
    python3 scripts/install-doctor.py inventory       # Count installed components

Exit codes:
    0 — All checks passed
    1 — One or more checks failed
    2 — Script error
"""

import json
import os
import sys
import importlib
from pathlib import Path


CLAUDE_DIR = Path.home() / ".claude"
COMPONENTS = ["agents", "skills", "hooks", "commands", "scripts"]


def check_claude_dir() -> dict:
    """Check if ~/.claude exists."""
    exists = CLAUDE_DIR.is_dir()
    return {
        "name": "claude_dir",
        "label": "~/.claude directory exists",
        "passed": exists,
        "detail": str(CLAUDE_DIR) if exists else "Directory not found. Run install.sh first.",
    }


def check_components_installed() -> list[dict]:
    """Check each component directory exists in ~/.claude."""
    results = []
    for comp in COMPONENTS:
        target = CLAUDE_DIR / comp
        is_symlink = target.is_symlink()
        is_dir = target.is_dir()
        exists = is_symlink or is_dir

        if is_symlink:
            link_target = os.readlink(target)
            detail = f"symlink -> {link_target}"
            # Check if symlink target actually exists
            if not target.resolve().exists():
                detail = f"BROKEN symlink -> {link_target}"
                exists = False
        elif is_dir:
            detail = "copied directory"
        else:
            detail = "Not found. Run install.sh."

        results.append({
            "name": f"component_{comp}",
            "label": f"~/.claude/{comp}",
            "passed": exists,
            "detail": detail,
        })
    return results


def check_settings_json() -> dict:
    """Check if settings.json exists and has hooks configured."""
    settings_file = CLAUDE_DIR / "settings.json"
    if not settings_file.exists():
        return {
            "name": "settings_json",
            "label": "settings.json exists with hooks",
            "passed": False,
            "detail": "settings.json not found. Run install.sh to create it.",
        }

    try:
        with open(settings_file) as f:
            settings = json.load(f)
    except json.JSONDecodeError as e:
        return {
            "name": "settings_json",
            "label": "settings.json exists with hooks",
            "passed": False,
            "detail": f"settings.json is invalid JSON: {e}",
        }

    has_hooks = "hooks" in settings and len(settings.get("hooks", {})) > 0
    hook_events = list(settings.get("hooks", {}).keys()) if has_hooks else []

    return {
        "name": "settings_json",
        "label": "settings.json exists with hooks",
        "passed": has_hooks,
        "detail": f"Hook events configured: {', '.join(hook_events)}" if has_hooks else "No hooks configured. Run install.sh.",
    }


def check_hook_files() -> list[dict]:
    """Check that hooks referenced in settings.json actually exist."""
    settings_file = CLAUDE_DIR / "settings.json"
    results = []

    if not settings_file.exists():
        return [{
            "name": "hook_files",
            "label": "Hook files exist",
            "passed": False,
            "detail": "Cannot check — settings.json missing",
        }]

    try:
        with open(settings_file) as f:
            settings = json.load(f)
    except (json.JSONDecodeError, OSError):
        return [{
            "name": "hook_files",
            "label": "Hook files exist",
            "passed": False,
            "detail": "Cannot check — settings.json unreadable",
        }]

    hooks = settings.get("hooks", {})
    missing = []
    found = 0

    def extract_hook_commands(obj):
        """Recursively extract command strings from nested hook structures."""
        commands = []
        if isinstance(obj, dict):
            if "command" in obj:
                commands.append(obj["command"])
            if "hooks" in obj and isinstance(obj["hooks"], list):
                for item in obj["hooks"]:
                    commands.extend(extract_hook_commands(item))
        elif isinstance(obj, list):
            for item in obj:
                commands.extend(extract_hook_commands(item))
        return commands

    for event, hook_list in hooks.items():
        for cmd in extract_hook_commands(hook_list):
            # Expand $HOME and strip quotes
            cmd_expanded = cmd.replace("$HOME", str(Path.home()))
            cmd_expanded = cmd_expanded.replace('"', '').replace("'", "")
            parts = cmd_expanded.split()
            for part in parts:
                if part.endswith(".py"):
                    path = Path(part)
                    if path.exists():
                        found += 1
                    else:
                        missing.append(f"{event}: {path.name}")
                    break

    if missing:
        return [{
            "name": "hook_files",
            "label": "Hook script files exist",
            "passed": False,
            "detail": f"{found} found, {len(missing)} missing: {', '.join(missing[:5])}",
        }]

    return [{
        "name": "hook_files",
        "label": "Hook script files exist",
        "passed": True,
        "detail": f"All {found} hook scripts found",
    }]


def check_python_version() -> dict:
    """Check Python version is 3.10+."""
    major, minor = sys.version_info.major, sys.version_info.minor
    passed = major >= 3 and minor >= 10
    return {
        "name": "python_version",
        "label": "Python 3.10+",
        "passed": passed,
        "detail": f"Python {major}.{minor}.{sys.version_info.micro}",
    }


def check_python_deps() -> list[dict]:
    """Check required Python dependencies are importable."""
    deps = [
        ("yaml", "PyYAML", True),
        ("requests", "requests", False),
        ("dotenv", "python-dotenv", False),
    ]
    results = []
    for module, package, required in deps:
        try:
            importlib.import_module(module)
            passed = True
            detail = "installed"
        except ImportError:
            passed = False
            suffix = "REQUIRED" if required else "optional"
            detail = f"Not installed ({suffix}). Run: pip install {package}"

        results.append({
            "name": f"dep_{module}",
            "label": f"Python: {package}",
            "passed": passed if required else True,  # Optional deps don't fail
            "detail": detail,
            "required": required,
        })
    return results


def check_learning_db() -> dict:
    """Check if learning.db is accessible."""
    db_path = CLAUDE_DIR / "learning.db"
    if not db_path.exists():
        return {
            "name": "learning_db",
            "label": "learning.db exists",
            "passed": True,  # Not existing is fine for fresh installs
            "detail": "Not yet created (will be created on first use)",
        }

    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT count(*) FROM learnings")
        count = cursor.fetchone()[0]
        conn.close()
        return {
            "name": "learning_db",
            "label": "learning.db accessible",
            "passed": True,
            "detail": f"{count} entries",
        }
    except Exception as e:
        return {
            "name": "learning_db",
            "label": "learning.db accessible",
            "passed": False,
            "detail": f"Error: {e}",
        }


def check_permissions() -> list[dict]:
    """Check that hook and script files are executable."""
    results = []
    for subdir in ["hooks", "scripts"]:
        target = CLAUDE_DIR / subdir
        if not target.is_dir():
            continue

        # Resolve symlinks
        real_dir = target.resolve()
        non_exec = []
        total = 0

        for f in real_dir.glob("*.py"):
            if f.name == "__init__.py":
                continue
            total += 1
            if not os.access(f, os.X_OK):
                non_exec.append(f.name)

        if non_exec:
            results.append({
                "name": f"perms_{subdir}",
                "label": f"{subdir}/*.py executable",
                "passed": False,
                "detail": f"{len(non_exec)}/{total} not executable: {', '.join(non_exec[:3])}{'...' if len(non_exec) > 3 else ''}",
            })
        else:
            results.append({
                "name": f"perms_{subdir}",
                "label": f"{subdir}/*.py executable",
                "passed": True,
                "detail": f"All {total} files OK",
            })
    return results


def inventory() -> dict:
    """Count installed components."""
    counts = {}
    for comp in COMPONENTS:
        target = CLAUDE_DIR / comp
        if not target.is_dir():
            counts[comp] = 0
            continue

        real_dir = target.resolve()
        if comp == "agents":
            counts[comp] = len([f for f in real_dir.glob("*.md") if f.name != "README.md" and f.name != "INDEX.json"])
        elif comp == "skills":
            counts[comp] = len(list(real_dir.glob("*/SKILL.md")))
            counts["skills_invocable"] = len([
                f for f in real_dir.glob("*/SKILL.md")
                if "user-invocable: true" in f.read_text(errors="ignore")
            ])
        elif comp == "hooks":
            counts[comp] = len([f for f in real_dir.glob("*.py") if f.name != "__init__.py"])
        elif comp == "commands":
            counts[comp] = len([f for f in real_dir.glob("*.md") if f.name != "README.md"])
        elif comp == "scripts":
            counts[comp] = len([f for f in real_dir.glob("*.py") if f.name != "__init__.py"])

    return counts


def run_all_checks() -> list[dict]:
    """Run all checks and return results."""
    results = []
    results.append(check_claude_dir())
    results.extend(check_components_installed())
    results.append(check_settings_json())
    results.extend(check_hook_files())
    results.append(check_python_version())
    results.extend(check_python_deps())
    results.append(check_learning_db())
    results.extend(check_permissions())
    return results


def print_results(results: list[dict]) -> bool:
    """Print results in human-readable format. Returns True if all passed."""
    all_passed = True
    for r in results:
        icon = "\u2713" if r["passed"] else "\u2717"
        status = "PASS" if r["passed"] else "FAIL"
        print(f"  [{icon}] {r['label']}: {r['detail']}")
        if not r["passed"]:
            all_passed = False
    return all_passed


def main():
    if len(sys.argv) < 2:
        print("Usage: install-doctor.py [check|inventory] [--json]")
        sys.exit(2)

    command = sys.argv[1]
    use_json = "--json" in sys.argv

    if command == "check":
        results = run_all_checks()
        if use_json:
            print(json.dumps({"checks": results, "all_passed": all(r["passed"] for r in results)}, indent=2))
        else:
            print("\n  Claude Code Toolkit — Installation Health Check\n")
            all_passed = print_results(results)
            passed = sum(1 for r in results if r["passed"])
            total = len(results)
            print(f"\n  Result: {passed}/{total} checks passed\n")
            if not all_passed:
                print("  Run install.sh to fix issues, or use /install for guided setup.\n")

        sys.exit(0 if all(r["passed"] for r in results) else 1)

    elif command == "inventory":
        counts = inventory()
        if use_json:
            print(json.dumps(counts, indent=2))
        else:
            print("\n  Installed Components:\n")
            print(f"  Agents:   {counts.get('agents', 0)}")
            print(f"  Skills:   {counts.get('skills', 0)} ({counts.get('skills_invocable', 0)} user-invocable)")
            print(f"  Hooks:    {counts.get('hooks', 0)}")
            print(f"  Commands: {counts.get('commands', 0)}")
            print(f"  Scripts:  {counts.get('scripts', 0)}")
            print()
        sys.exit(0)

    else:
        print(f"Unknown command: {command}")
        sys.exit(2)


if __name__ == "__main__":
    main()
