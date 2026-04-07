#!/usr/bin/env python3
"""
Validate INDEX.json integrity for agents and skills.

Checks:
  1. All skill entries in skills/INDEX.json have a corresponding SKILL.md on disk.
  2. All agent ``file`` fields in agents/INDEX.json point to existing files
     (paths resolved relative to the repo root).
  3. All names referenced in routing-tables.md exist in agents/ or skills/ INDEX.json.
  4. No skill or agent has fewer than 3 triggers (warn) or 0 triggers (error).
  5. No triggers are duplicated within a single entry.

Exit codes:
  0 — all checks pass (errors = 0)
  1 — one or more errors found

Usage:
    python scripts/validate-index-integrity.py
"""

import json
import re
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


def extract_routing_table_names(routing_tables_path: Path) -> set[str]:
    """Return the set of agent/skill names found in routing-tables.md.

    Matches bold-formatted names like ``**reviewer-code-playbook**`` or
    ``**go-patterns (FORCE)**``, stripping the bold markers and any
    parenthetical suffix (e.g. ``(FORCE)``, ``(code-cartographer)``).
    """
    if not routing_tables_path.exists():
        print(f"WARNING: routing-tables.md not found at {routing_tables_path}")
        return set()

    content = routing_tables_path.read_text(encoding="utf-8")
    # Match **name** or **name (qualifier)**
    raw_names = re.findall(r"\*\*([a-z][a-z0-9/-]*)(?:\s+\([^)]*\))?\*\*", content)
    return set(raw_names)


# ---------------------------------------------------------------------------
# Check functions
# ---------------------------------------------------------------------------


def check_skill_files(skills_index: dict, repo_root: Path) -> tuple[list[str], list[str]]:
    """Check 1: every skill entry has a SKILL.md on disk."""
    errors: list[str] = []
    warnings: list[str] = []

    for name, entry in skills_index.get("skills", {}).items():
        file_field = entry.get("file", "")
        skill_path = repo_root / file_field
        if not skill_path.exists():
            errors.append(f"  [skill missing file] '{name}': INDEX says '{file_field}' but file does not exist")

    return errors, warnings


def check_agent_files(agents_index: dict, repo_root: Path) -> tuple[list[str], list[str]]:
    """Check 2: every agent file field points to an existing file."""
    errors: list[str] = []
    warnings: list[str] = []

    for name, entry in agents_index.get("agents", {}).items():
        file_field = entry.get("file", "")
        agent_path = repo_root / file_field
        if not agent_path.exists():
            errors.append(f"  [agent missing file] '{name}': INDEX says '{file_field}' but file does not exist")

    return errors, warnings


def check_routing_table_coverage(
    routing_names: set[str],
    agents_index: dict,
    skills_index: dict,
    repo_root: Path,
) -> tuple[list[str], list[str]]:
    """Check 3: all names in routing-tables.md exist in agents, skills, or workflow refs."""
    errors: list[str] = []
    warnings: list[str] = []

    agent_names = set(agents_index.get("agents", {}).keys())
    skill_names = set(skills_index.get("skills", {}).keys())

    # Workflow references are sub-workflows accessed via the umbrella workflow skill.
    # They live in skills/workflow/references/ and are valid routing targets.
    workflow_refs_dir = repo_root / "skills" / "workflow" / "references"
    workflow_ref_names: set[str] = set()
    if workflow_refs_dir.exists():
        for ref_file in workflow_refs_dir.iterdir():
            if ref_file.suffix == ".md":
                workflow_ref_names.add(ref_file.stem)
            elif ref_file.is_dir():
                workflow_ref_names.add(ref_file.name)

    # Pipeline names from pipeline-index.json
    pipeline_names: set[str] = set()
    pipeline_index_path = workflow_refs_dir / "pipeline-index.json"
    if pipeline_index_path.exists():
        try:
            pipeline_data = json.loads(pipeline_index_path.read_text(encoding="utf-8"))
            pipeline_names = set(pipeline_data.get("pipelines", {}).keys())
        except (json.JSONDecodeError, OSError):
            pass

    # Non-component names that appear as bold entries in policy tables
    table_values = {"personal", "protected-org"}

    all_known = agent_names | skill_names | workflow_ref_names | pipeline_names | table_values

    for name in sorted(routing_names):
        if name not in all_known:
            errors.append(
                f"  [routing orphan] '{name}' in routing-tables.md "
                "but not found in agents/, skills/, or workflow references"
            )

    return errors, warnings


def check_trigger_counts(index: dict, index_type: str) -> tuple[list[str], list[str]]:
    """Check 4: no entry has < 3 triggers (warn) or 0 triggers (error)."""
    errors: list[str] = []
    warnings: list[str] = []

    items = index.get(index_type, {})
    for name, entry in items.items():
        triggers = entry.get("triggers", [])
        count = len(triggers)
        if count == 0:
            errors.append(
                f"  [zero triggers] {index_type[:-1]} '{name}' has 0 triggers — routing will never match this entry"
            )
        elif count < 3:
            warnings.append(
                f"  [few triggers] {index_type[:-1]} '{name}' has only {count} trigger(s) "
                "— consider adding more for reliable routing"
            )

    return errors, warnings


def check_duplicate_triggers(index: dict, index_type: str) -> tuple[list[str], list[str]]:
    """Check 5: no triggers are duplicated within a single entry."""
    errors: list[str] = []
    warnings: list[str] = []

    items = index.get(index_type, {})
    for name, entry in items.items():
        triggers = entry.get("triggers", [])
        seen: set[str] = set()
        duplicates: list[str] = []
        for t in triggers:
            if t in seen:
                duplicates.append(t)
            seen.add(t)
        if duplicates:
            errors.append(f"  [duplicate triggers] {index_type[:-1]} '{name}' has duplicate trigger(s): {duplicates}")

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
    routing_tables_path = repo_root / "skills" / "do" / "references" / "routing-tables.md"

    print("Loading index files...")
    skills_index = load_json(skills_index_path)
    agents_index = load_json(agents_index_path)

    print("Extracting routing table names...")
    routing_names = extract_routing_table_names(routing_tables_path)

    all_errors: list[str] = []
    all_warnings: list[str] = []

    # Run checks
    checks = [
        ("Check 1: skill files on disk", check_skill_files(skills_index, repo_root)),
        ("Check 2: agent files on disk", check_agent_files(agents_index, repo_root)),
        (
            "Check 3: routing-tables.md coverage",
            check_routing_table_coverage(routing_names, agents_index, skills_index, repo_root),
        ),
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
