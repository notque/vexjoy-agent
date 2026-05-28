#!/usr/bin/env python3
"""Auto-derived native-variant registry for /do workflow dispatch.

Scans ``skills/workflow/references/*.js`` for each file's exported
``meta.name`` and emits a JSON map ``{meta.name: script_path}``. A pipeline
name with a registry entry has a deterministic native Workflow variant;
absence means the pipeline is prose-only.

DERIVED, NOT HAND-MAINTAINED. Adding a ``*.js`` with a ``meta.name`` block
auto-registers it — there is no dict to keep in sync (mitigates drift, R3).
See adr/harness-conditional-workflow-dispatch.md.

Parsing: the runtime contract pins ``meta`` to a pure object literal
(``export const meta = { ... name: "..." ... }``). A tolerant regex finds the
``name`` key anywhere inside the first ``meta = { ... }`` block, independent of
key order, quote style, or line breaks. Files without a ``meta.name`` register
nothing.

Pure stdlib. Exit 0 always. Never raises.

Usage:
    python3 scripts/workflow-registry.py            # JSON map to stdout
    python3 scripts/workflow-registry.py --names    # one meta.name per line
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = REPO_ROOT / "skills" / "workflow" / "references"

# Capture the body of the first `meta = { ... }` block (non-greedy to the
# first closing brace at depth 0 — meta is a flat literal by contract).
_META_BLOCK = re.compile(r"meta\s*=\s*\{(.*?)\}", re.DOTALL)
# Within that body, find `name: "value"` (single or double quotes).
_NAME_KEY = re.compile(r"""\bname\s*:\s*(['"])(.*?)\1""", re.DOTALL)


def parse_meta_name(source: str) -> str | None:
    """Extract the exported ``meta.name`` from JS source, or None. Never raises."""
    try:
        block = _META_BLOCK.search(source)
        if not block:
            return None
        m = _NAME_KEY.search(block.group(1))
        return m.group(2) if m else None
    except Exception:
        return None


def build_registry(directory: Path | str | None = None) -> dict[str, str]:
    """Map ``meta.name`` -> absolute ``.js`` path for every variant in *directory*.

    Missing or empty directories yield an empty map. Never raises.
    """
    try:
        root = Path(directory) if directory is not None else DEFAULT_DIR
        if not root.is_dir():
            return {}
        registry: dict[str, str] = {}
        for js in sorted(root.glob("*.js")):
            name = parse_meta_name(js.read_text(encoding="utf-8", errors="replace"))
            if name:
                registry[name] = str(js.resolve())
        return registry
    except Exception:
        return {}


def main(argv: list[str]) -> int:
    registry = build_registry()
    if "--names" in argv:
        for name in registry:
            print(name)
        return 0
    print(json.dumps(registry, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception:
        print("{}")
        sys.exit(0)
