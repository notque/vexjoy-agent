#!/usr/bin/env python3
# hook-version: 1.0.0
"""
SessionStart Hook: Hook-Version Parity Check

Warn-only guard for the "merged is not deployed" gotcha: a hook change lands
on main but ~/.claude/hooks/ still runs the old copy (worktree sessions skip
sync-to-user-claude; copy-mode installs drift until the next main-repo sync),
so telemetry hooks silently starve the feedback loop.

Compares the `# hook-version: X.Y.Z` header of every repo hook .py against
the deployed copy in ~/.claude/hooks/. On any mismatch (or a deployed file
missing entirely) it emits ONE warning line naming the drifted hooks and the
sync command. On full parity it stays silent.

Skip conditions (silent):
- Not the toolkit repo (no hooks/sync-to-user-claude.py in the checkout)
- ~/.claude/hooks resolves to this checkout's hooks/ dir (symlink install —
  drift is impossible)
- ~/.claude/hooks does not exist (nothing deployed to compare)

Design (Warn-Only Gates doctrine):
- Never denies, never blocks — always exits 0
- Fast (<50ms): reads only the first bytes of each file, no subprocess
- ADR: adr/hook-version-parity-check.md
"""

import os
import re
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import context_output, empty_output

EVENT_NAME = "SessionStart"

# Deployed hooks location. Module-level so tests can point it at a tmp dir.
DEPLOYED_HOOKS_DIR = Path.home() / ".claude" / "hooks"

# `# hook-version: X.Y.Z` header, expected within the first few lines.
_VERSION_RE = re.compile(r"^#\s*hook-version:\s*(\S+)", re.MULTILINE)

# How many drifted hook names the one-line warning spells out.
_MAX_NAMED = 10

SYNC_CMD = "python3 ~/.claude/hooks/sync-to-user-claude.py"


def read_hook_version(path: Path) -> str | None:
    """Return the hook-version header value, or None (missing file/header)."""
    try:
        head = path.open("r", encoding="utf-8", errors="replace").read(512)
    except OSError:
        return None
    m = _VERSION_RE.search(head)
    return m.group(1) if m else None


def find_drifted_hooks(repo_hooks: Path, deployed_hooks: Path) -> list[str]:
    """Names of repo hooks whose deployed copy is missing or version-differs.

    Only files carrying a version header participate: a header-less repo file
    has nothing to compare, so it is skipped (bumping headers on change is the
    convention that feeds this check). A deployed copy that is missing or
    lacks the repo's header counts as drift — it is running older code.
    """
    drifted: list[str] = []
    for repo_file in sorted(repo_hooks.rglob("*.py")):
        rel = repo_file.relative_to(repo_hooks)
        if "tests" in rel.parts or "__pycache__" in rel.parts:
            continue
        repo_version = read_hook_version(repo_file)
        if repo_version is None:
            continue
        deployed_version = read_hook_version(deployed_hooks / rel)
        if deployed_version != repo_version:
            drifted.append(str(rel))
    return drifted


def build_warning(drifted: list[str]) -> str:
    """One line: count, names (capped), and the fix command."""
    named = ", ".join(drifted[:_MAX_NAMED])
    more = f" (+{len(drifted) - _MAX_NAMED} more)" if len(drifted) > _MAX_NAMED else ""
    return (
        f"[hook-parity] WARNING: {len(drifted)} deployed hook(s) differ from this checkout: "
        f"{named}{more} — merged is not deployed; run: {SYNC_CMD}"
    )


def main() -> None:
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())).resolve()
    repo_hooks = project_dir / "hooks"
    if not (repo_hooks / "sync-to-user-claude.py").is_file():
        # Not the toolkit repo — nothing to compare.
        empty_output(EVENT_NAME).print_and_exit()
        return

    deployed = DEPLOYED_HOOKS_DIR
    if not deployed.is_dir():
        if debug:
            print(f"[hook-parity] no deployed hooks dir at {deployed}", file=sys.stderr)
        empty_output(EVENT_NAME).print_and_exit()
        return
    try:
        if deployed.resolve() == repo_hooks.resolve():
            # Symlink install pointing at this checkout — drift impossible.
            empty_output(EVENT_NAME).print_and_exit()
            return
    except OSError:
        pass

    drifted = find_drifted_hooks(repo_hooks, deployed)
    if not drifted:
        if debug:
            print("[hook-parity] all deployed hook versions match", file=sys.stderr)
        empty_output(EVENT_NAME).print_and_exit()
        return

    msg = build_warning(drifted)
    print(msg, file=sys.stderr)
    context_output(EVENT_NAME, msg).print_and_exit()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise  # Let sys.exit(0) propagate normally
    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            traceback.print_exc(file=sys.stderr)
        else:
            print(f"[hook-parity] Error: {type(e).__name__}: {e}", file=sys.stderr)
        # Crashed hook must fail open — never block session start.
    finally:
        sys.exit(0)
