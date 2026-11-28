#!/usr/bin/env python3
# hook-version: 1.1.0
"""
PreToolUse:Agent Hook: Section-Integrity Validator

Advisory hook that validates subagent_type before Agent dispatch. The repo's
specialist agents are retired (plans/009): the worker is the built-in
general-purpose agent and the skill carries the domain. Valid names are the
harness built-ins (case-insensitive) plus private overlay agents from the
resolved agents index, minus the retired names. Catches three mistakes:

1. Dispatching with a skill name instead of an agent name (the harness rejects
   this but the error is confusing).
2. Dispatching a retired specialist agent.
3. Dispatching with a name that exists nowhere (typo or stale name).

This is ADVISORY only -- exit 0 always, never blocks.

Enforces with an exit code what a prompt can only ask for (PHILOSOPHY.md:
exact, repeatable checks belong in programs). Replaces the prose-only "SECTION-INTEGRITY RULE" in
skills/meta/do/SKILL.md with a real hook.

ARCH-002.
"""

import sys  # vexjoy-pyguard

if sys.version_info < (3, 10):  # vexjoy-pyguard advisory
    import os

    if not os.environ.get("VEXJOY_PYGUARD_REEXEC"):
        os.environ["VEXJOY_PYGUARD_REEXEC"] = "1"
        for _d in [*os.environ.get("PATH", "").split(os.pathsep), "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"]:
            for _v in ("14", "13", "12", "11", "10"):
                _p = os.path.join(_d, "python3." + _v)
                if _d and "/shims" not in _d and os.access(_p, os.X_OK):
                    os.execv(_p, [_p, *sys.argv])
    sys.stderr.write(
        "[vexjoy] hook %s needs Python 3.10+, got %s (%s); run ./install.sh in vexjoy-agent from a terminal"
        " outside Claude Code (gated tool calls stay blocked until then)\n"
        % (__file__.rsplit("/", 1)[-1], sys.version.split()[0], sys.executable)
    )
    sys.exit(0)

import json
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import context_output, hook_error
from stdin_timeout import read_stdin

_EVENT_NAME = "PreToolUse"

# Cache INDEX data per process (one invocation = one process, so this is just
# a guard against accidental double-load).
_agents_cache: set[str] | None = None
_skills_cache: set[str] | None = None

# Harness-provided agent types, valid without any index entry. Compared lower-case.
BUILTIN_AGENTS = frozenset(
    {
        "general-purpose",
        "fork",
        "explore",
        "plan",
        "claude",
        "statusline-setup",
        "claude-code-guide",
        "web-fetch",
    }
)

# Antigravity CLI built-in subagent types (valid only under Antigravity).
AGY_BUILTIN_AGENTS = frozenset({"self", "research", "image-generator"})


def _is_antigravity_runtime(event: dict) -> bool:
    """Return True when the hook is running under the Antigravity CLI runtime."""
    return (
        os.environ.get("VEXJOY_HOOK_RUNTIME") == "antigravity"
        or os.environ.get("ANTIGRAVITY_AGENT") == "1"
        or event.get("agy_tool_name") == "invoke_subagent"
    )


def _load_index_names(index_path: Path, key: str) -> set[str]:
    """Load names from an INDEX.json file. Returns empty set on any error."""
    try:
        with open(index_path) as f:
            data = json.load(f)
        entries = data.get(key, {})
        if isinstance(entries, dict):
            return set(entries.keys())
        return set()
    except (OSError, json.JSONDecodeError, KeyError):
        return set()


def _resolver():
    """``routing_index_merge`` from the toolkit's scripts/, or None (fail open)."""
    scripts = Path(__file__).resolve().parent.parent / "scripts"
    if not (scripts / "routing_index_merge.py").is_file():
        return None
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    try:
        import routing_index_merge
    except Exception:
        return None
    return routing_index_merge


def _resolved_names(kind: str, project_root: Path) -> set[str]:
    """Names of *kind* via the resolver (installer spec 7.2): installed index
    first, else the project's ``<kind>/INDEX.json`` (+ legacy local). Falls back
    to the plain project index when the resolver is unavailable or fails."""
    tracked = project_root / kind / "INDEX.json"
    rim = _resolver()
    if rim is not None:
        try:
            target = rim.detect_target(__file__)
            items = rim.load_resolved_items(
                kind, target, fallback=(tracked, "INDEX.local.json"), repo_root=project_root
            )
            return {str(name) for name in items}
        except Exception:
            pass
    return _load_index_names(tracked, kind)


def _find_project_root(event: dict) -> Path:
    """Resolve project root from event cwd or env fallback."""
    cwd_str = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR", ".")
    return Path(cwd_str).resolve()


def _retired_agents() -> frozenset[str]:
    rim = _resolver()
    return frozenset(getattr(rim, "RETIRED_AGENTS", frozenset())) if rim is not None else frozenset()


def _get_agent_names(project_root: Path) -> set[str]:
    """Valid agent names, lower-case: built-ins plus overlay agents, minus retired ones.

    A stale install still lists the retired repo agents, so they are subtracted.
    """
    global _agents_cache
    if _agents_cache is not None:
        return _agents_cache
    indexed = {name.lower() for name in _resolved_names("agents", project_root)}
    _agents_cache = (indexed - _retired_agents()) | BUILTIN_AGENTS
    return _agents_cache


def _get_skill_names(project_root: Path) -> set[str]:
    """Return set of skill names from the resolved skills index."""
    global _skills_cache
    if _skills_cache is not None:
        return _skills_cache
    _skills_cache = _resolved_names("skills", project_root)
    return _skills_cache


_BYPASS_ENV = "PRETOOL_SECTION_INTEGRITY_VALIDATOR_BYPASS"


def main() -> None:
    """Validate subagent_type against INDEX files."""
    if os.environ.get(_BYPASS_ENV) == "1":
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print(
                "[pretool-section-integrity-validator] Bypassed via PRETOOL_SECTION_INTEGRITY_VALIDATOR_BYPASS=1",
                file=sys.stderr,
            )
        sys.exit(0)

    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    raw = read_stdin(timeout=2)
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    # Only act on Agent tool dispatches.
    tool_name = event.get("tool_name", "")
    if tool_name != "Agent":
        sys.exit(0)

    tool_input = event.get("tool_input", {})
    subagent_type = tool_input.get("subagent_type")

    # No subagent_type or empty -- default agent, allow through.
    if not subagent_type:
        if debug:
            print(
                "[section-integrity] No subagent_type -- default agent, allowing",
                file=sys.stderr,
            )
        sys.exit(0)

    subagent_type = str(subagent_type).strip()
    if not subagent_type:
        sys.exit(0)

    project_root = _find_project_root(event)
    agent_names = _get_agent_names(project_root)
    if _is_antigravity_runtime(event):
        agent_names = agent_names | AGY_BUILTIN_AGENTS
    skill_names = _get_skill_names(project_root)

    if debug:
        print(
            f"[section-integrity] subagent_type={subagent_type!r}, "
            f"agents={len(agent_names)}, skills={len(skill_names)}",
            file=sys.stderr,
        )

    # Valid agent name -- allow silently.
    if subagent_type.lower() in agent_names:
        if debug:
            print(
                f"[section-integrity] '{subagent_type}' is a valid agent -- allowing",
                file=sys.stderr,
            )
        sys.exit(0)

    # Skill name used as agent -- warn with guidance.
    if subagent_type in skill_names:
        warning = (
            f"[section-integrity] WARNING: '{subagent_type}' is a skill name, not an agent name. "
            f"The harness will reject this dispatch. Consider using 'general-purpose' as the "
            f"agent and '{subagent_type}' as a skill."
        )
        if debug:
            print(warning, file=sys.stderr)
        context_output(_EVENT_NAME, warning).print_and_exit(0)

    # Retired specialist agent -- point at the worker + skill contract.
    if subagent_type.lower() in _retired_agents():
        warning = (
            f"[section-integrity] WARNING: '{subagent_type}' is a retired agent. Dispatch "
            f"'general-purpose' and load the skill that now holds its domain."
        )
        if debug:
            print(warning, file=sys.stderr)
        context_output(_EVENT_NAME, warning).print_and_exit(0)

    # Unknown everywhere -- warn about potential typo.
    warning = (
        f"[section-integrity] WARNING: '{subagent_type}' is not a built-in agent, an overlay agent, "
        f"or a skill. This may cause a dispatch failure."
    )
    if debug:
        print(warning, file=sys.stderr)
    context_output(_EVENT_NAME, warning).print_and_exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        hook_error("pretool-section-integrity-validator", e)
