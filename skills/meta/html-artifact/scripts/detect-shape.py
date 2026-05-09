#!/usr/bin/env python3
"""Deterministic shape classifier for html-artifact skill.

Analyzes a user request string and returns the best artifact shape
from eight categories: spec, code-review, prototype, report, editor, data-viz,
diagram, deck.

Classification is purely signal-word based — same input always produces same output.

Usage:
    python3 skills/meta/html-artifact/scripts/detect-shape.py --request "explore 3 auth approaches"
    python3 skills/meta/html-artifact/scripts/detect-shape.py --request "visualize metrics" --json-compact
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field

# --- Shape definitions ---
# Each shape has primary signals (2 points) and secondary signals (1 point).
# Priority order for tie-breaking: editor > spec > code-review > prototype > report > data-viz

SHAPES: dict[str, dict[str, list[str]]] = {
    "editor": {
        "primary": [
            "reorder",
            "triage",
            "edit config",
            "tune prompt",
            "pick",
            "drag",
            "bucket",
            "prioritize",
            "flag",
        ],
        "secondary": [
            "sort tickets",
            "manage",
            "organize",
            "configuration",
            "feature flags",
        ],
    },
    "spec": {
        "primary": [
            "plan",
            "explore",
            "compare",
            "brainstorm",
            "approach",
            "option",
            "tradeoff",
            "direction",
        ],
        "secondary": [
            "implementation plan",
            "design options",
            "side by side",
            "pros and cons",
        ],
    },
    "code-review": {
        "primary": [
            "review pr",
            "review this pr",
            "review my pr",
            "diff",
            "annotate",
            "code review",
            "explain code",
            "understand module",
            "pr writeup",
        ],
        "secondary": [
            "pull request",
            "code walkthrough",
            "what changed",
            "review the pr",
            "pr review",
        ],
    },
    "prototype": {
        "primary": [
            "prototype",
            "animation",
            "tune",
            "slider",
            "knob",
            "try options",
            "component",
            "variant",
            "tweak",
        ],
        "secondary": [
            "design system",
            "mockup",
            "interaction",
            "adjust",
            "playground",
        ],
    },
    "report": {
        "primary": [
            "report",
            "summarize",
            "status",
            "explain how",
            "incident",
            "timeline",
            "weekly",
            "research",
            "learning",
        ],
        "secondary": [
            "post-mortem",
            "overview",
            "digest",
            "briefing",
            "explainer",
        ],
    },
    "data-viz": {
        "primary": [
            "visualize",
            "chart",
            "dashboard",
            "graph",
            "trend",
            "metric",
            "plot",
            "data",
            "analytics",
        ],
        "secondary": [
            "show me the numbers",
            "performance over time",
            "distribution",
        ],
    },
    "diagram": {
        "primary": [
            "diagram",
            "flowchart",
            "architecture",
            "sequence",
            "svg",
            "illustrate",
            "figure",
            "data flow",
            "dependency map",
            "node graph",
        ],
        "secondary": [
            "draw a diagram",
            "system diagram",
            "service mesh",
            "topology",
        ],
    },
    "deck": {
        "primary": [
            "slides",
            "presentation",
            "deck",
            "talk",
            "pitch",
            "keynote",
            "slideshow",
        ],
        "secondary": [
            "slide deck",
            "lightning talk",
            "conference talk",
            "pitch deck",
        ],
    },
}

# Priority order for tie-breaking (index 0 = highest priority)
PRIORITY_ORDER: list[str] = ["editor", "spec", "code-review", "diagram", "deck", "prototype", "report", "data-viz"]

DEFAULT_SHAPE = "report"


@dataclass
class ShapeResult:
    """Classification result for a single shape."""

    shape: str
    score: int
    matched_signals: list[str] = field(default_factory=list)


def classify_request(request: str) -> dict[str, object]:
    """Classify a user request into an artifact shape.

    Args:
        request: The user's natural language request string.

    Returns:
        Dict with keys: shape, confidence, signals.
    """
    lowered = request.lower().strip()

    if not lowered:
        return {"shape": DEFAULT_SHAPE, "confidence": "low", "signals": []}

    results: list[ShapeResult] = []

    for shape_name in PRIORITY_ORDER:
        signals = SHAPES[shape_name]
        score = 0
        matched: list[str] = []

        for signal in signals["primary"]:
            if signal in lowered:
                score += 2
                matched.append(signal)

        for signal in signals["secondary"]:
            if signal in lowered:
                score += 1
                matched.append(signal)

        results.append(ShapeResult(shape=shape_name, score=score, matched_signals=matched))

    # Sort by score descending; ties broken by priority order (already iteration order)
    best = max(results, key=lambda r: (r.score, -PRIORITY_ORDER.index(r.shape)))

    if best.score == 0:
        return {"shape": DEFAULT_SHAPE, "confidence": "low", "signals": []}

    if best.score >= 4:
        confidence = "high"
    elif best.score >= 2:
        confidence = "medium"
    else:
        confidence = "low"

    return {"shape": best.shape, "confidence": confidence, "signals": best.matched_signals}


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Classify a user request into an artifact shape.")
    parser.add_argument("--request", required=True, help="User request string to classify.")
    parser.add_argument("--json-compact", action="store_true", help="Output compact JSON (no indentation).")
    args = parser.parse_args()

    result = classify_request(args.request)

    indent = None if args.json_compact else 2
    json.dump(result, sys.stdout, indent=indent)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
