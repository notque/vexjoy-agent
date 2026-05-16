#!/usr/bin/env python3
"""
Validate INDEX.json integrity for agents and skills.

Checks:
  1. All skill entries in skills/INDEX.json have a corresponding SKILL.md on disk.
  2. All agent ``file`` fields in agents/INDEX.json point to existing files
     (paths resolved relative to the repo root).
  3. No skill or agent has fewer than 5 triggers (warn) or 0 triggers (error).
  4. No triggers are duplicated within a single entry.
  5. No triggers are duplicated across entries (cross-entry overlap warning).

Note: routing-tables.md coverage check was removed in PR #653 — routing-tables.md was
absorbed into INDEX.json (PR #626) and check-routing-drift.py now covers this in CI.

Exit codes:
  0 — all checks pass (errors = 0)
  1 — one or more errors found

Usage:
    python scripts/validate-index-integrity.py
"""

import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_json(path: Path) -> dict:
    """Load and return JSON from *path*, exiting with an error on failure."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"ERROR: index file not found: {path}")
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"ERROR: cannot parse {path}: {exc}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Check functions
# ---------------------------------------------------------------------------


def check_skill_files(skills_index: dict, repo_root: Path) -> tuple[list[str], list[str]]:
    """Check 1: every skill entry has a SKILL.md on disk."""
    errors: list[str] = []
    warnings: list[str] = []

    for name, entry in skills_index.get("skills", {}).items():
        if not isinstance(entry, dict):
            errors.append(f"  [skill malformed] '{name}': INDEX entry is not a dict")
            continue
        file_field = entry.get("file", "")
        if not file_field:
            errors.append(f"  [skill missing file] '{name}': INDEX entry has no 'file' field")
            continue
        skill_path = repo_root / file_field
        if not skill_path.is_file():
            errors.append(f"  [skill missing file] '{name}': INDEX says '{file_field}' but file does not exist")

    return errors, warnings


def check_agent_files(agents_index: dict, repo_root: Path) -> tuple[list[str], list[str]]:
    """Check 2: every agent file field points to an existing file."""
    errors: list[str] = []
    warnings: list[str] = []

    for name, entry in agents_index.get("agents", {}).items():
        if not isinstance(entry, dict):
            errors.append(f"  [agent malformed] '{name}': INDEX entry is not a dict")
            continue
        file_field = entry.get("file", "")
        if not file_field:
            errors.append(f"  [agent missing file] '{name}': INDEX entry has no 'file' field")
            continue
        agent_path = repo_root / file_field
        if not agent_path.is_file():
            errors.append(f"  [agent missing file] '{name}': INDEX says '{file_field}' but file does not exist")

    return errors, warnings


def check_trigger_counts(index: dict, index_type: str) -> tuple[list[str], list[str]]:
    """Check 4: no entry has < 5 triggers (warn) or 0 triggers (error)."""
    errors: list[str] = []
    warnings: list[str] = []

    label = {"skills": "skill", "agents": "agent"}.get(index_type, index_type)
    items = index.get(index_type, {})
    for name, entry in items.items():
        if not isinstance(entry, dict):
            continue
        triggers = entry.get("triggers", [])
        count = len(triggers)
        if count == 0:
            errors.append(f"  [zero triggers] {label} '{name}' has 0 triggers — routing will never match this entry")
        elif count < 5:
            warnings.append(
                f"  [few triggers] {label} '{name}' has only {count} trigger(s) "
                "— consider adding more for reliable routing"
            )

    return errors, warnings


def check_duplicate_triggers(index: dict, index_type: str) -> tuple[list[str], list[str]]:
    """Check 5: no triggers are duplicated within a single entry."""
    errors: list[str] = []
    warnings: list[str] = []

    label = {"skills": "skill", "agents": "agent"}.get(index_type, index_type)
    items = index.get(index_type, {})
    for name, entry in items.items():
        if not isinstance(entry, dict):
            continue
        triggers = entry.get("triggers", [])
        seen: set[str] = set()
        duplicates: list[str] = []
        for t in triggers:
            if t in seen:
                duplicates.append(t)
            seen.add(t)
        if duplicates:
            errors.append(f"  [duplicate triggers] {label} '{name}' has duplicate trigger(s): {duplicates}")

    return errors, warnings


def check_cross_entry_trigger_overlap(skills_index: dict, agents_index: dict) -> tuple[list[str], list[str]]:
    """Check 6: detect triggers claimed by multiple entries across both indexes."""
    errors: list[str] = []
    warnings: list[str] = []

    trigger_map: dict[str, list[str]] = {}
    for index, index_type in [(skills_index, "skills"), (agents_index, "agents")]:
        label = {"skills": "skill", "agents": "agent"}.get(index_type, index_type)
        for name, entry in index.get(index_type, {}).items():
            if not isinstance(entry, dict):
                continue
            for trigger in entry.get("triggers", []):
                trigger_lower = trigger.lower()
                trigger_map.setdefault(trigger_lower, []).append(f"{label}:{name}")

    for trigger, owners in sorted(trigger_map.items()):
        if len(owners) > 1:
            warnings.append(f"  [trigger overlap] '{trigger}' claimed by: {', '.join(owners)}")

    return errors, warnings


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    """Run all integrity checks and report results. Returns exit code."""
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent

    skills_index_path = repo_root / "skills" / "INDEX.json"
    agents_index_path = repo_root / "agents" / "INDEX.json"

    print("Loading index files...")
    skills_index = load_json(skills_index_path)
    agents_index = load_json(agents_index_path)

    all_errors: list[str] = []
    all_warnings: list[str] = []

    # Run checks
    # Note: routing-tables.md coverage check removed — routing-tables.md was absorbed
    # into INDEX.json (PR #626) and check-routing-drift.py now covers this in CI.
    checks = [
        ("Check 1: skill files on disk", check_skill_files(skills_index, repo_root)),
        ("Check 2: agent files on disk", check_agent_files(agents_index, repo_root)),
        ("Check 4a: skill trigger counts", check_trigger_counts(skills_index, "skills")),
        ("Check 4b: agent trigger counts", check_trigger_counts(agents_index, "agents")),
        (
            "Check 5a: skill duplicate triggers",
            check_duplicate_triggers(skills_index, "skills"),
        ),
        (
            "Check 5b: agent duplicate triggers",
            check_duplicate_triggers(agents_index, "agents"),
        ),
        (
            "Check 6: cross-entry trigger overlap",
            check_cross_entry_trigger_overlap(skills_index, agents_index),
        ),
    ]

    for label, (errors, warnings) in checks:
        status = "PASS" if not errors else "FAIL"
        warn_suffix = f" ({len(warnings)} warning(s))" if warnings else ""
        print(f"\n{label}: {status}{warn_suffix}")
        for msg in errors:
            print(f"ERROR: {msg}")
        for msg in warnings:
            print(f"WARN:  {msg}")
        all_errors.extend(errors)
        all_warnings.extend(warnings)

    # Summary
    print("\n" + "=" * 60)
    print(f"Total errors:   {len(all_errors)}")
    print(f"Total warnings: {len(all_warnings)}")

    if all_errors:
        print("VERDICT: FAIL")
        return 1

    print("VERDICT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
