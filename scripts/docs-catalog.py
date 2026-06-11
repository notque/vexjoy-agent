#!/usr/bin/env python3
"""Emit a routing catalog for docs/*.md from frontmatter summary + read_when.

Modes:
  default  markdown table: file | summary | read_when
  --json   machine-readable catalog
  --check  exit 1 when any doc lacks valid frontmatter (summary + read_when)

Rebuilt in Python from the docs-list pattern in steipete/agent-scripts.
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
EXCLUDED_DIRS = {"archive", "images"}


def docs_files() -> list[Path]:
    files = []
    for path in sorted(DOCS_DIR.rglob("*.md")):
        rel = path.relative_to(DOCS_DIR)
        if EXCLUDED_DIRS.intersection(rel.parts[:-1]):
            continue
        files.append(path)
    return files


def parse_frontmatter(path: Path) -> tuple[str | None, list[str], str | None]:
    """Return (summary, read_when, error). Minimal parser; stdlib only."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None, [], "missing frontmatter"
    end = text.find("\n---", 4)
    if end == -1:
        return None, [], "unterminated frontmatter"
    summary = None
    read_when: list[str] = []
    in_read_when = False
    for line in text[4:end].splitlines():
        stripped = line.strip()
        if stripped.startswith("summary:"):
            summary = stripped[len("summary:") :].strip().strip('"')
            in_read_when = False
        elif stripped == "read_when:":
            in_read_when = True
        elif in_read_when and stripped.startswith("- "):
            read_when.append(stripped[2:].strip().strip('"'))
        elif stripped and not line.startswith(" "):
            in_read_when = False
    if not summary:
        return summary, read_when, "missing summary"
    if not read_when:
        return summary, read_when, "missing read_when"
    return summary, read_when, None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON catalog")
    parser.add_argument("--check", action="store_true", help="exit 1 on missing/invalid frontmatter")
    args = parser.parse_args()

    entries = []
    errors = []
    for path in docs_files():
        rel = str(path.relative_to(REPO_ROOT))
        summary, read_when, error = parse_frontmatter(path)
        if error:
            errors.append(f"{rel}: {error}")
        entries.append({"file": rel, "summary": summary, "read_when": read_when})

    if args.check:
        if errors:
            print("docs-catalog check failed:")
            for err in errors:
                print(f"  {err}")
            return 1
        print(f"docs-catalog check passed: {len(entries)} docs")
        return 0

    if args.json:
        print(json.dumps({"docs": entries, "errors": errors}, indent=2))
        return 0

    print("| File | Summary | Read when |")
    print("|---|---|---|")
    for entry in entries:
        triggers = "; ".join(entry["read_when"]) or "-"
        print(f"| `{entry['file']}` | {entry['summary'] or '-'} | {triggers} |")
    if errors:
        print(f"\n{len(errors)} docs missing frontmatter (run --check for detail)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
