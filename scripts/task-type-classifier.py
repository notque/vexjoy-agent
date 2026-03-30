#!/usr/bin/env python3
"""Deterministic classifier for user requests into canonical task types.

Classifies a request string into one of 8 canonical task types using keyword
matching, then returns the corresponding chain template from canonical-chains.md.

Usage:
    python3 scripts/task-type-classifier.py --request "create a new Helm chart"
    python3 scripts/task-type-classifier.py --request "debug failing tests" --json
    python3 scripts/task-type-classifier.py --request "deploy to staging" --check-catalog skills/workflow/catalog.json

Exit codes:
    0 — Classification successful
    1 — Error during classification
    2 — Bad input (missing arguments, invalid paths)
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent

CANONICAL_CHAINS: dict[str, list[str]] = {
    "generation": ["ADR", "RESEARCH", "COMPILE", "GENERATE", "VALIDATE", "REFINE", "OUTPUT"],
    "review": ["ADR", "RESEARCH", "ASSESS", "REVIEW (3+)", "AGGREGATE", "REPORT"],
    "debugging": ["ADR", "PROBE", "SEARCH", "ASSESS", "PLAN", "EXECUTE", "VERIFY", "OUTPUT"],
    "operations": [
        "ADR",
        "PROBE",
        "ASSESS",
        "PLAN",
        "GUARD",
        "EXECUTE",
        "VALIDATE",
        "MONITOR",
        "OUTPUT",
    ],
    "configuration": [
        "ADR",
        "RESEARCH",
        "COMPILE",
        "TEMPLATE",
        "CONFORM",
        "VALIDATE",
        "REFINE",
        "OUTPUT",
    ],
    "analysis": [
        "ADR",
        "RESEARCH",
        "COMPILE",
        "ASSESS",
        "BRAINSTORM",
        "SYNTHESIZE",
        "REFINE",
        "REPORT",
    ],
    "migration": [
        "ADR",
        "CHARACTERIZE",
        "PLAN",
        "GUARD",
        "SNAPSHOT",
        "EXECUTE",
        "VALIDATE",
        "COMPARE",
        "OUTPUT",
    ],
    "testing": [
        "ADR",
        "RESEARCH",
        "COMPILE",
        "CHARACTERIZE",
        "GENERATE",
        "VALIDATE",
        "REFINE",
        "REPORT",
    ],
}

TASK_KEYWORDS: dict[str, list[str]] = {
    "generation": ["create", "write", "generate", "build", "scaffold", "produce"],
    "review": ["review", "check", "audit", "evaluate", "assess", "grade"],
    "debugging": ["debug", "fix", "diagnose", "investigate", "root cause", "failing"],
    "operations": ["deploy", "configure", "scale", "manage", "provision", "set up"],
    "configuration": ["config", "template", "helm", "terraform", "yaml", "manifest"],
    "analysis": ["analyze", "compare", "benchmark", "measure", "assess", "recommend"],
    "migration": ["migrate", "convert", "upgrade", "transition", "move from"],
    "testing": ["test", "coverage", "fuzz", "characterize", "benchmark suite"],
}

DEFAULT_TASK_TYPE = "analysis"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ClassificationResult:
    """Result of classifying a user request."""

    task_type: str
    chain: list[str]
    steps: int
    confidence: float
    keywords_matched: list[str]
    existing_pipeline: str | None = None


@dataclass
class CatalogEntry:
    """A pipeline entry from the catalog file."""

    name: str
    keywords: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Classification logic
# ---------------------------------------------------------------------------


def classify_request(request: str) -> ClassificationResult:
    """Classify a request string into a canonical task type.

    Args:
        request: The user request text to classify.

    Returns:
        ClassificationResult with the best-matching task type, chain, and metadata.
    """
    lowered = request.lower()

    scores: dict[str, list[str]] = {}
    for task_type, keywords in TASK_KEYWORDS.items():
        matched = [kw for kw in keywords if kw in lowered]
        scores[task_type] = matched

    max_count = max(len(v) for v in scores.values())

    if max_count == 0:
        chain = CANONICAL_CHAINS[DEFAULT_TASK_TYPE]
        return ClassificationResult(
            task_type=DEFAULT_TASK_TYPE,
            chain=chain,
            steps=len(chain),
            confidence=0.0,
            keywords_matched=[],
        )

    # Collect all task types with the max match count
    candidates = [t for t, matched in scores.items() if len(matched) == max_count]

    # Tie-break: prefer the type with more steps in its canonical chain
    best = max(candidates, key=lambda t: len(CANONICAL_CHAINS[t]))

    matched_keywords = scores[best]
    total_keywords = len(TASK_KEYWORDS[best])
    confidence = round(len(matched_keywords) / total_keywords, 2) if total_keywords > 0 else 0.0

    chain = CANONICAL_CHAINS[best]
    return ClassificationResult(
        task_type=best,
        chain=chain,
        steps=len(chain),
        confidence=confidence,
        keywords_matched=matched_keywords,
    )


# ---------------------------------------------------------------------------
# Catalog checking
# ---------------------------------------------------------------------------


def load_catalog(catalog_path: Path) -> list[CatalogEntry]:
    """Load a pipeline catalog from a JSON file.

    Args:
        catalog_path: Path to the catalog JSON file.

    Returns:
        List of CatalogEntry objects.

    Raises:
        SystemExit: If the file cannot be read or parsed.
    """
    try:
        data = json.loads(catalog_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"Error: Catalog file not found: {catalog_path}", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in catalog: {e}", file=sys.stderr)
        sys.exit(2)
    except OSError as e:
        print(f"Error: Cannot read catalog: {e}", file=sys.stderr)
        sys.exit(2)

    entries: list[CatalogEntry] = []
    pipelines = data if isinstance(data, list) else data.get("pipelines", [])

    for item in pipelines:
        if isinstance(item, dict) and "name" in item:
            # Accept both "keywords" and "triggers" fields
            keywords = item.get("keywords", []) or item.get("triggers", [])
            if isinstance(keywords, list):
                entries.append(CatalogEntry(name=item["name"], keywords=keywords))

    return entries


def check_catalog_overlap(request: str, catalog: list[CatalogEntry], threshold: float = 0.35) -> str | None:
    """Check if an existing pipeline covers the request with sufficient keyword overlap.

    Uses word-level matching: extracts unique words from trigger phrases and
    checks what fraction appear in the request. Threshold is 0.35 (not 0.70)
    because trigger phrases share many words, inflating the denominator.
    A match of 4-5 trigger words out of 10-12 unique words is a strong signal.

    Args:
        request: The user request text.
        catalog: List of catalog entries to check against.
        threshold: Minimum keyword overlap ratio (default 0.35).

    Returns:
        Pipeline name if overlap meets threshold, None otherwise.
    """
    lowered = request.lower()

    best_name: str | None = None
    best_overlap: float = 0.0

    for entry in catalog:
        if not entry.keywords:
            continue

        # Extract unique words from all trigger phrases
        trigger_words = set()
        for kw in entry.keywords:
            for word in kw.lower().split():
                if len(word) > 2:  # Skip short words (a, an, to, etc.)
                    trigger_words.add(word)

        if not trigger_words:
            continue

        # Count how many trigger words appear in the request
        request_words = set(lowered.split())
        matched = len(trigger_words & request_words)
        overlap = matched / len(trigger_words)

        if overlap >= threshold and overlap > best_overlap:
            best_overlap = overlap
            best_name = entry.name

    return best_name


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def format_chain_arrow(chain: list[str]) -> str:
    """Format a chain list as an arrow-separated string.

    Args:
        chain: List of step names.

    Returns:
        Arrow-separated string like "ADR -> RESEARCH -> OUTPUT".
    """
    return " -> ".join(chain)


def format_text_output(result: ClassificationResult) -> str:
    """Format classification result as a single-line text string.

    Args:
        result: The classification result.

    Returns:
        Formatted text output string.
    """
    if result.existing_pipeline:
        return f"existing_pipeline:{result.existing_pipeline}"

    chain_str = format_chain_arrow(result.chain)
    return f"task_type:{result.task_type} chain:{chain_str} steps:{result.steps}"


def format_json_output(result: ClassificationResult) -> str:
    """Format classification result as a JSON string.

    Args:
        result: The classification result.

    Returns:
        JSON string with classification details.
    """
    if result.existing_pipeline:
        output = {
            "existing_pipeline": result.existing_pipeline,
            "task_type": result.task_type,
            "chain": result.chain,
            "steps": result.steps,
            "confidence": result.confidence,
            "keywords_matched": result.keywords_matched,
        }
    else:
        output = {
            "task_type": result.task_type,
            "chain": result.chain,
            "steps": result.steps,
            "confidence": result.confidence,
            "keywords_matched": result.keywords_matched,
        }

    return json.dumps(output, indent=2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        description="Deterministic classifier for user requests into canonical task types.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            '  python3 scripts/task-type-classifier.py --request "create a new Helm chart"\n'
            '  python3 scripts/task-type-classifier.py --request "debug failing tests" --json\n'
            '  python3 scripts/task-type-classifier.py --request "deploy to staging" '
            "--check-catalog skills/workflow/catalog.json\n"
        ),
    )
    parser.add_argument(
        "--request",
        required=True,
        help="The user request text to classify",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--check-catalog",
        metavar="PATH",
        help="Path to a pipeline catalog JSON file to check for existing coverage",
    )
    return parser


def main() -> int:
    """Entry point."""
    parser = build_parser()
    args = parser.parse_args()

    request = args.request.strip()
    if not request:
        print("Error: --request must not be empty", file=sys.stderr)
        return 2

    # Classify the request
    result = classify_request(request)

    # Check catalog if provided
    if args.check_catalog:
        catalog_path = Path(args.check_catalog)
        if not catalog_path.is_absolute():
            catalog_path = REPO_ROOT / catalog_path
        catalog = load_catalog(catalog_path)
        existing = check_catalog_overlap(request, catalog)
        if existing:
            result.existing_pipeline = existing

    # Output
    if args.json_output:
        print(format_json_output(result))
    else:
        print(format_text_output(result))

    return 0


if __name__ == "__main__":
    sys.exit(main())
