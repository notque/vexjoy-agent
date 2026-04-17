#!/usr/bin/env python3
"""Validate agent reference files for structural correctness."""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

AGENTS_DIR = Path(__file__).parent.parent / "agents"

VALID_IMPACT_LEVELS = {"CRITICAL", "HIGH", "MEDIUM-HIGH", "MEDIUM", "LOW-MEDIUM", "LOW"}

IMPACT_PATTERN = re.compile(r"\*\*Impact:\*\*\s+(\S+)")

REFERENCE_LINK_PATTERN = re.compile(r"\[(?:[^\]]+)\]\(([^)]*references/[^)]+\.md|[^)]+(?<!/)[a-z][^/)]+\.md)\)")


@dataclass
class ReferenceIssue:
    kind: str
    path: str
    detail: str = ""


@dataclass
class AgentResult:
    name: str
    declared: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    issues: list[ReferenceIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.missing and not self.issues


def find_declared_references(agent_file: Path) -> list[str]:
    """Extract all references/... paths mentioned in an agent .md file."""
    content = agent_file.read_text(encoding="utf-8")
    agent_dir = AGENTS_DIR / agent_file.stem

    raw_paths: list[str] = []

    for match in REFERENCE_LINK_PATTERN.finditer(content):
        link_target = match.group(1)
        if "references/" in link_target:
            raw_paths.append(link_target)

    resolved: list[str] = []
    seen: set[str] = set()

    for raw in raw_paths:
        if raw.startswith("references/"):
            candidate = str(agent_dir / raw)
        elif raw.startswith("../"):
            candidate = str((agent_file.parent / raw).resolve())
        else:
            candidate = str(AGENTS_DIR / raw)

        if candidate not in seen:
            seen.add(candidate)
            resolved.append(candidate)

    return resolved


def validate_reference_file(ref_path: Path) -> list[ReferenceIssue]:
    """Check structural requirements of a single reference .md file."""
    issues: list[ReferenceIssue] = []
    content = ref_path.read_text(encoding="utf-8")
    rel = str(ref_path.relative_to(AGENTS_DIR))

    headings = [line for line in content.splitlines() if line.startswith("## ")]
    if not headings:
        issues.append(ReferenceIssue("no-headings", rel, "No ## headings found"))
        return issues

    sections = re.split(r"^## .+", content, flags=re.MULTILINE)
    body_sections = sections[1:] if sections[0].strip() == "" or not sections[0].startswith("## ") else sections
    for heading, body in zip(headings, body_sections):
        stripped = body.strip()
        if not stripped:
            issues.append(ReferenceIssue("empty-section", rel, f"Section '{heading.strip()}' has no body text"))

    if "```" not in content:
        issues.append(ReferenceIssue("no-code-examples", rel, "No code blocks found (consider adding examples)"))

    for match in IMPACT_PATTERN.finditer(content):
        level = match.group(1).rstrip(".,;")
        if level not in VALID_IMPACT_LEVELS:
            issues.append(
                ReferenceIssue(
                    "invalid-impact",
                    rel,
                    f"Impact level '{level}' not in {sorted(VALID_IMPACT_LEVELS)}",
                )
            )

    return issues


def validate_agent(agent_file: Path, check_structure: bool = True) -> AgentResult:
    """Validate all declared references for a single agent."""
    result = AgentResult(name=agent_file.stem)
    declared_paths = find_declared_references(agent_file)
    result.declared = declared_paths

    for path_str in declared_paths:
        ref_path = Path(path_str)
        if not ref_path.exists():
            result.missing.append(path_str)
        elif check_structure:
            result.issues.extend(validate_reference_file(ref_path))

    return result


def find_all_reference_files() -> list[Path]:
    """Find every .md file inside any references/ subdirectory under agents/."""
    return list(AGENTS_DIR.rglob("references/*.md"))


def find_orphan_references(all_results: list[AgentResult]) -> list[Path]:
    """Return reference files that exist on disk but aren't declared by any agent."""
    declared_set: set[str] = set()
    for result in all_results:
        for path_str in result.declared:
            declared_set.add(str(Path(path_str).resolve()))

    orphans: list[Path] = []
    for ref_file in find_all_reference_files():
        if str(ref_file.resolve()) not in declared_set:
            orphans.append(ref_file)
    return orphans


def print_text_results(results: list[AgentResult], orphans: list[Path]) -> None:
    """Print human-readable validation output."""
    for result in results:
        total = len(result.declared)
        missing_count = len(result.missing)
        present_count = total - missing_count
        issue_count = len(result.issues)

        if result.ok:
            print(f"  {result.name}: {present_count}/{total} references present, 0 issues")
        else:
            print(f"  {result.name}: {present_count}/{total} references present, {issue_count} issues")
            for path_str in result.missing:
                rel = Path(path_str).relative_to(AGENTS_DIR) if AGENTS_DIR in Path(path_str).parents else path_str
                print(f"    MISSING: {rel}")
            for issue in result.issues:
                label = issue.kind.upper().replace("-", "_")
                print(f"    {label}: {issue.path} — {issue.detail}")

    if orphans:
        print("\nOrphan reference files (not declared by any agent):")
        for orphan in orphans:
            print(f"  ORPHAN: {orphan.relative_to(AGENTS_DIR)}")

    ok_count = sum(1 for r in results if r.ok)
    issue_count = sum(1 for r in results if not r.ok)
    total_missing = sum(len(r.missing) for r in results)
    total_issues = sum(len(r.issues) for r in results)

    parts = [f"{ok_count} agents OK"]
    if issue_count:
        parts.append(f"{issue_count} agent(s) with issues")
    if total_missing:
        parts.append(f"{total_missing} file(s) missing")
    if total_issues:
        parts.append(f"{total_issues} structure issue(s)")
    if orphans:
        parts.append(f"{len(orphans)} orphan(s)")

    print(f"\nSummary: {', '.join(parts)}")


def build_json_results(results: list[AgentResult], orphans: list[Path]) -> dict:
    """Build JSON-serializable results dict."""
    agents_out = []
    for result in results:
        agents_out.append(
            {
                "agent": result.name,
                "ok": result.ok,
                "declared": len(result.declared),
                "present": len(result.declared) - len(result.missing),
                "missing": [str(p) for p in result.missing],
                "issues": [{"kind": i.kind, "path": i.path, "detail": i.detail} for i in result.issues],
            }
        )

    ok_count = sum(1 for r in results if r.ok)
    issue_count = sum(1 for r in results if not r.ok)
    missing_count = sum(len(r.missing) for r in results)
    structure_issues = sum(len(r.issues) for r in results)
    has_failures = issue_count > 0 or missing_count > 0

    return {
        "agents": agents_out,
        "orphans": [str(o.relative_to(AGENTS_DIR)) for o in orphans],
        "summary": {
            "ok": ok_count,
            "issues": issue_count,
            "missing_files": missing_count,
            "structure_issues": structure_issues,
            "orphans": len(orphans),
        },
        "exit_code": 1 if has_failures else 0,
    }


def main() -> None:
    """Entry point for reference validation CLI."""
    parser = argparse.ArgumentParser(description="Validate agent reference files")
    parser.add_argument("--agent", help="Validate references for specific agent")
    parser.add_argument("--all", action="store_true", help="Validate all agents")
    parser.add_argument("--check-declared", action="store_true", help="Only check declared refs exist")
    parser.add_argument("--json", dest="json_output", action="store_true", help="JSON output for CI")
    args = parser.parse_args()

    if not args.agent and not args.all:
        parser.error("Specify --agent <name> or --all")

    check_structure = not args.check_declared

    agent_files: list[Path] = []
    if args.agent:
        candidate = AGENTS_DIR / f"{args.agent}.md"
        if not candidate.exists():
            print(f"ERROR: Agent file not found: {candidate}", file=sys.stderr)
            sys.exit(1)
        agent_files = [candidate]
    else:
        agent_files = sorted(AGENTS_DIR.glob("*.md"))
        agent_files = [f for f in agent_files if f.name not in {"README.md", "INDEX.json"}]

    results: list[AgentResult] = []
    for agent_file in agent_files:
        if not agent_file.is_file():
            continue
        result = validate_agent(agent_file, check_structure=check_structure)
        if result.declared or not check_structure:
            results.append(result)

    all_results_for_orphans = results if args.all else []
    orphans: list[Path] = []
    if args.all and check_structure:
        all_agent_results = [validate_agent(f, check_structure=False) for f in sorted(AGENTS_DIR.glob("*.md"))]
        orphans = find_orphan_references(all_agent_results)

    if args.json_output:
        output = build_json_results(results, orphans)
        print(json.dumps(output, indent=2))
        sys.exit(output["exit_code"])
    else:
        print_text_results(results, orphans)
        has_failures = any(not r.ok for r in results) or bool(orphans)
        sys.exit(1 if has_failures else 0)


if __name__ == "__main__":
    main()
