"""Shared git command parsing, Windows path normalization, and repo policy helpers."""

from __future__ import annotations

import json
import os
import re
import shlex
from pathlib import Path

# Git global options that may sit between `git` and the subcommand verb
# (e.g. `git -C dir commit`, `git -c k=v commit`, `git --no-pager commit`).
GIT_OPTS_RE_STR = (
    r"\bgit(?:\s+(?:-[Cc]\s+(?:\"[^\"]*\"|'[^']*'|[^\s\"']\S*)"
    r"|--(?:git-dir|work-tree|namespace|super-prefix|config-env)(?:=|\s+)(?:\"[^\"]*\"|'[^']*'|[^\s\"']\S*)"
    r"|--?[A-Za-z][\w-]*(?:=\S+)?))*\s+"
)
GIT_COMMIT_RE = re.compile(GIT_OPTS_RE_STR + r"commit(?:\s|$)")

_MSYS_DRIVE_RE = re.compile(r"^/([A-Za-z])(/.*)?$")


def normalize_bash_path(path: str) -> str:
    """Convert Git Bash / MSYS2 drive paths (`/c/Users/...`) to `C:/Users/...` on Windows."""
    if not path or os.name != "nt":
        return path
    m = _MSYS_DRIVE_RE.match(path)
    if m:
        drive = m.group(1).upper()
        rest = m.group(2) or "/"
        return f"{drive}:{rest}"
    return path


def _overlay_roots() -> list[Path]:
    """Return configured private overlay roots from ~/.claude/vexjoy/overlays.json."""
    cfg_path = Path.home() / ".claude" / "vexjoy" / "overlays.json"
    if not cfg_path.is_file():
        return []
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    roots: list[Path] = []
    for entry in data.get("overlays", []) if isinstance(data, dict) else []:
        if isinstance(entry, dict) and isinstance(entry.get("root"), str) and entry["root"]:
            try:
                roots.append(Path(os.path.expanduser(entry["root"])).resolve())
            except OSError:
                pass
    return roots


def is_private_or_runtime_skill_path(file_path: str) -> bool:
    """True when *file_path* targets a deployed runtime skills dir or a private overlay repo."""
    if not file_path:
        return False
    norm = normalize_bash_path(file_path).replace("\\", "/")
    lower = norm.lower()
    if any(seg in lower for seg in ("/.claude/skills/", "/.codex/skills/", "/.gemini/skills/", "/private-skills/")):
        return True
    try:
        resolved = Path(os.path.expanduser(norm)).resolve()
    except OSError:
        return False
    for root in _overlay_roots():
        if resolved == root or root in resolved.parents:
            return True
    return False


def repo_allows_direct_main(repo_root: str | Path | None) -> bool:
    """True when *repo_root* explicitly opts in to direct commits on main/master.

    Opt-in sources:
      1. Marker file `<repo_root>/.vexjoy-allow-main-commits`
      2. Entry in `~/.claude/vexjoy/direct-main-repos.json` (`{"repos": [...]}`)
    """
    if not repo_root:
        return False
    try:
        root = Path(normalize_bash_path(str(repo_root))).resolve()
    except OSError:
        return False
    if (root / ".vexjoy-allow-main-commits").is_file():
        return True
    cfg_path = Path.home() / ".claude" / "vexjoy" / "direct-main-repos.json"
    if not cfg_path.is_file():
        return False
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    repos = data.get("repos", []) if isinstance(data, dict) else []
    for entry in repos:
        if not isinstance(entry, str) or not entry.strip():
            continue
        try:
            cand = Path(os.path.expanduser(normalize_bash_path(entry.strip()))).resolve()
        except OSError:
            continue
        if root == cand:
            return True
    return False


_WIN_PATH_RE = re.compile(r"[A-Za-z]:\\[^\s\"']*")


def split_shell_tokens(command: str, *, strict: bool = False) -> list[str]:
    """Tokenize a shell command with POSIX quoting while preserving Windows drive paths."""
    if not command:
        return []
    escaped = _WIN_PATH_RE.sub(lambda m: m.group(0).replace("\\", "\\\\"), command)
    try:
        return shlex.split(escaped, posix=True)
    except ValueError:
        if strict:
            raise
        return command.split()
