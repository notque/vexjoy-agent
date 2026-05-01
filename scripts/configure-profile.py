#!/usr/bin/env python3
"""Interactive TUI to build .local/profile.yaml.

Runs three multi-select checkbox prompts (skills / agents / hooks). All items
are pre-selected as ENABLED; the user un-checks items to disable them. On
confirm, writes ``<repo>/.local/profile.yaml`` with the disabled lists.

Sources:
    - skills: top-level subdirectories of skills/ that contain SKILL.md
    - agents: agents/<name>.md (excluding README*)
    - hooks:  hooks/*.py (excluding __init__.py and the lib/ package)

Requires the ``questionary`` package. If it is not installed, prints an
install hint and exits 1.

Usage:
    python3 scripts/configure-profile.py
    python3 scripts/configure-profile.py --output .local/profile.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / ".local" / "profile.yaml"

PROFILE_HEADER = """\
# Toolkit profile — items listed here are excluded by ./install.sh.
#
# This file is regenerated each time you run:
#   ./install.sh --configure
#
# To install without prompting (using the lists below as-is), pass
# --non-interactive to install.sh, or simply run ./install.sh.
"""


def list_skills() -> list[str]:
    skills_dir = REPO_ROOT / "skills"
    if not skills_dir.is_dir():
        return []
    names: list[str] = []
    for entry in sorted(skills_dir.iterdir()):
        if entry.is_dir() and (entry / "SKILL.md").is_file():
            names.append(entry.name)
    return names


def list_agents() -> list[str]:
    agents_dir = REPO_ROOT / "agents"
    if not agents_dir.is_dir():
        return []
    names: list[str] = []
    for entry in sorted(agents_dir.glob("*.md")):
        stem = entry.stem
        if stem.upper().startswith("README"):
            continue
        names.append(stem)
    return names


def list_hooks() -> list[str]:
    hooks_dir = REPO_ROOT / "hooks"
    if not hooks_dir.is_dir():
        return []
    names: list[str] = []
    for entry in sorted(hooks_dir.glob("*.py")):
        if entry.name == "__init__.py":
            continue
        names.append(entry.name)
    return names


def run_prompts(skills: list[str], agents: list[str], hooks: list[str]) -> dict[str, list[str]]:
    try:
        import questionary
    except ImportError:
        print(
            "error: 'questionary' is required for --configure.\n"
            "Install with: pip install questionary  (or pip install -r requirements.txt)",
            file=sys.stderr,
        )
        sys.exit(1)

    if not sys.stdin.isatty():
        print(
            "error: --configure requires an interactive terminal (TTY).\n"
            "Edit .local/profile.yaml by hand or run from a terminal.",
            file=sys.stderr,
        )
        sys.exit(1)

    def ask(label: str, items: list[str]) -> list[str]:
        if not items:
            return []
        choices = [questionary.Choice(name, checked=True) for name in items]
        result = questionary.checkbox(
            f"{label} — uncheck items to DISABLE (space toggles, enter confirms):",
            choices=choices,
        ).ask()
        if result is None:
            # User aborted (Ctrl-C / Esc).
            print("aborted: no changes written.", file=sys.stderr)
            sys.exit(130)
        enabled = set(result)
        return [name for name in items if name not in enabled]

    disabled_skills = ask("Skills", skills)
    disabled_agents = ask("Agents", agents)
    disabled_hooks = ask("Hooks", hooks)
    return {
        "skills": disabled_skills,
        "agents": disabled_agents,
        "hooks": disabled_hooks,
    }


def write_profile(path: Path, disabled: dict[str, list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = yaml.safe_dump({"disabled": disabled}, sort_keys=False, default_flow_style=False)
    path.write_text(PROFILE_HEADER + "\n" + body, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    skills = list_skills()
    agents = list_agents()
    hooks = list_hooks()

    disabled = run_prompts(skills, agents, hooks)
    write_profile(args.output, disabled)

    print(
        f"wrote {args.output} "
        f"(disabled: {len(disabled['skills'])} skills, "
        f"{len(disabled['agents'])} agents, {len(disabled['hooks'])} hooks)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
