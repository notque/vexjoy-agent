#!/usr/bin/env python3
"""Deterministic routing from INDEX files for the /do router.

Reads skills/INDEX.json, pipelines/INDEX.json, and agents/INDEX.json to produce
structured routing decisions: force-routes, scored candidates, pair suggestions,
model preferences, and composition chains.

Usage:
    python3 scripts/index-router.py --request "write Go tests for auth package" --json
    python3 scripts/index-router.py --request "push this to GitHub" --json
    python3 scripts/index-router.py --request "help me understand this error" --force-only

Exit codes:
    0 — Always (routing is advisory, not blocking)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent

INDEX_PATHS: dict[str, Path] = {
    "skills": REPO_ROOT / "skills" / "INDEX.json",
    "pipelines": REPO_ROOT / "pipelines" / "INDEX.json",
    "agents": REPO_ROOT / "agents" / "INDEX.json",
}

# Composition chains encode common multi-skill workflows.
# Key = entry skill, value = ordered sequence of skills in the chain.
COMPOSITION_CHAINS: dict[str, list[str]] = {
    "systematic-debugging": ["systematic-debugging", "test-driven-development", "pr-pipeline"],
    "research-to-article": [
        "research-to-article",
        "de-ai-pipeline",
        "wordpress-uploader",
        "wordpress-live-validation",
    ],
    "forensics": ["forensics", "testing-anti-patterns", "learn"],
    "docs-sync-checker": ["docs-sync-checker", "doc-pipeline", "generate-claudemd"],
    "systematic-refactoring": ["systematic-refactoring", "code-linting", "verification-before-completion"],
}

MAX_CANDIDATES = 10
MIN_SCORE_THRESHOLD = 0.1


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class IndexEntry:
    """A unified entry from any INDEX file."""

    name: str
    entry_type: str  # "skill", "pipeline", or "agent"
    triggers: list[str] = field(default_factory=list)
    force_route: bool = False
    agent: str | None = None
    model: str | None = None
    pairs_with: list[str] = field(default_factory=list)
    description: str = ""
    category: str = ""


@dataclass
class Candidate:
    """A scored routing candidate."""

    entry_type: str
    name: str
    score: float
    agent: str | None = None
    model: str | None = None


@dataclass
class RoutingResult:
    """Complete routing decision."""

    force_route: dict[str, str] | None = None
    candidates: list[Candidate] = field(default_factory=list)
    pairs_with: list[str] = field(default_factory=list)
    model_preference: str | None = None
    composition_chains: list[list[str]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# INDEX loading
# ---------------------------------------------------------------------------


def load_indexes() -> list[IndexEntry]:
    """Load all three INDEX files and return a unified list of entries.

    Missing or malformed INDEX files are silently skipped (empty list returned
    for that index type).

    Returns:
        List of IndexEntry objects from all available INDEX files.
    """
    entries: list[IndexEntry] = []

    for index_type, path in INDEX_PATHS.items():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            continue

        # Each INDEX file uses its type as the top-level key
        items = raw.get(index_type, {})
        if not isinstance(items, dict):
            continue

        for name, data in items.items():
            if not isinstance(data, dict):
                continue

            entry = IndexEntry(
                name=name,
                entry_type="skill" if index_type == "skills" else index_type.rstrip("s"),
                triggers=data.get("triggers", []),
                force_route=bool(data.get("force_route", False)),
                agent=data.get("agent"),
                model=data.get("model"),
                pairs_with=data.get("pairs_with", []),
                description=data.get("description", ""),
                category=data.get("category", ""),
            )
            entries.append(entry)

    return entries


# ---------------------------------------------------------------------------
# Force-route matching
# ---------------------------------------------------------------------------


def _is_single_word(trigger: str) -> bool:
    """Check if a trigger is a single word (no spaces).

    Args:
        trigger: The trigger string to check.

    Returns:
        True if the trigger contains no spaces after stripping.
    """
    return " " not in trigger.strip()


def _trigger_matches(trigger: str, request_lower: str) -> bool:
    r"""Check if a trigger matches the request.

    Single-word triggers use word-boundary matching (``\b``) to avoid false
    positives like "push" matching "let me push back on this design."
    Multi-word triggers use substring containment, which is safe because the
    full phrase must appear.

    Note: ``\b`` treats hyphens as word boundaries, so a trigger like
    "go-testing" is effectively matched as the phrase "go-testing" appearing
    between word boundaries on each end. This is the desired behavior for
    hyphenated compound triggers.

    Args:
        trigger: A single trigger phrase (original case).
        request_lower: The lowercased request string.

    Returns:
        True if the trigger matches.
    """
    trigger_lower = trigger.lower().strip()
    if not trigger_lower:
        return False

    if _is_single_word(trigger_lower):
        # Word-boundary match for single-word triggers
        pattern = r"\b" + re.escape(trigger_lower) + r"\b"
        return re.search(pattern, request_lower, re.IGNORECASE) is not None

    # Multi-word triggers: substring containment (phrase must appear in full)
    return trigger_lower in request_lower


def check_force_routes(request: str, entries: list[IndexEntry]) -> IndexEntry | None:
    """Check force-routed entries for a trigger match.

    Single-word triggers use word-boundary matching to prevent false positives
    (e.g. "go" should not match "let's go ahead"). Multi-word triggers use
    substring containment which is safe since the full phrase must appear.

    Args:
        request: The user request text.
        entries: All loaded INDEX entries.

    Returns:
        The first matching force-route entry, or None.
    """
    lowered = request.lower()

    for entry in entries:
        if not entry.force_route:
            continue
        for trigger in entry.triggers:
            if _trigger_matches(trigger, lowered):
                return entry

    return None


# ---------------------------------------------------------------------------
# Candidate scoring
# ---------------------------------------------------------------------------


def _extract_trigger_words(triggers: list[str]) -> set[str]:
    """Extract unique words (length > 2) from trigger phrases.

    Args:
        triggers: List of trigger phrase strings.

    Returns:
        Set of unique lowercase words longer than 2 characters.
    """
    words: set[str] = set()
    for trigger in triggers:
        for word in trigger.lower().split():
            if len(word) > 2:
                words.add(word)
    return words


def score_candidates(request: str, entries: list[IndexEntry]) -> list[Candidate]:
    """Score all entries by trigger word overlap with the request.

    Score = count of trigger words appearing in the request / total trigger
    words for the entry. Returns the top candidates sorted by score descending.

    Args:
        request: The user request text.
        entries: All loaded INDEX entries.

    Returns:
        List of Candidate objects with score > MIN_SCORE_THRESHOLD, sorted by
        score descending, limited to MAX_CANDIDATES.
    """
    request_words = set(request.lower().split())
    scored: list[Candidate] = []

    for entry in entries:
        trigger_words = _extract_trigger_words(entry.triggers)
        if not trigger_words:
            continue

        matched = len(trigger_words & request_words)
        score = round(matched / len(trigger_words), 2)

        if score > MIN_SCORE_THRESHOLD:
            scored.append(
                Candidate(
                    entry_type=entry.entry_type,
                    name=entry.name,
                    score=score,
                    agent=entry.agent,
                    model=entry.model,
                )
            )

    scored.sort(key=lambda c: c.score, reverse=True)
    return scored[:MAX_CANDIDATES]


# ---------------------------------------------------------------------------
# Agent resolution
# ---------------------------------------------------------------------------


def resolve_agent(candidate: Candidate, entries: list[IndexEntry]) -> str | None:
    """Resolve the agent for a candidate.

    If the candidate already has an agent, return it. Otherwise, look through
    agent entries for the best trigger-word match against the candidate name.

    Args:
        candidate: The candidate to resolve an agent for.
        entries: All loaded INDEX entries.

    Returns:
        Agent name or None if no agent can be resolved.
    """
    if candidate.agent:
        return candidate.agent

    # Try to match candidate name words against agent triggers
    candidate_words = set(candidate.name.lower().replace("-", " ").split())
    best_agent: str | None = None
    best_overlap = 0

    for entry in entries:
        if entry.entry_type != "agent":
            continue
        trigger_words = _extract_trigger_words(entry.triggers)
        if not trigger_words:
            continue
        overlap = len(candidate_words & trigger_words)
        if overlap > best_overlap:
            best_overlap = overlap
            best_agent = entry.name

    return best_agent


# ---------------------------------------------------------------------------
# Pair suggestions
# ---------------------------------------------------------------------------


def suggest_pairs(matched_entries: list[IndexEntry]) -> list[str]:
    """Collect unique pairs_with values from matched entries.

    Args:
        matched_entries: Entries that matched the request.

    Returns:
        Deduplicated list of pair suggestions, preserving first-seen order.
    """
    seen: set[str] = set()
    pairs: list[str] = []

    # Also collect the names of matched entries to exclude self-references
    matched_names = {e.name for e in matched_entries}

    for entry in matched_entries:
        for pair in entry.pairs_with:
            if pair not in seen and pair not in matched_names:
                seen.add(pair)
                pairs.append(pair)

    return pairs


# ---------------------------------------------------------------------------
# Composition chains
# ---------------------------------------------------------------------------


def check_composition_chains(matched_name: str | None) -> list[list[str]]:
    """Check if the matched skill is part of a composition chain.

    Args:
        matched_name: Name of the primary matched skill/pipeline.

    Returns:
        List of composition chains that include the matched skill.
    """
    if not matched_name:
        return []

    chains: list[list[str]] = []
    for _trigger, chain in COMPOSITION_CHAINS.items():
        if matched_name in chain:
            chains.append(chain)

    return chains


# ---------------------------------------------------------------------------
# Main routing logic
# ---------------------------------------------------------------------------


def route_request(request: str, force_only: bool = False) -> RoutingResult:
    """Route a request using INDEX file data.

    Args:
        request: The user request text.
        force_only: If True, only check force routes (fast path).

    Returns:
        RoutingResult with force route, candidates, pairs, model, and chains.
    """
    entries = load_indexes()
    result = RoutingResult()

    # Step 1: Check force routes
    force_match = check_force_routes(request, entries)
    if force_match:
        agent = force_match.agent
        # If force match has no agent, try to resolve from agent INDEX
        if not agent:
            dummy = Candidate(
                entry_type=force_match.entry_type,
                name=force_match.name,
                score=1.0,
                agent=None,
                model=force_match.model,
            )
            agent = resolve_agent(dummy, entries)

        force_dict: dict[str, str] = {force_match.entry_type: force_match.name}
        if agent:
            force_dict["agent"] = agent
        result.force_route = force_dict
        result.model_preference = force_match.model
        result.pairs_with = suggest_pairs([force_match])
        result.composition_chains = check_composition_chains(force_match.name)
        if force_only:
            return result

    # Step 2: Score candidates (skip if force_only)
    if not force_only:
        candidates = score_candidates(request, entries)

        # Resolve agents for top candidates
        for candidate in candidates:
            if not candidate.agent:
                candidate.agent = resolve_agent(candidate, entries)

        result.candidates = candidates

        # Step 3: Determine model preference from top candidate if not set
        if not result.model_preference and candidates:
            result.model_preference = candidates[0].model

        # Step 4: Collect pairs from top candidates
        if not result.force_route and candidates:
            # Find full entries for top candidates
            entry_map = {e.name: e for e in entries}
            matched = [entry_map[c.name] for c in candidates[:3] if c.name in entry_map]
            result.pairs_with = suggest_pairs(matched)

        # Step 5: Check composition chains from top candidate
        if not result.composition_chains and candidates:
            result.composition_chains = check_composition_chains(candidates[0].name)

    return result


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def format_json_output(result: RoutingResult) -> str:
    """Format routing result as JSON.

    Args:
        result: The routing result.

    Returns:
        JSON string with routing details.
    """
    output: dict[str, object] = {
        "force_route": result.force_route,
        "candidates": [
            {
                "type": c.entry_type,
                "name": c.name,
                "score": c.score,
                **({"agent": c.agent} if c.agent else {}),
                **({"model": c.model} if c.model else {}),
            }
            for c in result.candidates
        ],
        "pairs_with": result.pairs_with,
        "model_preference": result.model_preference,
        "composition_chains": result.composition_chains,
    }
    return json.dumps(output, indent=2)


def format_text_output(result: RoutingResult) -> str:
    """Format routing result as human-readable text.

    Args:
        result: The routing result.

    Returns:
        Multi-line text summary.
    """
    lines: list[str] = []

    if result.force_route:
        parts = [f"{k}={v}" for k, v in result.force_route.items()]
        lines.append(f"force_route: {', '.join(parts)}")

    if result.candidates:
        lines.append("candidates:")
        for c in result.candidates:
            agent_str = f" (agent={c.agent})" if c.agent else ""
            lines.append(f"  {c.entry_type}:{c.name} score={c.score}{agent_str}")

    if result.pairs_with:
        lines.append(f"pairs_with: {', '.join(result.pairs_with)}")

    if result.model_preference:
        lines.append(f"model: {result.model_preference}")

    if result.composition_chains:
        for chain in result.composition_chains:
            lines.append(f"chain: {' -> '.join(chain)}")

    if not lines:
        lines.append("no_match: true")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        description="Deterministic routing from INDEX files for the /do router.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            '  python3 scripts/index-router.py --request "write Go tests for auth" --json\n'
            '  python3 scripts/index-router.py --request "push this to GitHub" --json\n'
            '  python3 scripts/index-router.py --request "help me understand this error" --force-only\n'
        ),
    )
    parser.add_argument(
        "--request",
        required=True,
        help="The user request text to route",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--force-only",
        action="store_true",
        dest="force_only",
        help="Only check force routes (fast path)",
    )
    return parser


def main() -> int:
    """Entry point."""
    parser = build_parser()
    args = parser.parse_args()

    request = args.request.strip()
    if not request:
        print("Error: --request must not be empty", file=sys.stderr)
        return 0  # Advisory — always exit 0

    result = route_request(request, force_only=args.force_only)

    if args.json_output:
        print(format_json_output(result))
    else:
        print(format_text_output(result))

    return 0


if __name__ == "__main__":
    sys.exit(main())
