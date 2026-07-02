#!/usr/bin/env python3
"""Validate the MERGED (tracked + local) routing index.

The 2026-07-02 audit found every live routing defect sitting in the merged
view (tracked INDEX.json + gitignored INDEX.local.json overlay) that no
validator read: validate-index-integrity.py checks tracked files only. This
script runs the audit's defect classes over the merged skills and agents
indexes (merge logic shared via routing_index_merge.py):

  D1 PHANTOM        — `file` field resolves neither under the repo root nor
                      under ~/.claude (deployed flat layout, the same fallback
                      generate-skill-index.py scans). CRITICAL when the entry
                      is force_route: the router is told to PREFER an
                      unloadable skill. Missing `file` field counts too.
  D2 DEAD-AGENT-REF — skill `agent` field names no agent in the merged
                      agents index, no agents/*.md on disk, and no
                      harness builtin (BUILTIN_AGENTS, as in
                      validate-do-references.py).
  D3/D4 MISSING-FIELD — entry has no `category`, or neither `description`
                      nor `short_description`.
  D5 NOT-PREFIX     — `not_for` starts with "NOT: "; routing-manifest.py
                      prepends " NOT: " again, rendering "NOT: NOT:".
  UNKNOWN-CATEGORY  — WARN: category absent from scripts/category-registry.json
                      (snapshot of categories in use; consolidation is a
                      future owner decision). Skipped if the registry is absent.

Output: one line per finding, `LEVEL CLASS name — detail`, sorted by
severity, class, name. Then a summary count.

Exit codes:
    0 — advisory default: findings printed, never gates. Also --strict with
        no critical/error findings (WARN never gates).
    1 — --strict with critical/error findings, or an index file is missing
        or unparseable (invocation error, both modes).

Usage:
    python3 scripts/validate-merged-index.py [--strict]
        [--repo-root PATH] [--claude-dir PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

# Shared tracked+local INDEX merge — single source in routing_index_merge.py.
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
from routing_index_merge import load_index_items

# Harness-provided agents outside agents/INDEX.json (same set as
# validate-do-references.py).
BUILTIN_AGENTS = frozenset({"general-purpose"})

_LEVEL_RANK = {"CRITICAL": 0, "ERROR": 1, "WARN": 2}


@dataclass(frozen=True)
class Finding:
    level: str  # CRITICAL | ERROR | WARN
    cls: str  # PHANTOM | DEAD-AGENT-REF | MISSING-FIELD | NOT-PREFIX | UNKNOWN-CATEGORY
    name: str  # entry name
    detail: str

    def sort_key(self) -> tuple[int, str, str, str]:
        return (_LEVEL_RANK[self.level], self.cls, self.name, self.detail)

    def line(self) -> str:
        return f"{self.level} {self.cls} {self.name} — {self.detail}"


def load_merged(tracked: Path, key: str) -> dict:
    """Merged entries (tracked + INDEX.local.json overlay). Exits 1 when the
    tracked file is missing or unparseable — a silent empty merge would
    report a clean index it never read."""
    if not tracked.is_file():
        print(f"ERROR: index file not found: {tracked}", file=sys.stderr)
        sys.exit(1)
    try:
        json.loads(tracked.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: cannot parse {tracked}: {exc}", file=sys.stderr)
        sys.exit(1)
    merged: dict = load_index_items(tracked, "INDEX.local.json", key)
    return merged


def load_registry(repo_root: Path) -> set[str] | None:
    """Category registry, or None (check skipped) when absent/unreadable."""
    path = repo_root / "scripts" / "category-registry.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        print(f"note: {path} not found or unreadable — category check skipped", file=sys.stderr)
        return None
    categories = data.get("categories", [])
    return {c for c in categories if isinstance(c, str)}


def resolvable(file_field: str, repo_root: Path, claude_dir: Path) -> bool:
    """True when the path exists under the repo root or the deployed layout
    (~/.claude/skills/<name>/SKILL.md — INDEX.local.json writes flat
    skills/<name>/... paths that only resolve there)."""
    return (repo_root / file_field).is_file() or (claude_dir / file_field).is_file()


def known_agents(agents: dict, repo_root: Path) -> set[str]:
    """Union: merged agents-index names, agents/*.md stems on disk, builtins."""
    on_disk = {p.stem for p in (repo_root / "agents").glob("*.md")}
    return set(agents) | on_disk | BUILTIN_AGENTS


def check_entry(
    name: str,
    entry: dict,
    kind: str,
    repo_root: Path,
    claude_dir: Path,
    agent_names: set[str] | None,
    registry: set[str] | None,
) -> list[Finding]:
    """All checks for one merged-index entry. `agent_names` is None for
    agent entries (they carry no `agent` field)."""
    findings: list[Finding] = []

    file_field = entry.get("file", "")
    if not file_field:
        findings.append(Finding("ERROR", "PHANTOM", name, f"{kind} entry has no 'file' field"))
    elif not resolvable(file_field, repo_root, claude_dir):
        where = f"'{file_field}' not found under repo root or {claude_dir}"
        if entry.get("force_route"):
            findings.append(
                Finding(
                    "CRITICAL",
                    "PHANTOM",
                    name,
                    f"force_route {kind}: router is told to PREFER an unloadable skill; {where}",
                )
            )
        else:
            findings.append(Finding("ERROR", "PHANTOM", name, f"{kind} file {where}"))

    if agent_names is not None:
        agent_ref = entry.get("agent")
        if agent_ref and agent_ref not in agent_names:
            findings.append(
                Finding(
                    "ERROR",
                    "DEAD-AGENT-REF",
                    name,
                    f"agent '{agent_ref}' is in no agents index, agents/*.md, or builtin set",
                )
            )

    category = entry.get("category")
    if not category:
        findings.append(Finding("ERROR", "MISSING-FIELD", name, f"{kind} entry has no 'category'"))
    elif registry is not None and category not in registry:
        findings.append(
            Finding(
                "WARN",
                "UNKNOWN-CATEGORY",
                name,
                f"category '{category}' not in scripts/category-registry.json",
            )
        )

    if not (entry.get("description") or entry.get("short_description")):
        findings.append(Finding("ERROR", "MISSING-FIELD", name, f"{kind} entry has no 'description'"))

    not_for = entry.get("not_for")
    if isinstance(not_for, str) and not_for.startswith("NOT: "):
        findings.append(
            Finding(
                "ERROR",
                "NOT-PREFIX",
                name,
                "not_for starts with 'NOT: ' — routing-manifest.py prepends it again ('NOT: NOT:')",
            )
        )

    return findings


def validate(repo_root: Path, claude_dir: Path) -> list[Finding]:
    """Run every check over the merged skills and agents indexes."""
    skills = load_merged(repo_root / "skills" / "INDEX.json", "skills")
    agents = load_merged(repo_root / "agents" / "INDEX.json", "agents")
    registry = load_registry(repo_root)
    agent_names = known_agents(agents, repo_root)

    findings: list[Finding] = []
    for name, entry in skills.items():
        if isinstance(entry, dict):
            findings.extend(check_entry(name, entry, "skill", repo_root, claude_dir, agent_names, registry))
    for name, entry in agents.items():
        if isinstance(entry, dict):
            findings.extend(check_entry(name, entry, "agent", repo_root, claude_dir, None, registry))
    return sorted(findings, key=Finding.sort_key)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the merged (tracked + local) routing index.")
    parser.add_argument("--strict", action="store_true", help="Exit 1 on critical/error findings (WARN never gates)")
    parser.add_argument("--repo-root", type=Path, default=_SCRIPTS_DIR.parent, help="Repo root (default: this repo)")
    parser.add_argument(
        "--claude-dir",
        type=Path,
        default=Path.home() / ".claude",
        help="Deployed-layout fallback for file resolution (default: ~/.claude)",
    )
    args = parser.parse_args()

    findings = validate(args.repo_root, args.claude_dir)

    for finding in findings:
        print(finding.line())

    counts = {level: sum(1 for f in findings if f.level == level) for level in _LEVEL_RANK}
    print(
        f"\nSummary: {len(findings)} finding(s) — "
        f"{counts['CRITICAL']} critical, {counts['ERROR']} error, {counts['WARN']} warn"
    )

    gating = counts["CRITICAL"] + counts["ERROR"]
    if args.strict:
        print(f"VERDICT: {'FAIL' if gating else 'PASS'} (--strict)")
        return 1 if gating else 0
    print("ADVISORY: exit 0 — use --strict to gate on critical/error findings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
