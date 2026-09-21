#!/usr/bin/env python3
"""Deterministic filename generator for html-artifact skill.

Given a request string, produces a kebab-case .html filename.

Usage:
    python3 skills/meta/html-artifact/scripts/generate-filename.py --request "explore 3 approaches to rate limiting"
    python3 skills/meta/html-artifact/scripts/generate-filename.py --request "build a dashboard" --shape data-viz
"""

from __future__ import annotations

import argparse
import re
import sys

VALID_SHAPES = ("spec", "code-review", "prototype", "report", "editor", "data-viz")

STOP_WORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "to",
        "for",
        "of",
        "in",
        "on",
        "at",
        "by",
        "with",
        "from",
        "this",
        "that",
        "these",
        "those",
        "my",
        "our",
        "your",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "shall",
        "should",
        "can",
        "could",
        "may",
        "might",
        "must",
        "need",
        "me",
        "i",
        "we",
        "you",
        "it",
        "he",
        "she",
        "they",
    }
)

VERB_PREFIXES = frozenset(
    {
        "explore",
        "create",
        "make",
        "build",
        "write",
        "generate",
        "show",
        "help",
        "review",
        "explain",
        "analyze",
        "compare",
        "visualize",
        "prototype",
        "design",
        "report",
        "summarize",
        "triage",
        "reorder",
        "edit",
        "tune",
    }
)


def generate_filename(request: str, shape: str | None = None) -> str:
    """Generate a kebab-case .html filename from a request string.

    Args:
        request: The user's natural language request.
        shape: Optional shape to prepend if not already present.

    Returns:
        A kebab-case .html filename.
    """
    # Step 1: lowercase
    lowered = request.lower()

    # Step 2-3: extract words, remove stop words and verb prefixes
    words = re.findall(r"[a-z]+", lowered)
    content_words = [w for w in words if w not in STOP_WORDS and w not in VERB_PREFIXES]

    # Step 4: max 4 content words
    content_words = content_words[:4]

    # Step 7: fallback if no content words
    if not content_words:
        if shape:
            return f"{shape}-artifact.html"
        return "artifact.html"

    filename_base = "-".join(content_words)

    # Step 8: prepend shape if provided and shape word not in filename
    if shape:
        # Normalize shape for comparison (e.g., "data-viz" -> ["data", "viz"])
        shape_parts = shape.split("-")
        if not any(part in content_words for part in shape_parts):
            filename_base = f"{shape}-{filename_base}"

    return f"{filename_base}.html"


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Generate a kebab-case filename from a request.")
    parser.add_argument("--request", required=True, help="User request string.")
    parser.add_argument("--shape", default=None, help="Optional shape to prepend.")
    args = parser.parse_args()

    if args.shape is not None and args.shape not in VALID_SHAPES:
        sys.stderr.write(f"Error: Invalid shape '{args.shape}'. Valid shapes: {', '.join(VALID_SHAPES)}\n")
        sys.exit(1)

    filename = generate_filename(args.request, args.shape)
    sys.stdout.write(filename + "\n")


if __name__ == "__main__":
    main()
