#!/usr/bin/env python3
"""Validate that bash/python command examples in docs reference real files.

Extracts ```bash``` and ```python``` fenced code blocks from docs/ + root markdown,
finds invocations of `python3 path/to/script.py` and `./path/to/script.sh`, and
verifies each referenced script exists on disk.

Skips:
- Commands that reference `~/.claude/...` (those are runtime-installed, not in repo)
- Variables, environment placeholders ($HOME, $VAR)
- External commands without paths (gh, git, ls, claude, codex, etc.)

Exits 0 when every script-by-path reference resolves; exits 1 otherwise.

Usage:
    python3 scripts/validate-doc-commands.py
    python3 scripts/validate-doc-commands.py --json
    python3 scripts/validate-doc-commands.py --check-sdir   # /do SKILL.md $SDIR portability
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


# ---------------------------------------------------------------------------
# $SDIR portability (--check-sdir)
#
# The /do SKILL.md must invoke its scripts as "$SDIR/name.py", never as
# repo-relative `python3 scripts/name.py`: from a non-repo cwd the mandatory
# builder then fails silently. Each $SDIR script must exist and start from a
# non-repo cwd (`--help` exits 0, or 2 for an argparse usage error).
# ---------------------------------------------------------------------------

DO_SKILL_MD = REPO_ROOT / "skills" / "meta" / "do" / "SKILL.md"
SDIR_REF = re.compile(r"\$SDIR/([a-zA-Z0-9_-]+\.py)")
BARE_SCRIPT_INVOKE = re.compile(r"python3 scripts/[a-zA-Z0-9_-]+\.py")
MIN_SDIR_SCRIPTS = 2  # pre-route.py and build-dispatch.py; guards a regex that silently matches nothing


def check_sdir(skill_md: Path = DO_SKILL_MD, scripts_dir: Path = REPO_ROOT / "scripts") -> list[str]:
    """Return failures for $SDIR script references in the /do SKILL.md."""
    import subprocess
    import tempfile

    text = skill_md.read_text(encoding="utf-8")
    names = sorted(set(SDIR_REF.findall(text)))
    failures = [f"bare repo-relative invocation (use $SDIR): {b}" for b in BARE_SCRIPT_INVOKE.findall(text)]
    if len(names) < MIN_SDIR_SCRIPTS:
        failures.append(f"expected at least {MIN_SDIR_SCRIPTS} $SDIR scripts, found {names}")
    with tempfile.TemporaryDirectory() as cwd:
        for name in names:
            script = scripts_dir / name
            if not script.is_file():
                failures.append(f"$SDIR/{name}: missing from {scripts_dir}")
                continue
            result = subprocess.run(
                [sys.executable, str(script), "--help"], capture_output=True, text=True, cwd=cwd, timeout=10
            )
            if result.returncode not in (0, 2):
                failures.append(f"$SDIR/{name}: exit {result.returncode} from a non-repo cwd: {result.stderr[:300]}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check-sdir", action="store_true", help="check $SDIR script portability in /do SKILL.md")
    args = parser.parse_args()

    if args.check_sdir:
        failures = check_sdir()
        for line in failures:
            print(f"  SDIR: {line}")
        print(f"{len(failures)} $SDIR issue(s)" if failures else "SDIR: all /do scripts portable.")
        return 1 if failures else 0

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
