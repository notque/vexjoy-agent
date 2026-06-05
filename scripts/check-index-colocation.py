#!/usr/bin/env python3
"""
WARN-ONLY metadata-consistency check: routing frontmatter changed without INDEX.

Flags when a diff changes an agent's (or skill's) routing-relevant frontmatter
but the corresponding INDEX entry's representation differs and was not refreshed
in the same change. It NEVER fails a build by default (exit 0). --strict makes
findings exit 1 — an escalation flag wired into no gate by this ADR.

ADR: agents-index-autosync (Part 2).

Routing-relevant fields (what the index generators read):
    routing.triggers, routing.not_for, routing.pairs_with, routing.complexity,
    routing.category, and description (drives short_description).

Usage:
    python3 scripts/check-index-colocation.py [--base REF] [--head REF]
    python3 scripts/check-index-colocation.py --staged
    python3 scripts/check-index-colocation.py --json
    python3 scripts/check-index-colocation.py --strict

Default (no range): working-tree diff vs HEAD.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# Reuse the agent index generator's frontmatter parser — single source of truth
# for what the INDEX captures.
_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))
import importlib.util

_gen_spec = importlib.util.spec_from_file_location("generate_agent_index", _SCRIPT_DIR / "generate-agent-index.py")
_gen = importlib.util.module_from_spec(_gen_spec)
_gen_spec.loader.exec_module(_gen)
extract_frontmatter = _gen.extract_frontmatter

AGENT_RE = re.compile(r"^agents/[^/]+\.md$")
SKILL_RE = re.compile(r"^skills/(?:[^/]+/)+SKILL\.md$")
ROUTING_FIELDS = ("triggers", "not_for", "pairs_with", "complexity", "category")


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)


def changed_files(base: str | None, head: str | None, staged: bool, cwd: Path) -> list[str]:
    """Return changed component files for the requested diff range."""
    if staged:
        args = ["diff", "--cached", "--name-only"]
    elif base:
        args = ["diff", f"{base}..{head or 'HEAD'}", "--name-only"]
    else:
        args = ["diff", "HEAD", "--name-only"]
    proc = _run_git(args, cwd)
    if proc.returncode != 0:
        return []
    files = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    return [f for f in files if AGENT_RE.match(f) or SKILL_RE.match(f)]


def _file_at_ref(path: str, ref: str | None, cwd: Path) -> str | None:
    """Content of path at a git ref. ref=None means the working tree."""
    if ref is None:
        p = cwd / path
        return p.read_text(encoding="utf-8") if p.is_file() else None
    proc = _run_git(["show", f"{ref}:{path}"], cwd)
    return proc.stdout if proc.returncode == 0 else None


def _index_view(content: str | None) -> dict:
    """Routing-relevant projection of a component file, as the INDEX would store it."""
    if not content:
        return {}
    fm = extract_frontmatter(content) or {}
    routing = fm.get("routing", {}) or {}
    view = {"description": fm.get("description", "")}
    for field in ROUTING_FIELDS:
        if field in routing:
            view[field] = routing[field]
    return view


def changed_routing_fields(old: dict, new: dict) -> list[str]:
    """Names of routing-relevant fields that differ between two index views."""
    changed = []
    for field in ("description", *ROUTING_FIELDS):
        if old.get(field) != new.get(field):
            label = field if field == "description" else f"routing.{field}"
            changed.append(label)
    return changed


def check(base: str | None, head: str | None, staged: bool, cwd: Path) -> list[dict]:
    """Return colocation findings: routing changed but INDEX entry would differ."""
    old_ref = base if base else "HEAD"
    new_ref = head if (base and head) else None  # None = working tree
    findings: list[dict] = []

    for path in changed_files(base, head, staged, cwd):
        old_view = _index_view(_file_at_ref(path, old_ref, cwd))
        new_view = _index_view(_file_at_ref(path, new_ref, cwd))
        fields = changed_routing_fields(old_view, new_view)
        if not fields:
            continue  # pure body edit — not a colocation warning
        component = "agents" if AGENT_RE.match(path) else "skills"
        findings.append(
            {
                "component": component,
                "file": path,
                "changed_fields": fields,
                # INDEX entry would change but the source diff didn't refresh it.
                "index_entry_changed": False,
            }
        )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="WARN-ONLY frontmatter<->INDEX colocation check.")
    parser.add_argument("--base", default=None, help="Base git ref (e.g. origin/main).")
    parser.add_argument("--head", default=None, help="Head git ref (default HEAD when --base given).")
    parser.add_argument("--staged", action="store_true", help="Check staged changes (git diff --cached).")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable findings.")
    parser.add_argument("--strict", action="store_true", help="Exit 1 on findings (escalation flag).")
    args = parser.parse_args()

    cwd = Path.cwd()
    findings = check(args.base, args.head, args.staged, cwd)

    if args.json:
        print(json.dumps(findings, indent=2))
    else:
        n_agents = sum(1 for f in findings if f["component"] == "agents")
        n_skills = sum(1 for f in findings if f["component"] == "skills")
        for f in findings:
            index_name = "agents/INDEX.json" if f["component"] == "agents" else "skills/INDEX.json"
            entry = Path(f["file"]).stem
            print(
                f"WARN: {f['file']} changed {', '.join(f['changed_fields'])} "
                f"but {index_name} entry '{entry}' unchanged in this diff"
            )
        print(f"{n_agents} agent file(s), {n_skills} skill file(s) flagged; {len(findings)} warning(s).")
        if findings:
            print("Fix: regenerate the index — python3 scripts/generate-agent-index.py (or skill equivalent).")

    if args.strict and findings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
