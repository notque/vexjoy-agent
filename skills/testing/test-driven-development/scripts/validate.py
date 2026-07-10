#!/usr/bin/env python3
"""Validate the test-driven-development skill against its current contract."""

from __future__ import annotations

from pathlib import Path

ValidationResult = tuple[str, bool, str]
SKILL_DIR = Path(__file__).resolve().parent.parent


def _frontmatter(content: str) -> dict[str, str]:
    """Read the scalar frontmatter fields needed for this local contract check."""
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
    """Check canonical frontmatter and the six actual TDD phase headings."""
    skill_file = SKILL_DIR / "SKILL.md"
    if not skill_file.is_file():
        return [("SKILL.md exists", False, "Missing SKILL.md")]

    content = skill_file.read_text(encoding="utf-8")
    fields = _frontmatter(content)
    results: list[ValidationResult] = [
        ("frontmatter name", fields.get("name") == "test-driven-development", "Must match directory name"),
        ("frontmatter description", bool(fields.get("description")), "Missing description"),
        ("routing metadata", "routing" in fields, "Missing routing mapping"),
    ]
    for phase in range(1, 7):
        marker = f"### Phase {phase}:"
        results.append((f"phase {phase}", marker in content, f"Missing {marker}"))
    return results


def validate_references() -> list[ValidationResult]:
    """Check the references named by the loading table and error-handling section."""
    references = ["error-handling.md", "examples.md", "phase-guidance.md"]
    return [
        (f"reference exists: {reference}", (SKILL_DIR / "references" / reference).is_file(), f"Missing {reference}")
        for reference in references
    ]


def validate_script_syntax() -> list[ValidationResult]:
    """Compile this validator instead of requiring an executable file mode."""
    script = Path(__file__)
    try:
        compile(script.read_text(encoding="utf-8"), str(script), "exec")
    except SyntaxError as exc:
        return [("validator syntax", False, str(exc))]
    return [("validator syntax", True, "OK")]


def run_all_validations() -> bool:
    """Run every validation and print a compact result table."""
    results = [
        *validate_skill_contract(),
        *validate_references(),
        *validate_script_syntax(),
    ]
    for description, passed, detail in results:
        print(f"{'PASS' if passed else 'FAIL'} {description}" + (f": {detail}" if not passed else ""))
    print(f"SUMMARY: {sum(passed for _, passed, _ in results)}/{len(results)} checks passed")
    return all(passed for _, passed, _ in results)


if __name__ == "__main__":
    raise SystemExit(0 if run_all_validations() else 1)
