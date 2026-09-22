#!/usr/bin/env python3
# hook-version: 2.0.0
"""SessionStart hook: run ``vexinstall sync --target all`` from the toolkit repo.

Thin, fail-open wrapper (installer spec 5.1). The engine in scripts/vexinstall
does every install, ledger, settings, and index write; this hook only decides
whether to call it and relays its one summary line, for example
``[sync] claude: +2 ~1 -0, 71 skills, 0 collisions; codex: ...``.

Skips (exit 0, at most one stderr line) when:
- cwd is not a toolkit checkout (no skills/, agents/, hooks/);
- ``$VEXJOY_SYNC_DISABLED=1`` (hook smoke tests, CI);
- HOME resolves inside the repo (the engine guard also refuses this; the check
  here keeps a mis-set HOME from even starting a run);
- cwd is a linked git worktree or under an ephemeral prefix
  (``$VEXINSTALL_EPHEMERAL_PREFIXES``, default ``/tmp``). Session sync never
  installs from a transient checkout; use ``install.sh`` for that on purpose.
Any error or timeout prints one warning and exits 0.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

TIMEOUT_S = 18  # under the 20 s SessionStart hook timeout
DISABLE_ENV = "VEXJOY_SYNC_DISABLED"


def is_toolkit_repo(path: Path) -> bool:
    """True for a toolkit-shaped checkout (skills/, agents/, hooks/)."""
    return all((path / d).is_dir() for d in ("skills", "agents", "hooks"))


def home_inside(repo: Path) -> bool:
    """True when ``~/.claude`` would resolve inside *repo*."""
    claude = os.path.realpath(str(Path.home() / ".claude"))
    root = os.path.realpath(str(repo))
    return claude == root or claude.startswith(root.rstrip(os.sep) + os.sep)


def engine_scripts(repo: Path) -> Path | None:
    """scripts/ dir holding the vexinstall package: the repo's, else this hook's checkout."""
    for scripts in (repo / "scripts", Path(__file__).resolve().parent.parent / "scripts"):
        if (scripts / "vexinstall" / "__init__.py").is_file():
            return scripts
    return None


def transient_reason(repo: Path, scripts_dir: Path) -> str | None:
    """Why *repo* is a worktree or ephemeral checkout (engine's own checks), or None."""
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from vexinstall import gitutil

    if gitutil.is_worktree(repo):
        return "running inside a git worktree"
    if gitutil.is_ephemeral(repo):
        return "running inside an ephemeral checkout"
    return None


def build_command(repo: Path, scripts_dir: Path) -> tuple[list[str], dict[str, str]]:
    """``python3 -m vexinstall sync --target all`` argv and env for *repo*."""
    scripts = str(scripts_dir)
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(p for p in (scripts, os.environ.get("PYTHONPATH")) if p)}
    argv = [sys.executable, "-m", "vexinstall", "sync", "--target", "all", "--source-root", str(repo)]
    return argv, env


def run(repo: Path) -> int:
    """Run the engine sync for *repo*; relay its lines. Never raises."""
    if os.environ.get(DISABLE_ENV) == "1":
        return 0
    scripts = engine_scripts(repo)
    if not is_toolkit_repo(repo) or scripts is None:
        return 0
    if home_inside(repo):
        print(f"[sync] skipped: HOME resolves inside {repo}; not syncing into the repo", file=sys.stderr)
        return 0
    reason = transient_reason(repo, scripts)
    if reason:
        print(f"[sync] skipped: {reason} ({repo}); not syncing", file=sys.stderr)
        return 0
    argv, env = build_command(repo, scripts)
    try:
        proc = subprocess.run(
            argv, capture_output=True, text=True, env=env, timeout=TIMEOUT_S, stdin=subprocess.DEVNULL
        )
    except (subprocess.SubprocessError, OSError) as exc:
        print(f"[sync] warning: vexinstall sync failed: {type(exc).__name__}", file=sys.stderr)
        return 0
    for line in proc.stdout.splitlines():
        if line.strip():
            print(line)
    for line in proc.stderr.splitlines():
        if line.strip():
            print(line, file=sys.stderr)
    if proc.returncode != 0 and not proc.stderr.strip():
        print(f"[sync] warning: vexinstall sync exited {proc.returncode}", file=sys.stderr)
    return 0


def main() -> int:
    """Hook entry point: always exit 0."""
    try:
        return run(Path.cwd())
    except Exception as exc:  # fail open: a broken sync must never block a session
        print(f"[sync] warning: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
