#!/usr/bin/env python3
"""Validate the docs-sync-checker skill against the repository's current contract."""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

ValidationResult = tuple[str, bool, str]
SKILL_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SKILL_DIR.parents[2]


def _frontmatter(content: str) -> dict[str, str]:
    """Parse the scalar fields this validator needs without imposing optional metadata."""
    if not content.startswith("---\n"):
        return {}
    try:
        block = content.split("\n---", 1)[0].removeprefix("---\n")
    except ValueError:
        return {}
    fields: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line or line.startswith((" ", "-")):
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip('"')
    return fields


def validate_skill_contract() -> list[ValidationResult]:
    """Check the canonical required fields and routing metadata for this skill."""
    skill_file = SKILL_DIR / "SKILL.md"
    if not skill_file.is_file():
        return [("SKILL.md exists", False, "Missing SKILL.md")]

    fields = _frontmatter(skill_file.read_text(encoding="utf-8"))
    results: list[ValidationResult] = []
    results.append(("frontmatter name", fields.get("name") == "docs-sync-checker", "Must match directory name"))
    results.append(("frontmatter description", bool(fields.get("description")), "Missing description"))
    results.append(("routing metadata", "routing" in fields, "Missing routing mapping"))
    return results


def validate_required_files() -> list[ValidationResult]:
    """Check every document and executable that the skill's entrypoint names."""
    required = [
        "SKILL.md",
        "scripts/scan_tools.py",
        "scripts/parse_docs.py",
        "scripts/generate_report.py",
        "references/documentation-structure.md",
        "references/integration-guide.md",
        "references/sync-rules.md",
    ]
    return [(f"file exists: {path}", (SKILL_DIR / path).is_file(), f"Missing {path}") for path in required]


def validate_script_syntax() -> list[ValidationResult]:
    """Compile the locally shipped Python scripts without requiring execute bits."""
    results: list[ValidationResult] = []
    for script in sorted((SKILL_DIR / "scripts").glob("*.py")):
        try:
            compile(script.read_text(encoding="utf-8"), str(script), "exec")
        except SyntaxError as exc:
            results.append((f"syntax: {script.name}", False, str(exc)))
        else:
            results.append((f"syntax: {script.name}", True, "OK"))
    return results


def validate_scanner_contract() -> list[ValidationResult]:
    """Verify a category-nested skill without version metadata is discovered."""
    sys.path.insert(0, str(SKILL_DIR / "scripts"))
    from scan_tools import ToolScanner

    with tempfile.TemporaryDirectory() as temp_dir:
        repo = Path(temp_dir)
        skill_file = repo / "skills" / "testing" / "demo" / "SKILL.md"
        skill_file.parent.mkdir(parents=True)
        skill_file.write_text(
            "---\nname: demo\ndescription: Demo skill\nrouting:\n  category: testing\n---\n", encoding="utf-8"
        )
        agent_file = repo / "agents" / "demo-agent.md"
        agent_file.parent.mkdir()
        agent_file.write_text("---\nname: demo-agent\ndescription: Demo agent\n---\n", encoding="utf-8")

        invalid_skill = repo / "skills" / "testing" / "mismatch" / "SKILL.md"
        invalid_skill.parent.mkdir(parents=True)
        invalid_skill.write_text(
            "---\nname: wrong-name\ndescription: Invalid skill\nrouting:\n  category: testing\n---\n",
            encoding="utf-8",
        )

        scan = ToolScanner(repo).scan_all(["skills", "agents"])

    return [
        ("nested skill discovery", [item["name"] for item in scan["skills"]] == ["demo"], str(scan["skills"])),
        ("versionless component discovery", [item["name"] for item in scan["skills"]] == ["demo"], str(scan["skills"])),
        (
            "name mismatch detection",
            any("does not match directory" in error for error in scan.get("errors", [])),
            str(scan.get("errors", [])),
        ),
        ("agent discovery", [item["name"] for item in scan["agents"]] == ["demo-agent"], str(scan["agents"])),
    ]


def _parse_docs_module():
    sys.path.insert(0, str(SKILL_DIR / "scripts"))
    import parse_docs

    return parse_docs


def validate_primary_docs(repo_root: Path = REPO_ROOT) -> list[ValidationResult]:
    """Every doc the checker targets exists, and SKILL.md names exactly those targets.

    A target list naming files that do not exist made every agent and command
    look undocumented (agents/README.md and commands/README.md were gone).
    """
    parse_docs = _parse_docs_module()
    results: list[ValidationResult] = [
        (f"primary doc exists: {rel}", (repo_root / rel).is_file(), f"Missing {rel}; update PRIMARY_DOCS")
        for rel in parse_docs.PRIMARY_DOCS.values()
    ]
    skill_text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    phase2 = skill_text.split("### Phase 2", 1)[-1].split("### Phase 3", 1)[0]
    named = set(re.findall(r"^\| `([^`]+\.md)` \|", phase2, re.M))
    expected = set(parse_docs.PRIMARY_DOCS.values()) | {"README.md"}
    results.append(
        (
            "SKILL.md Phase 2 table matches PRIMARY_DOCS",
            named == expected,
            f"table {sorted(named)} != {sorted(expected)}",
        )
    )
    for rel in sorted(named):
        results.append((f"Phase 2 doc exists: {rel}", (repo_root / rel).is_file(), f"Missing {rel}"))
    return results


def validate_primary_docs_parse(repo_root: Path = REPO_ROOT) -> list[ValidationResult]:
    """Every primary doc parses to more than 0 entries for its type at the repo root.

    A renamed section heading or changed first-cell format otherwise yields an
    empty documented set and a flood of false "missing" issues.
    """
    parse_docs = _parse_docs_module()
    parser = parse_docs.DocumentationParser(repo_root)
    results: list[ValidationResult] = []
    for tool_type, rel in parse_docs.PRIMARY_DOCS.items():
        try:
            count = len(parser.parse_primary(tool_type))
        except (OSError, ValueError) as exc:
            results.append((f"primary doc parses: {rel}", False, str(exc)))
        else:
            results.append((f"primary doc parses: {rel}", count > 0, f"{count} {tool_type} entries"))
    return results


def validate_missing_target_fails() -> list[ValidationResult]:
    """parse_docs.py exits 2 when a primary doc is missing, instead of reporting it empty."""
    with tempfile.TemporaryDirectory() as temp_dir:
        repo = Path(temp_dir)
        (repo / "docs").mkdir()
        (repo / "docs" / "skills.md").write_text("| Skill | Description |\n|---|---|\n", encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(SKILL_DIR / "scripts" / "parse_docs.py"), "--repo-root", str(repo)],
            capture_output=True,
            text=True,
            check=False,
        )
    return [("missing primary doc exits 2", proc.returncode == 2, f"exit {proc.returncode}: {proc.stderr[:200]}")]


def run_all_validations() -> bool:
    """Run every validation and print a compact result table."""
    validations = [
        ("Skill contract", validate_skill_contract),
        ("Required files", validate_required_files),
        ("Script syntax", validate_script_syntax),
        ("Scanner contract", validate_scanner_contract),
        ("Primary docs", validate_primary_docs),
        ("Primary docs parse", validate_primary_docs_parse),
        ("Missing target", validate_missing_target_fails),
    ]
    results = [result for _, check in validations for result in check()]
    for description, passed, detail in results:
        print(f"{'PASS' if passed else 'FAIL'} {description}" + (f": {detail}" if not passed else ""))
    print(f"SUMMARY: {sum(passed for _, passed, _ in results)}/{len(results)} checks passed")
    return all(passed for _, passed, _ in results)


if __name__ == "__main__":
    raise SystemExit(0 if run_all_validations() else 1)
