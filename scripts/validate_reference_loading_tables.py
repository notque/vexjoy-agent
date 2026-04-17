#!/usr/bin/env python3
"""Validate that components with reference files declare a Reference Loading Table."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parent.parent
TABLE_HEADER_RE = re.compile(r"^\s*#{1,6}\s+Reference Loading Table\s*$", re.IGNORECASE | re.MULTILINE)
TABLE_ROW_RE = re.compile(r"^\|.+\|.+\|", re.MULTILINE)
EXEMPT_COMPONENTS: set[tuple[str, str]] = {
    ("skill", "do"),
}


@dataclass
class Violation:
    component_type: str
    component: str
    file: str
    issue: str


def collect_component_files(repo_root: Path, component_type: str) -> list[Path]:
    if component_type == "agent":
        return sorted(path for path in (repo_root / "agents").glob("*.md") if path.is_file())
    if component_type == "skill":
        return sorted(path for path in (repo_root / "skills").glob("*/SKILL.md") if path.is_file())
    raise ValueError(f"unsupported component type: {component_type}")


def reference_dir_for(component_file: Path, component_type: str) -> Path:
    if component_type == "agent":
        return component_file.with_suffix("") / "references"
    return component_file.parent / "references"


def component_name(component_file: Path, component_type: str) -> str:
    if component_type == "agent":
        return component_file.stem
    return component_file.parent.name


def has_reference_markdown(refs_dir: Path) -> bool:
    return refs_dir.exists() and any(path.is_file() for path in refs_dir.rglob("*.md"))


def has_reference_loading_table(md_text: str) -> bool:
    if not TABLE_HEADER_RE.search(md_text):
        return False

    lines = md_text.splitlines()
    for idx, line in enumerate(lines):
        if TABLE_HEADER_RE.match(line):
            table_lines: list[str] = []
            for candidate in lines[idx + 1 :]:
                stripped = candidate.strip()
                if not stripped:
                    if table_lines:
                        break
                    continue
                if stripped.startswith("|"):
                    table_lines.append(stripped)
                    continue
                if table_lines:
                    break
            return len(table_lines) >= 3 and any(TABLE_ROW_RE.match(row) for row in table_lines[2:])
    return False


def validate_components(
    repo_root: Path,
    component_types: list[str],
    component_paths: list[Path] | None = None,
) -> list[Violation]:
    violations: list[Violation] = []
    normalized_paths = {path.resolve() for path in component_paths or []}

    for component_type in component_types:
        for component_file in collect_component_files(repo_root, component_type):
            if normalized_paths and component_file.resolve() not in normalized_paths:
                continue

            component = component_name(component_file, component_type)
            if (component_type, component) in EXEMPT_COMPONENTS:
                continue

            refs_dir = reference_dir_for(component_file, component_type)
            if not has_reference_markdown(refs_dir):
                continue

            md_text = component_file.read_text(encoding="utf-8", errors="ignore")
            if has_reference_loading_table(md_text):
                continue

            violations.append(
                Violation(
                    component_type=component_type,
                    component=component,
                    file=str(component_file.relative_to(repo_root)),
                    issue="references exist but no parseable Reference Loading Table was found",
                )
            )

    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Reference Loading Table coverage")
    parser.add_argument(
        "--component-type",
        choices=("agent", "skill"),
        action="append",
        dest="component_types",
        help="Limit validation to a component type. Repeat to include both.",
    )
    parser.add_argument("--json", dest="json_output", action="store_true", help="Emit JSON output")
    parser.add_argument(
        "paths",
        nargs="*",
        help="Optional component markdown paths to validate instead of scanning the full repo.",
    )
    args = parser.parse_args()

    component_types = args.component_types or ["agent", "skill"]
    component_paths = [Path(path) for path in args.paths] if args.paths else None
    violations = validate_components(REPO_ROOT, component_types, component_paths)

    payload = {"count": len(violations), "violations": [asdict(item) for item in violations]}
    if args.json_output:
        print(json.dumps(payload, indent=2))
    else:
        for violation in violations:
            print(f"{violation.file}: {violation.issue}")
        print(f"count: {len(violations)}")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
