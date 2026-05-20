#!/usr/bin/env python3
"""Read-only preflight check for html-artifact skill.

Confirms the reference files the orchestrator expects to load before generation
all exist on disk. Does not modify anything.

Exit codes:
    0: all expected references found
    1: one or more expected references missing
    2: invalid shape

Usage:
    python3 skills/meta/html-artifact/scripts/preflight.py --shape deck
    python3 skills/meta/html-artifact/scripts/preflight.py --shape spec --json-compact
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REFERENCES_DIR = Path(__file__).parent.parent / "references"

# Always-loaded references for every shape.
ALWAYS_LOAD = ("design-system.md", "interaction-patterns.md")

# Map task-spec shape names to their reference filename. Mirrors select-references.py
# but extended to cover the gate-relevant shapes (deck, diagram).
SHAPE_REFERENCE: dict[str, str] = {
    "spec": "shape-spec-exploration.md",
    "code-review": "shape-code-review.md",
    "prototype": "shape-design-prototype.md",
    "report": "shape-report-research.md",
    "editor": "shape-custom-editor.md",
    "data-viz": "shape-data-visualization.md",
    "diagram": "shape-diagram-illustration.md",
    "deck": "shape-slide-deck.md",
}


def preflight(shape: str) -> dict[str, object]:
    """Check that the reference files for ``shape`` exist on disk.

    Args:
        shape: Artifact shape to check.

    Returns:
        Dict with ``ok``, ``loaded`` (existing files), and ``missing`` (absent files).

    Raises:
        ValueError: If ``shape`` is not recognized.
    """
    if shape not in SHAPE_REFERENCE:
        raise ValueError(f"Invalid shape '{shape}'. Valid shapes: {', '.join(sorted(SHAPE_REFERENCE))}")

    expected = list(ALWAYS_LOAD) + [SHAPE_REFERENCE[shape]]
    loaded: list[str] = []
    missing: list[str] = []
    for name in expected:
        if (REFERENCES_DIR / name).is_file():
            loaded.append(name)
        else:
            missing.append(name)

    return {
        "ok": not missing,
        "shape": shape,
        "loaded": loaded,
        "missing": missing,
    }


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Preflight check for html-artifact references.")
    parser.add_argument("--shape", required=True, help="Artifact shape to check.")
    parser.add_argument("--json-compact", action="store_true", help="Output compact JSON.")
    args = parser.parse_args()

    try:
        result = preflight(args.shape)
    except ValueError as e:
        error_result = {"ok": False, "error": str(e), "valid_shapes": sorted(SHAPE_REFERENCE)}
        indent = None if args.json_compact else 2
        json.dump(error_result, sys.stdout, indent=indent)
        sys.stdout.write("\n")
        sys.exit(2)

    indent = None if args.json_compact else 2
    json.dump(result, sys.stdout, indent=indent)
    sys.stdout.write("\n")
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
