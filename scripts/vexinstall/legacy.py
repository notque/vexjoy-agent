"""Legacy hook-command and repo-link patterns adopted as engine-owned (spec 10).

Old installs registered hooks by absolute repo path instead of through
``~/.claude/hooks`` and linked container entries to prior toolkit checkouts.
A command or link target matching one of these patterns is treated as owned so
the engine can replace, dedupe, or prune it.
"""

from __future__ import annotations

import re

LEGACY_HOOK_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"/claude-code-toolkit/hooks/[^/]+$"),
    re.compile(r"/vexjoy-agent/hooks/[^/]+$"),
    re.compile(r"/claude-code-toolkit/hooks/lib/[^/]+$"),
    re.compile(r"/vexjoy-agent/hooks/lib/[^/]+$"),
)

LEGACY_REPO_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"/(?:claude-code-toolkit|vexjoy-agent)/(?:skills|agents|commands|hooks|scripts)(?:/|$)"),
)


def is_legacy_hook_path(path: str) -> bool:
    """True when *path* matches an old absolute repo hook location."""
    return any(p.search(path) for p in LEGACY_HOOK_PATTERNS)


def is_legacy_repo_path(path: str) -> bool:
    """True when *path* points into a toolkit checkout's managed source dirs."""
    return any(p.search(path.replace("\\", "/")) for p in LEGACY_REPO_PATTERNS)
