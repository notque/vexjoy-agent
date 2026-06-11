"""Shared tracked + local INDEX merge for the routing scripts.

Single source for the merge formerly hand-duplicated in routing-manifest.py,
pre-route.py, and index-router.py. Those scripts import this module; the
merge can no longer diverge between them.

Importable by name (underscores). The routing scripts add their own directory
to sys.path before importing, since they run as files, not as a package.
"""

from __future__ import annotations

import json
from pathlib import Path


def load_index_items(tracked: Path, local_name: str | None, key: str) -> dict:
    """Load index items from the tracked file, overlaying the local override.

    Local override files (INDEX.local.json) are gitignored supersets produced
    by the generator with --include-private; they add entries for
    symlinked/private directories. The local file regenerates less often than
    the tracked one, so it can be stale. The merge is add-only (tracked first,
    local fills gaps per-name): a stale local can never hide a tracked skill
    or agent, and never overrides tracked entry content such as triggers or
    force_route — full replacement and per-name update both did.
    """
    items: dict = {}
    paths = [tracked]
    if local_name:
        local = tracked.parent / local_name
        if local.exists():
            paths.append(local)
    for path in paths:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            continue
        loaded = raw.get(key, {})
        if isinstance(loaded, dict):
            for name, data in loaded.items():
                items.setdefault(name, data)
    return items
