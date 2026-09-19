#!/usr/bin/env python3
"""Deterministic reference file selector for html-artifact skill.

Given a shape, outputs the list of reference files to load.
Replaces LLM table-lookup with a script.

Exit codes:
    0: valid shape, references returned
    1: invalid shape

Usage:
    python3 skills/meta/html-artifact/scripts/select-references.py --shape spec
    python3 skills/meta/html-artifact/scripts/select-references.py --shape report --json-compact
"""

from __future__ import annotations

import argparse
import json
import sys

VALID_SHAPES = ("spec", "code-review", "prototype", "report", "editor", "data-viz")

ALWAYS_LOAD = [
    "references/design-system.md",
    "references/interaction-patterns.md",
]

SHAPE_SPECIFIC: dict[str, str] = {
    "spec": "references/shape-spec-exploration.md",
    "code-review": "references/shape-code-review.md",
    "prototype": "references/shape-design-prototype.md",
    "report": "references/shape-report-research.md",
    "editor": "references/shape-custom-editor.md",
    "data-viz": "references/shape-data-visualization.md",
}


def select_references(shape: str) -> dict[str, object]:
    """Return reference file lists for a given shape.

    Args:
        shape: One of the 6 valid artifact shapes.

    Returns:
        Dict with shape, always_load, shape_specific, and all_files keys.

    Raises:
        ValueError: If shape is not one of the valid shapes.
    """
    if shape not in VALID_SHAPES:
        raise ValueError(f"Invalid shape '{shape}'. Valid shapes: {', '.join(VALID_SHAPES)}")

    shape_ref = SHAPE_SPECIFIC[shape]
    shape_specific = [shape_ref]

    return {
        "shape": shape,
        "always_load": list(ALWAYS_LOAD),
        "shape_specific": shape_specific,
        "all_files": ALWAYS_LOAD + shape_specific,
    }


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Select reference files for an artifact shape.")
    parser.add_argument(
        "--shape", required=True, help="Artifact shape (spec, code-review, prototype, report, editor, data-viz)."
    )
    parser.add_argument("--json-compact", action="store_true", help="Output compact JSON (no indentation).")
    args = parser.parse_args()

    try:
        result = select_references(args.shape)
    except ValueError as e:
        error_result = {"error": str(e), "valid_shapes": list(VALID_SHAPES)}
        indent = None if args.json_compact else 2
        json.dump(error_result, sys.stderr, indent=indent)
        sys.stderr.write("\n")
        sys.exit(1)

    indent = None if args.json_compact else 2
    json.dump(result, sys.stdout, indent=indent)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
