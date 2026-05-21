#!/usr/bin/env python3
"""Validate that bash/python command examples in docs reference real files.

Extracts ```bash``` and ```python``` fenced code blocks from docs/ + root markdown,
finds invocations of `python3 path/to/script.py` and `./path/to/script.sh`, and
verifies each referenced script exists on disk.

Skips:
- Commands that reference `~/.claude/...` (those are runtime-installed, not in repo)
- Variables, environment placeholders ($HOME, $VAR)
- External commands without paths (gh, git, ls, claude, codex, gemini, etc.)

Exits 0 when every script-by-path reference resolves; exits 1 otherwise.

Usage:
    python3 scripts/validate-doc-commands.py
    python3 scripts/validate-doc-commands.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
ROOT_MARKDOWN = ["README.md", "CONTRIBUTING.md", "CLAUDE.md"]

FENCE = re.compile(r"```(bash|sh|python|console)\s*\n(.*?)\n```", re.DOTALL)

# python3 scripts/foo.py | python3 ~/path/foo.py
PY_INVOKE = re.compile(r"python3?\s+([^\s|;&<>]+\.py)")
# ./scripts/foo.sh | ./install.sh
SH_INVOKE = re.compile(r"(?<![\w/])(\./[\w./-]+\.(?:sh|py))")

EXTERNAL_PREFIXES = (
    "~/",
    "$HOME",
    "/tmp/",
    "/dev/",
    "/etc/",
    "/var/",
)


def collect_markdown_files() -> list[Path]:
    files = []
    if DOCS_DIR.is_dir():
        files.extend(sorted(DOCS_DIR.rglob("*.md")))
    for name in ROOT_MARKDOWN:
        p = REPO_ROOT / name
        if p.is_file():
            files.append(p)
    return files


def is_repo_local(path: str) -> bool:
    return not path.startswith(EXTERNAL_PREFIXES) and "$" not in path


def resolve_repo_path(invocation: str) -> Path:
    p = invocation.lstrip("./")
    return REPO_ROOT / p


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    missing: list[dict] = []
    checked = 0

    for md in collect_markdown_files():
        text = md.read_text(encoding="utf-8", errors="replace")
        rel = md.relative_to(REPO_ROOT)
        for fence_match in FENCE.finditer(text):
            block = fence_match.group(2)
            for invoke_match in PY_INVOKE.finditer(block):
                target = invoke_match.group(1)
                if not is_repo_local(target):
                    continue
                checked += 1
                if not resolve_repo_path(target).is_file():
                    missing.append({"source": str(rel), "target": target})
            for invoke_match in SH_INVOKE.finditer(block):
                target = invoke_match.group(1)
                if not is_repo_local(target):
                    continue
                checked += 1
                if not resolve_repo_path(target).is_file():
                    missing.append({"source": str(rel), "target": target})

    if args.json:
        print(json.dumps({"checked": checked, "missing": missing}, indent=2))
    else:
        print(f"Checked {checked} repo-local script invocations across {len(collect_markdown_files())} files.")
        if missing:
            print(f"\nMissing: {len(missing)}")
            for m in missing:
                print(f"  {m['source']}: {m['target']}")
        else:
            print("All script references resolve.")

    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
