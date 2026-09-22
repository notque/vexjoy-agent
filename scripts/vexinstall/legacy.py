"""Legacy hook-command patterns adopted as engine-owned (spec 10).

Old installs registered hooks by absolute repo path instead of through
``~/.claude/hooks``. A command whose first path token matches one of these
patterns is treated as owned so the engine can replace or dedupe it.
"""

from __future__ import annotations

import re

LEGACY_HOOK_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"/claude-code-toolkit/hooks/[^/]+$"),
    re.compile(r"/vexjoy-agent/hooks/[^/]+$"),
    re.compile(r"/claude-code-toolkit/hooks/lib/[^/]+$"),
    re.compile(r"/vexjoy-agent/hooks/lib/[^/]+$"),
)


def is_legacy_hook_path(path: str) -> bool:
    """True when *path* matches an old absolute repo hook location."""
    return any(p.search(path) for p in LEGACY_HOOK_PATTERNS)
