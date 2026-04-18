#!/usr/bin/env python3
"""Strip model: lines from YAML frontmatter in agent and skill files.

Removes the model: field from YAML frontmatter in .md files. The model
field is redundant context: 44/49 agents specify 'sonnet' (the default),
and the field doesn't work in Codex. The only model override that
matters is the Haiku one in /do's SKILL.md instruction.

Usage:
    python3 scripts/strip-model-frontmatter.py                    # dry run
    python3 scripts/strip-model-frontmatter.py --apply            # apply changes
    python3 scripts/strip-model-frontmatter.py --path ~/custom    # custom path

Exit codes:
    0 — Success
    1 — No files found
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TOOLKIT_DIR = Path.home() / ".toolkit"


def strip_model_from_frontmatter(text: str) -> tuple[str, str | None]:
    """Remove model: line from YAML frontmatter. Returns (new_text, old_model)."""
    if not text.startswith("---"):
        return text, None

    end = text.find("\n---", 3)
    if end == -1:
        return text, None

    frontmatter = text[3:end]
    match = re.search(r"\n\s*model:\s*(.+)", frontmatter)
    if not match:
        return text, None

    old_model = match.group(1).strip().strip("\"'")
    new_frontmatter = frontmatter[: match.start()] + frontmatter[match.end() :]
    return "---" + new_frontmatter + text[end:], old_model


def find_files(base: Path) -> list[Path]:
    """Find agent .md files and skill SKILL.md files."""
    files = []

    agents_dir = base / "agents"
    if agents_dir.exists():
        for f in sorted(agents_dir.glob("*.md")):
            if f.name == "README.md":
                continue
            files.append(f.resolve())

    skills_dir = base / "skills"
    if skills_dir.exists():
        for f in sorted(skills_dir.glob("*/SKILL.md")):
            files.append(f.resolve())

    return files


def main() -> int:
    parser = argparse.ArgumentParser(description="Strip model: from frontmatter.")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default: dry run)")
    parser.add_argument("--path", type=Path, default=TOOLKIT_DIR, help="Base path to scan")
    args = parser.parse_args()

    files = find_files(args.path)
    if not files:
        print(f"No files found under {args.path}")
        return 1

    changed = 0
    skipped = 0

    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue

        new_text, old_model = strip_model_from_frontmatter(text)
        if old_model is None:
            skipped += 1
            continue

        rel = path.relative_to(args.path) if str(path).startswith(str(args.path)) else path
        action = "stripped" if args.apply else "would strip"
        print(f"  {action} model={old_model} from {rel}")

        if args.apply:
            path.write_text(new_text, encoding="utf-8")

        changed += 1

    mode = "Applied" if args.apply else "Dry run"
    print(f"\n{mode}: {changed} files changed, {skipped} files without model field")
    return 0


if __name__ == "__main__":
    sys.exit(main())
