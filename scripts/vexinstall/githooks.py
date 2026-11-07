"""Pre-engine post-merge hook detection. Read-only.

The pre-engine install.sh wrote a post-merge that ran an add-only ``ln -s``
loop over ``$HOME/.claude`` and the other runtime roots after every pull. Git
Bash without symlink privilege made copies, which landed inside engine-owned
dirs, so the engine treated them as user edits and stopped updating them. The
current hook only runs ``-m vexinstall sync --target all``.

``doctor`` and the SessionStart sync hook report a legacy hook. Neither
rewrites it, because the repo guard forbids engine writes inside the repo.
Imports stay light (no apply, no lock), so the sync hook can warn even where
the engine cannot load.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from . import gitutil
from .adapters import ADAPTERS

LEGACY_HEADER = "auto-syncs new items after git pull"
INSTALL_MARKER = "Written by vexjoy-agent"
_SCAN_BYTES = 64 * 1024
_ROOTS = "|".join(sorted(re.escape(a.root) for a in ADAPTERS.values()))
_DIRS = "|".join(
    sorted({"hooks", "scripts"} | {d for a in ADAPTERS.values() for d in (a.skills, a.agents, a.commands) if d})
)
# `ln -s` in any spelling: -s, -sf, -fs, -f -s, --symbolic.
_LN_SYMLINK = re.compile(r"\bln(?:\s+-[-\w]+)*?\s+(?:-[A-Za-z]*s[A-Za-z]*|--symbolic)(?=\s)")
# A $HOME-anchored runtime root on its own, with a variable below it, or with an
# engine-managed dir below it. A personal file such as ~/.claude/CLAUDE.md does not count.
_RUNTIME_ROOT = re.compile(r"(?:\$HOME|\$\{HOME\}|~)\"?/(?:" + _ROOTS + r")(?:/(?:" + _DIRS + r")\b|/\$|/?(?![\w./-]))")
_ENGINE_SYNC = re.compile(r"-m\s+vexinstall\s+sync\b[^\n]*?--target(?:\s+|=)all\b")
_COMMENT = re.compile(r"(?:^|\s)#.*")


@dataclass(frozen=True)
class LegacyHook:
    """A legacy post-merge that git runs, and how to remove it."""

    path: Path
    advice: str


def is_legacy_post_merge(text: str) -> bool:
    """True for a post-merge that links repo items into runtime roots itself.

    Signs: ``ln -s`` plus a runtime root (``_RUNTIME_ROOT``), or the legacy
    header. A line that runs ``-m vexinstall sync --target all`` cancels only
    the header sign, so a legacy loop with that line added still matches.
    Comments count only for the header.
    """
    code = "\n".join(_COMMENT.sub("", line) for line in text.splitlines())
    links = _LN_SYMLINK.search(code) is not None and _RUNTIME_ROOT.search(code) is not None
    return links or (LEGACY_HEADER in text and _ENGINE_SYNC.search(code) is None)


def advice(text: str) -> str:
    """Why the hook is harmful and how to remove it.

    Deleting is always safe: the SessionStart sync keeps installs current. A
    hook without the install.sh marker may also hold the user's own hooks.
    """
    why = (
        "after every git pull it links or copies repo files into ~/.claude and the other agent dirs,"
        " so the engine stops updating them"
    )
    if INSTALL_MARKER in text:
        return f"{why}; delete it (the SessionStart sync keeps installs current)"
    return f"{why}; remove its ln -s loop, or delete it if nothing else in it is yours"


def find_legacy_post_merge(root: Path) -> LegacyHook | None:
    """The legacy post-merge git runs for the checkout at *root*, or None. Never writes."""
    hooks = gitutil.hooks_dir(root)
    if hooks is None:
        return None
    hook = hooks / "post-merge"
    # os.path.isfile, not Path.is_file: an unsearchable hooks dir must return False, not raise.
    # git skips a hook without the exec bit; Windows has none, so X_OK always passes there.
    if not os.path.isfile(hook) or not os.access(hook, os.X_OK):
        return None
    try:
        with open(hook, "rb") as fh:
            text = fh.read(_SCAN_BYTES).decode("utf-8", "replace")
    except OSError:
        return None
    return LegacyHook(hook, advice(text)) if is_legacy_post_merge(text) else None
