#!/usr/bin/env python3
"""
install-doctor.py — Deterministic health checks for Claude Code Toolkit installation.

Usage:
    python3 scripts/install-doctor.py check          # From repo root
    python3 ~/.claude/scripts/install-doctor.py check # From anywhere
    python3 scripts/install-doctor.py check --json    # Machine-readable output
    python3 scripts/install-doctor.py inventory       # Count installed components
    python3 scripts/install-doctor.py mcp             # List MCP servers from registry

Exit codes:
    0 — All checks passed
    1 — One or more checks failed
    2 — Script error
"""

import importlib
import importlib.util
import json
import os
import shlex
import sys
from pathlib import Path

CLAUDE_DIR = Path.home() / ".claude"
CODEX_DIR = Path.home() / ".codex"
COMPONENTS = ["agents", "skills", "hooks", "commands", "scripts"]


def _is_toolkit_repo(path: Path) -> bool:
    """Return True when a path looks like the toolkit repo root."""
    return (path / "skills").is_dir() and (path / "agents").is_dir() and (path / "hooks").is_dir()


def get_toolkit_repo_root() -> Path | None:
    """Locate the source repo root for comparisons against the Codex mirror."""
    repo_candidate = Path(__file__).resolve().parent.parent
    if _is_toolkit_repo(repo_candidate):
        return repo_candidate

    manifest_path = CLAUDE_DIR / ".install-manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    toolkit_path = manifest.get("toolkit_path")
    if not toolkit_path:
        return None

    manifest_repo = Path(toolkit_path).expanduser()
    return manifest_repo if _is_toolkit_repo(manifest_repo) else None


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
    """Check each component directory exists in ~/.claude and validate symlink targets."""
    results = []
    for comp in COMPONENTS:
        target = CLAUDE_DIR / comp
        is_symlink = target.is_symlink()
        is_dir = target.is_dir()
        exists = is_symlink or is_dir

        if is_symlink:
            try:
                link_target = os.readlink(target)
            except OSError as e:
                results.append(
                    {
                        "name": f"component_{comp}",
                        "label": f"~/.claude/{comp}",
                        "passed": False,
                        "detail": f"Symlink exists but cannot be read: {e}",
                    }
                )
                continue
            detail = f"symlink -> {link_target}"
            if not target.resolve().exists():
                detail = f"BROKEN symlink -> {link_target}"
                exists = False
        elif is_dir:
            detail = "copied directory"
        else:
            detail = "Not found. Run install.sh."

        results.append(
            {
                "name": f"component_{comp}",
                "label": f"~/.claude/{comp}",
                "passed": exists,
                "detail": detail,
            }
        )
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
    except OSError as e:
        return {
            "name": "settings_json",
            "label": "settings.json exists with hooks",
            "passed": False,
            "detail": f"settings.json exists but cannot be read: {e}",
        }

    has_hooks = "hooks" in settings and len(settings.get("hooks", {})) > 0
    hook_events = list(settings.get("hooks", {}).keys()) if has_hooks else []

    return {
        "name": "settings_json",
        "label": "settings.json exists with hooks",
        "passed": has_hooks,
        "detail": f"Hook events configured: {', '.join(hook_events)}"
        if has_hooks
        else "No hooks configured. Run install.sh.",
    }


def check_codex_skills() -> dict:
    """Check that toolkit skills are mirrored into ~/.codex/skills."""
    codex_skills_dir = CODEX_DIR / "skills"
    repo_root = get_toolkit_repo_root()

    if repo_root is None:
        return {
            "name": "codex_skills",
            "label": "~/.codex/skills mirror",
            "passed": codex_skills_dir.is_dir(),
            "detail": str(codex_skills_dir)
            if codex_skills_dir.is_dir()
            else "Codex skills mirror not found. Run install.sh from the toolkit repo.",
        }

    expected_entries = [item.name for item in sorted((repo_root / "skills").iterdir())]

    private_skills_dir = repo_root / "private-skills"
    if private_skills_dir.is_dir():
        for skill_dir in sorted(private_skills_dir.iterdir()):
            expected_entries.append(skill_dir.name)

    private_voices_dir = repo_root / "private-voices"
    if private_voices_dir.is_dir():
        for voice_dir in sorted(private_voices_dir.iterdir()):
            if (voice_dir / "skill").is_dir():
                expected_entries.append(f"voice-{voice_dir.name}")

    expected_entries = list(dict.fromkeys(expected_entries))

    if not codex_skills_dir.is_dir():
        return {
            "name": "codex_skills",
            "label": "~/.codex/skills mirror",
            "passed": False,
            "detail": "Directory not found. Run install.sh to mirror toolkit skills for Codex.",
        }

    missing = [entry for entry in expected_entries if not (codex_skills_dir / entry).exists()]
    if missing:
        return {
            "name": "codex_skills",
            "label": "~/.codex/skills mirror",
            "passed": False,
            "detail": f"{len(expected_entries) - len(missing)}/{len(expected_entries)} entries present; missing: {', '.join(missing[:5])}",
        }

    return {
        "name": "codex_skills",
        "label": "~/.codex/skills mirror",
        "passed": True,
        "detail": f"All {len(expected_entries)} toolkit entries mirrored",
    }


def check_codex_agents() -> dict:
    """Check that toolkit agents are mirrored into ~/.codex/agents."""
    codex_agents_dir = CODEX_DIR / "agents"
    repo_root = get_toolkit_repo_root()

    if repo_root is None:
        return {
            "name": "codex_agents",
            "label": "~/.codex/agents mirror",
            "passed": codex_agents_dir.is_dir(),
            "detail": str(codex_agents_dir)
            if codex_agents_dir.is_dir()
            else "Codex agents mirror not found. Run install.sh from the toolkit repo.",
        }

    expected_entries = [item.name for item in sorted((repo_root / "agents").iterdir())]

    private_agents_dir = repo_root / "private-agents"
    if private_agents_dir.is_dir():
        for agent_item in sorted(private_agents_dir.iterdir()):
            expected_entries.append(agent_item.name)

    expected_entries = list(dict.fromkeys(expected_entries))

    if not codex_agents_dir.is_dir():
        return {
            "name": "codex_agents",
            "label": "~/.codex/agents mirror",
            "passed": False,
            "detail": "Directory not found. Run install.sh to mirror toolkit agents for Codex.",
        }

    missing = [entry for entry in expected_entries if not (codex_agents_dir / entry).exists()]
    if missing:
        return {
            "name": "codex_agents",
            "label": "~/.codex/agents mirror",
            "passed": False,
            "detail": f"{len(expected_entries) - len(missing)}/{len(expected_entries)} entries present; missing: {', '.join(missing[:5])}",
        }

    return {
        "name": "codex_agents",
        "label": "~/.codex/agents mirror",
        "passed": True,
        "detail": f"All {len(expected_entries)} toolkit entries mirrored",
    }


def check_hook_files() -> list[dict]:
    """Check that hooks referenced in settings.json actually exist."""
    settings_file = CLAUDE_DIR / "settings.json"
    results = []

    if not settings_file.exists():
        return [
            {
                "name": "hook_files",
                "label": "Hook files exist",
                "passed": False,
                "detail": "Cannot check — settings.json missing",
            }
        ]

    try:
        with open(settings_file) as f:
            settings = json.load(f)
    except (json.JSONDecodeError, OSError):
        return [
            {
                "name": "hook_files",
                "label": "Hook files exist",
                "passed": False,
                "detail": "Cannot check — settings.json unreadable",
            }
        ]

    hooks = settings.get("hooks", {})
    missing = []
    found = 0

    def extract_python_paths(command: str) -> list[Path]:
        """Extract Python script paths from a hook command."""
        expanded = os.path.expandvars(command)
        try:
            parts = shlex.split(expanded)
        except ValueError:
            parts = expanded.replace('"', "").replace("'", "").split()

        paths = []
        for part in parts:
            resolved = Path(os.path.expanduser(part))
            if resolved.suffix.lower() == ".py":
                paths.append(resolved)
        return paths

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
            for path in extract_python_paths(cmd):
                if path.exists():
                    found += 1
                else:
                    missing.append(f"{event}: {path.name}")

    if missing:
        return [
            {
                "name": "hook_files",
                "label": "Hook script files exist",
                "passed": False,
                "detail": f"{found} found, {len(missing)} missing: {', '.join(missing[:5])}",
            }
        ]

    return [
        {
            "name": "hook_files",
            "label": "Hook script files exist",
            "passed": True,
            "detail": f"All {found} hook scripts found",
        }
    ]


def check_python_version() -> dict:
    """Check Python version is 3.10+."""
    major, minor = sys.version_info.major, sys.version_info.minor
    passed = (major, minor) >= (3, 10)
    return {
        "name": "python_version",
        "label": "Python 3.10+",
        "passed": passed,
        "detail": f"Python {major}.{minor}.{sys.version_info.micro}",
    }


def check_python_deps() -> list[dict]:
    """Check Python dependencies (required and optional) are importable."""
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

        if not required and not passed:
            detail = f"Not installed (optional)"

        results.append(
            {
                "name": f"dep_{module}",
                "label": f"Python: {package}",
                "passed": passed if required else True,
                "detail": detail,
                "required": required,
            }
        )
    return results


def check_learning_db() -> dict:
    """Check learning.db existence and table accessibility. Absence is acceptable for fresh installs."""
    import sqlite3

    env_learning_dir = os.environ.get("CLAUDE_LEARNING_DIR")
    candidates = []
    if env_learning_dir:
        candidates.append(Path(env_learning_dir).expanduser() / "learning.db")
    candidates.append(CLAUDE_DIR / "learning" / "learning.db")
    candidates.append(CLAUDE_DIR / "learning.db")

    db_path = next((path for path in candidates if path.exists()), candidates[0])
    if not db_path.exists():
        return {
            "name": "learning_db",
            "label": "learning.db exists",
            "passed": True,
            "detail": f"Not yet created (expected at {db_path})",
        }

    try:
        conn = sqlite3.connect(str(db_path))
        try:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "learnings" not in tables:
                available = ", ".join(sorted(tables)[:5]) or "no tables"
                return {
                    "name": "learning_db",
                    "label": "learning.db accessible",
                    "passed": False,
                    "detail": f"Unsupported schema at {db_path} (missing learnings table; found: {available})",
                }
            cursor = conn.execute("SELECT count(*) FROM learnings")
            count = cursor.fetchone()[0]
            schema_version = conn.execute("PRAGMA user_version").fetchone()[0]
        finally:
            conn.close()
        return {
            "name": "learning_db",
            "label": "learning.db accessible",
            "passed": True,
            "detail": f"{db_path} ({count} entries, schema v{schema_version})",
        }
    except sqlite3.OperationalError as e:
        return {
            "name": "learning_db",
            "label": "learning.db accessible",
            "passed": False,
            "detail": f"Database error (table missing or schema mismatch?): {e}",
        }
    except sqlite3.DatabaseError as e:
        return {
            "name": "learning_db",
            "label": "learning.db accessible",
            "passed": False,
            "detail": f"Database is corrupt or unreadable: {e}",
        }
    except OSError as e:
        return {
            "name": "learning_db",
            "label": "learning.db accessible",
            "passed": False,
            "detail": f"Cannot open file: {e}",
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
            results.append(
                {
                    "name": f"perms_{subdir}",
                    "label": f"{subdir}/*.py executable",
                    "passed": False,
                    "detail": f"{len(non_exec)}/{total} not executable: {', '.join(non_exec[:3])}{'...' if len(non_exec) > 3 else ''}",
                }
            )
        else:
            results.append(
                {
                    "name": f"perms_{subdir}",
                    "label": f"{subdir}/*.py executable",
                    "passed": True,
                    "detail": f"All {total} files OK",
                }
            )
    return results


def check_mcp_servers() -> list[dict]:
    """Check which MCP servers from the registry are configured.

    Loads the REGISTRY from mcp-registry.py (same directory) and checks
    whether each server's tool_prefix appears in the mcpServers key of
    ~/.claude/settings.json or ~/.claude/settings.local.json.
    """
    results = []

    # Import REGISTRY from mcp-registry.py in the same directory
    script_dir = Path(__file__).resolve().parent
    registry_path = script_dir / "mcp-registry.py"
    if not registry_path.exists():
        return [
            {
                "name": "mcp_registry",
                "label": "MCP registry available",
                "passed": True,
                "detail": "mcp-registry.py not found (MCP inventory not available yet)",
            }
        ]

    try:
        spec = importlib.util.spec_from_file_location("mcp_registry", registry_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        registry = getattr(mod, "REGISTRY", None)
    except Exception as e:
        return [
            {
                "name": "mcp_registry",
                "label": "MCP registry loadable",
                "passed": False,
                "detail": f"Failed to load mcp-registry.py: {e}",
            }
        ]

    if not registry:
        return [
            {
                "name": "mcp_registry",
                "label": "MCP registry has entries",
                "passed": True,
                "detail": "REGISTRY is empty or not defined",
            }
        ]

    # Collect configured mcpServers keys from settings files
    configured_servers: set[str] = set()
    for settings_name in ["settings.json", "settings.local.json"]:
        settings_path = CLAUDE_DIR / settings_name
        if not settings_path.exists():
            continue
        try:
            with open(settings_path) as f:
                data = json.load(f)
            for key in data.get("mcpServers", {}):
                configured_servers.add(key)
        except (json.JSONDecodeError, OSError):
            continue

    # Also check ~/.claude.json (global config)
    global_config = Path.home() / ".claude.json"
    if global_config.exists():
        try:
            with open(global_config) as f:
                data = json.load(f)
            for key in data.get("mcpServers", {}):
                configured_servers.add(key)
        except (json.JSONDecodeError, OSError):
            pass

    for key, entry in registry.items():
        display_name = entry.get("name", key)
        # Match if the registry key appears in configured server names
        found = key in configured_servers
        results.append(
            {
                "name": f"mcp_{key}",
                "label": f"MCP: {display_name}",
                "passed": found,
                "detail": "configured" if found else "not configured",
            }
        )

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
            counts[comp] = len([f for f in real_dir.glob("*.md") if f.name != "README.md"])
        elif comp == "skills":
            counts[comp] = len(list(real_dir.glob("*/SKILL.md")))
            invocable = 0
            for f in real_dir.glob("*/SKILL.md"):
                try:
                    if "user-invocable: true" in f.read_text(errors="ignore"):
                        invocable += 1
                except OSError:
                    pass
            counts["skills_invocable"] = invocable
        elif comp == "hooks":
            counts[comp] = len([f for f in real_dir.glob("*.py") if f.name != "__init__.py"])
        elif comp == "commands":
            counts[comp] = len([f for f in real_dir.glob("*.md") if f.name != "README.md"])
        elif comp == "scripts":
            counts[comp] = len([f for f in real_dir.glob("*.py") if f.name != "__init__.py"])

    codex_skills_dir = CODEX_DIR / "skills"
    if codex_skills_dir.is_dir():
        counts["codex_skills"] = len(list(codex_skills_dir.glob("*/SKILL.md")))
    else:
        counts["codex_skills"] = 0

    codex_agents_dir = CODEX_DIR / "agents"
    if codex_agents_dir.is_dir():
        counts["codex_agents"] = len([f for f in codex_agents_dir.glob("*.md") if f.name != "README.md"])
    else:
        counts["codex_agents"] = 0

    # Count MCP servers from registry
    mcp_results = check_mcp_servers()
    mcp_total = sum(1 for r in mcp_results if r["name"].startswith("mcp_") and r["name"] != "mcp_registry")
    mcp_configured = sum(
        1 for r in mcp_results if r["name"].startswith("mcp_") and r["name"] != "mcp_registry" and r["passed"]
    )
    counts["mcps"] = mcp_total
    counts["mcps_configured"] = mcp_configured

    return counts


def run_all_checks() -> list[dict]:
    """Run all checks and return results."""
    results = []
    results.append(check_claude_dir())
    results.extend(check_components_installed())
    results.append(check_codex_skills())
    results.append(check_codex_agents())
    results.append(check_settings_json())
    results.extend(check_hook_files())
    results.append(check_python_version())
    results.extend(check_python_deps())
    results.append(check_learning_db())
    results.extend(check_permissions())
    results.extend(check_mcp_servers())
    return results


def print_results(results: list[dict]) -> bool:
    """Print results in human-readable format. Returns True if all passed."""
    all_passed = True
    for r in results:
        icon = "\u2713" if r["passed"] else "\u2717"
        print(f"  [{icon}] {r['label']}: {r['detail']}")
        if not r["passed"]:
            all_passed = False
    return all_passed


def main():
    if len(sys.argv) < 2:
        print("Usage: install-doctor.py [check|inventory|mcp] [--json]")
        sys.exit(2)

    try:
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
                print(
                    f"  Codex:    {counts.get('codex_skills', 0)} skills available, "
                    f"{counts.get('codex_agents', 0)} agents available"
                )
                print(f"  Hooks:    {counts.get('hooks', 0)}")
                print(f"  Commands: {counts.get('commands', 0)}")
                print(f"  Scripts:  {counts.get('scripts', 0)}")
                print(f"  MCPs:     {counts.get('mcps', 0)} ({counts.get('mcps_configured', 0)} configured)")
                print()
            sys.exit(0)

        elif command == "mcp":
            import subprocess

            # Delegate to mcp-registry.py list
            script_dir = Path(__file__).resolve().parent
            registry_script = script_dir / "mcp-registry.py"
            if not registry_script.exists():
                print("mcp-registry.py not found. MCP inventory not available yet.", file=sys.stderr)
                sys.exit(2)
            result = subprocess.run(
                [sys.executable, str(registry_script), "list"],
                check=False,
            )
            sys.exit(result.returncode)

        else:
            print(f"Unknown command: {command}")
            sys.exit(2)

    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        print(f"install-doctor.py internal error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
