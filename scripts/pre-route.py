#!/usr/bin/env python3
"""Deterministic pre-router for /do dispatch.

Pattern-matches user requests against trigger keywords from INDEX.json
files BEFORE the Haiku LLM routing agent. High-confidence matches skip
LLM routing entirely; low-confidence or unmatched requests fall through.

Usage:
    python3 scripts/pre-route.py --request "run go tests"
    python3 scripts/pre-route.py --request "create a PR" --json-compact

Exit codes:
    0 -- always (output is JSON to stdout)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _resolve_index(tracked: Path, local_name: str) -> Path:
    """Return the local override path when it exists, otherwise the tracked path."""
    local = tracked.parent / local_name
    return local if local.exists() else tracked


INDEX_PATHS = {
    "skills": _resolve_index(REPO_ROOT / "skills" / "INDEX.json", "INDEX.local.json"),
    "agents": _resolve_index(REPO_ROOT / "agents" / "INDEX.json", "INDEX.local.json"),
}

# Phrases that look like trigger matches but are common English idioms
# unrelated to the skill. Keyed by skill name -> set of disqualifying context words.
SEMANTIC_GUARDS: dict[str, set[str]] = {
    "pr-workflow": {"back", "pressure", "pushback", "pushed", "pushing"},
    "fish-shell-config": {"for", "bug", "bugs", "compliments", "information", "ideas", "answers", "out", "feedback"},
    "voice-writer": {"remove", "strip", "clean", "detect", "identify", "fix", "scan", "audit"},
}


@dataclass
class MatchEntry:
    """A single trigger-to-target mapping."""

    name: str
    entry_type: str  # "skill" or "agent"
    agent: str | None
    force_route: bool
    trigger: str
    pattern: re.Pattern[str]


@dataclass
class ScoredMatch:
    """A candidate match with computed score."""

    name: str
    entry_type: str
    agent: str | None
    force_route: bool
    matched_triggers: list[str] = field(default_factory=list)
    total_chars: int = 0
    score: float = 0.0


def load_entries() -> list[dict]:
    """Load all INDEX entries into a flat list."""
    entries: list[dict] = []

    for index_type, path in INDEX_PATHS.items():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            continue

        items = raw.get(index_type, {})
        if not isinstance(items, dict):
            continue

        for name, data in items.items():
            if not isinstance(data, dict):
                continue
            entries.append(
                {
                    "name": name,
                    "type": "skill" if index_type == "skills" else "agent",
                    "triggers": data.get("triggers", []),
                    "agent": data.get("agent"),
                    "force_route": bool(data.get("force_route", False)),
                }
            )

    return entries


def _build_pattern(trigger_lower: str) -> re.Pattern[str]:
    """Build a regex pattern for a trigger phrase.

    Single-word triggers: exact word-boundary match.
    Multi-word triggers: each word must appear in order with up to 2
    intervening words allowed (handles "create a PR" matching trigger
    "create PR", or "run the go tests" matching "go test").
    """
    words = trigger_lower.split()
    if len(words) == 1:
        escaped = re.escape(words[0])
        return re.compile(rf"\b{escaped}\b", re.IGNORECASE)

    # Multi-word: allow up to 2 words between each trigger word.
    # Also allow the last trigger word to be a prefix (e.g. "test" matches "tests").
    parts = []
    for i, word in enumerate(words):
        escaped = re.escape(word)
        if i == len(words) - 1:
            # Last word: allow plural/suffix (word boundary after stem)
            parts.append(rf"\b{escaped}\w*\b")
        else:
            parts.append(rf"\b{escaped}\b")

    # Join with "up to 2 intervening words" gap
    gap = r"(?:\s+\S+){0,2}\s+"
    full_pattern = gap.join(parts)
    return re.compile(full_pattern, re.IGNORECASE)


def build_match_table(entries: list[dict]) -> list[MatchEntry]:
    """Compile trigger keywords into regex patterns.

    Single-word triggers use exact word-boundary match.
    Multi-word triggers allow up to 2 intervening words between
    trigger words (e.g. "create PR" matches "create a PR").
    """
    table: list[MatchEntry] = []

    for entry in entries:
        name = entry["name"]
        entry_type = entry["type"]
        agent = entry.get("agent")
        force_route = entry.get("force_route", False)

        for trigger in entry.get("triggers", []):
            trigger_lower = trigger.lower()
            pattern = _build_pattern(trigger_lower)

            table.append(
                MatchEntry(
                    name=name,
                    entry_type=entry_type,
                    agent=agent,
                    force_route=force_route,
                    trigger=trigger_lower,
                    pattern=pattern,
                )
            )

    return table


def _is_semantically_guarded(
    skill_name: str, request_lower: str, matched_trigger: str, trigger_pattern: re.Pattern[str]
) -> bool:
    """Check if the match is a false positive due to common English idioms.

    Uses the trigger's compiled regex pattern to locate the match position,
    which correctly handles multi-word triggers with intervening words
    (e.g. "create a PR" matching trigger "create pr").

    Returns True if the match should be discarded.
    """
    guards = SEMANTIC_GUARDS.get(skill_name)
    if not guards:
        return False

    # Use the regex pattern to find the trigger match position, not str.find().
    # str.find() fails for multi-word triggers with intervening words.
    m = trigger_pattern.search(request_lower)
    if m is None:
        return False

    trigger_pos = m.start()
    match_len = m.end() - m.start()

    # Extract context window: 60 chars before and after the trigger match
    ctx_start = max(0, trigger_pos - 60)
    ctx_end = min(len(request_lower), trigger_pos + match_len + 60)
    context = request_lower[ctx_start:ctx_end]

    words_in_context = set(re.findall(r"\b\w+\b", context))
    return bool(words_in_context & guards)


def score_matches(table: list[MatchEntry], request: str) -> dict[str, ScoredMatch]:
    """Score each entry by matching triggers against the request.

    Scoring:
    - Each matched trigger adds 1.0 to score
    - Force-route entries get a 2.0 bonus
    - Longer triggers get a specificity bonus (len/100)
    """
    request_lower = request.lower()
    candidates: dict[str, ScoredMatch] = {}

    for entry in table:
        if not entry.pattern.search(request_lower):
            continue

        # Semantic guard check
        if _is_semantically_guarded(entry.name, request_lower, entry.trigger, entry.pattern):
            continue

        key = f"{entry.entry_type}:{entry.name}"
        if key not in candidates:
            candidates[key] = ScoredMatch(
                name=entry.name,
                entry_type=entry.entry_type,
                agent=entry.agent,
                force_route=entry.force_route,
            )

        match = candidates[key]
        match.matched_triggers.append(entry.trigger)
        match.total_chars += len(entry.trigger)

    # Compute final scores
    for match in candidates.values():
        trigger_count = len(match.matched_triggers)
        specificity_bonus = match.total_chars / 100.0
        force_bonus = 2.0 if match.force_route else 0.0
        match.score = trigger_count + specificity_bonus + force_bonus

    return candidates


def determine_confidence(match: ScoredMatch) -> str:
    """Determine confidence level based on match characteristics.

    Thresholds:
    - force_route + 2+ trigger matches -> "high"
    - force_route + 1 trigger match -> "medium"
    - non-force + 3+ trigger matches -> "medium"
    - anything less -> "low" (fall through)
    """
    trigger_count = len(match.matched_triggers)

    if match.force_route and trigger_count >= 2:
        return "high"
    if match.force_route and trigger_count >= 1:
        return "medium"
    if not match.force_route and trigger_count >= 3:
        return "medium"
    return "low"


def route(request: str, entries: list[dict] | None = None) -> dict:
    """Run the pre-router on a request string.

    Args:
        request: The user's request text.
        entries: Optional pre-loaded INDEX entries. Loaded from disk if None.

    Returns:
        Routing decision dict with matched, agent, skill, confidence,
        match_type, and reasoning fields.
    """
    if entries is None:
        entries = load_entries()

    table = build_match_table(entries)
    candidates = score_matches(table, request)

    if not candidates:
        return {
            "matched": False,
            "agent": None,
            "skill": None,
            "confidence": "low",
            "match_type": "fallthrough",
            "reasoning": "no trigger keywords matched",
        }

    # Sort by score descending, then by name ascending for deterministic tie-breaking
    ranked = sorted(candidates.values(), key=lambda m: (-m.score, m.name))
    top = ranked[0]
    confidence = determine_confidence(top)

    if confidence == "low":
        return {
            "matched": False,
            "agent": top.agent,
            "skill": top.name if top.entry_type == "skill" else None,
            "confidence": "low",
            "match_type": "fallthrough",
            "reasoning": f"weak match on {top.matched_triggers!r} for {top.name} (score={top.score:.2f})",
        }

    # Determine agent and skill from the match
    agent = top.agent
    skill = top.name if top.entry_type == "skill" else None

    # If matched entry is an agent (not skill), set agent from name
    if top.entry_type == "agent":
        agent = top.name
        skill = None

    match_type = "force_route" if top.force_route else "trigger_keyword"
    triggers_str = ", ".join(f"'{t}'" for t in top.matched_triggers)

    return {
        "matched": True,
        "agent": agent,
        "skill": skill,
        "confidence": confidence,
        "match_type": match_type,
        "reasoning": f"matched triggers [{triggers_str}] for {top.name}",
    }


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Deterministic pre-router for /do dispatch.",
    )
    parser.add_argument(
        "--request",
        required=True,
        help="The user request string to route.",
    )
    parser.add_argument(
        "--json-compact",
        action="store_true",
        help="Output compact JSON (no indentation).",
    )
    args = parser.parse_args()

    result = route(args.request)

    indent = None if args.json_compact else 2
    print(json.dumps(result, indent=indent))
    return 0


if __name__ == "__main__":
    sys.exit(main())
