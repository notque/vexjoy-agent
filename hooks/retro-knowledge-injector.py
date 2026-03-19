#!/usr/bin/env python3
"""
UserPromptSubmit Hook: Retro Knowledge Auto-Injection

Queries learning.db (SQLite + FTS5) for relevant accumulated knowledge
and injects it into agent context for cross-feature learning.

Benchmark results (7 trials):
- Win rate: 67% when retro knowledge is relevant
- Avg margin: +5.3 points (8-dimension rubric)
- Knowledge Transfer dimension: 5-0 win record
- Token efficiency: 23.5K vs 34.5K (retro agents use LESS context)

Design:
- Single source: learning.db via FTS5 search
- Relevance gate: keyword matching + work-intent detection
- Fast path: skip entirely for trivial prompts (< 5 words)
- Token budget: ~2000 tokens per injection
"""

import json
import os
import re
import sys
import traceback
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import context_output, empty_output

# Try to import learning_db_v2 for SQLite-based injection
try:
    from learning_db_v2 import search_learnings as _search_db

    _HAS_LEARNING_DB = True
except ImportError:
    _HAS_LEARNING_DB = False

# =============================================================================
# Configuration
# =============================================================================

EVENT_NAME = "UserPromptSubmit"

# Minimum prompt length to consider for retro injection (skip trivial)
MIN_PROMPT_WORDS = 4

# Tags that indicate code/design/plan work (trigger retro consideration)
WORK_INDICATORS = {
    "implement",
    "build",
    "create",
    "design",
    "plan",
    "add",
    "feature",
    "middleware",
    "service",
    "api",
    "handler",
    "endpoint",
    "refactor",
    "architecture",
}

# Prompts starting with these are trivial (skip retro)
SKIP_PREFIXES = [
    re.compile(r"^(what|how|show|read|cat|ls|git|explain|help)\b", re.IGNORECASE),
    # Note: slash commands no longer skipped here. The work-intent filter
    # (has_work_intent) gates injection for trivial commands. Substantive
    # slash commands like /pr-review and /comprehensive-review should receive
    # retro knowledge. Only /do had its own injection — all others were silently
    # missing retro context.
]

# =============================================================================
# Relevance Gate
# =============================================================================


def extract_prompt_keywords(prompt: str) -> set[str]:
    """Extract meaningful keywords from the prompt for relevance matching."""
    # Normalize and split — exclude hyphens from token chars because
    # FTS5 interprets '-' as NOT operator, so 'force-route' would become
    # 'force NOT route' and poison the entire OR query
    words = set(re.findall(r"\b[a-z][a-z0-9_]+\b", prompt.lower()))
    # Remove very common stop words
    stop_words = {
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "and",
        "or",
        "but",
        "not",
        "for",
        "with",
        "from",
        "into",
        "can",
        "will",
        "should",
        "would",
        "could",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "to",
        "of",
        "in",
        "on",
        "at",
        "by",
        "as",
        "if",
        "so",
        "up",
        "out",
        "about",
        "all",
        "some",
        "any",
        "no",
        "my",
        "your",
        "we",
        "us",
        "our",
        "they",
        "them",
        "their",
        "me",
        "you",
        "he",
        "she",
        "him",
        "her",
        "also",
        "just",
        "like",
        "need",
        "want",
        "make",
        "new",
        "use",
        "using",
        "please",
        "let",
        "get",
    }
    return words - stop_words


def has_work_intent(prompt_keywords: set[str]) -> bool:
    """Check if the prompt indicates substantive work (not just questions/reads)."""
    return bool(prompt_keywords & WORK_INDICATORS)


def is_trivial(prompt: str) -> bool:
    """Check if prompt is trivial and should skip retro injection."""
    # Too short
    if len(prompt.split()) < MIN_PROMPT_WORDS:
        return True

    # Starts with trivial prefix
    return any(pattern.search(prompt) for pattern in SKIP_PREFIXES)


# =============================================================================
# Knowledge Injection (learning_db_v2)
# =============================================================================


def _agent_type_tags(agent_type: str) -> set[str]:
    """Derive search tags from agent_type name for relevance boosting.

    Maps agent names like 'golang-general-engineer' to language tags
    that improve knowledge retrieval specificity.
    """
    if not agent_type:
        return set()

    agent_lower = agent_type.lower()
    tag_map = {
        "go": {"go", "golang"},
        "python": {"python"},
        "typescript": {"typescript", "javascript"},
        "javascript": {"javascript"},
        "rust": {"rust"},
        "java": {"java"},
        "kubernetes": {"kubernetes", "k8s", "helm"},
        "react": {"react", "typescript", "frontend"},
    }

    tags: set[str] = set()
    for keyword, derived_tags in tag_map.items():
        if keyword in agent_lower:
            tags.update(derived_tags)
    return tags


def query_knowledge_from_db(prompt_keywords: set[str], debug: bool = False, agent_type: str = "") -> str | None:
    """Query learning.db for relevant knowledge. Returns injection string or None."""
    if not _HAS_LEARNING_DB:
        return None

    try:
        # Enrich search tags with agent-type-derived tags
        search_tags = set(prompt_keywords)
        agent_tags = _agent_type_tags(agent_type)
        search_tags.update(agent_tags)

        # Build FTS5 query: OR-join top tags for broad matching with stemming
        query_str = " OR ".join(list(search_tags)[:10])
        results = _search_db(
            query_str,
            min_confidence=0.5,
            exclude_graduated=True,
            limit=15,
        )

        if not results:
            if debug:
                print("[retro] DB query: no results", file=sys.stderr)
            return None

        # Token budget: ~2000 tokens ≈ 8000 chars
        TOKEN_BUDGET_CHARS = 8000
        chars_used = 0

        parts = [
            "<retro-knowledge>",
            "**Accumulated knowledge from prior features.** Use these patterns where applicable.",
            "Adapt, don't copy. Note where patterns do NOT apply to the current task.",
            "",
        ]

        selected = []
        for r in results:
            entry_chars = len(r["value"]) + 80  # overhead for heading
            if chars_used + entry_chars > TOKEN_BUDGET_CHARS:
                break
            selected.append(r)
            chars_used += entry_chars

        if not selected:
            return None

        # Group by topic for readability
        by_topic: dict[str, list[dict]] = {}
        for r in selected:
            t = r["topic"]
            if t not in by_topic:
                by_topic[t] = []
            by_topic[t].append(r)

        for topic, entries in by_topic.items():
            heading = topic.replace("-", " ").title() + " Patterns"
            parts.append(f"## {heading}")
            for e in entries:
                obs = f" [{e['observation_count']}x]" if e["observation_count"] > 1 else ""
                first_line = e["value"].split("\n")[0][:150]
                parts.append(f"- {e['key']}{obs}: {first_line}")
            parts.append("")

        parts.append("</retro-knowledge>")

        if debug:
            print(f"[retro] DB: injecting {len(selected)} entries from {len(by_topic)} topics", file=sys.stderr)

        return "\n".join(parts)
    except Exception as e:
        if debug:
            print(f"[retro] DB query error: {e}", file=sys.stderr)
        return None


# =============================================================================
# Main
# =============================================================================


def main():
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    try:
        # Parse hook input
        try:
            hook_input = json.load(sys.stdin)
            if not isinstance(hook_input, dict):
                empty_output(EVENT_NAME).print_and_exit()
            prompt = hook_input.get("prompt", "").strip()
            agent_type = hook_input.get("agent_type", "")
        except json.JSONDecodeError:
            empty_output(EVENT_NAME).print_and_exit()

        if not prompt:
            empty_output(EVENT_NAME).print_and_exit()

        # Fast path: skip trivial prompts
        if is_trivial(prompt):
            if debug:
                print("[retro] Skipped: trivial prompt", file=sys.stderr)
            empty_output(EVENT_NAME).print_and_exit()

        # Extract prompt keywords for relevance matching
        prompt_keywords = extract_prompt_keywords(prompt)

        # Check work intent — only inject for substantive tasks
        if not has_work_intent(prompt_keywords):
            if debug:
                print(f"[retro] Skipped: no work intent in keywords {prompt_keywords}", file=sys.stderr)
            empty_output(EVENT_NAME).print_and_exit()

        # Query learning.db for relevant knowledge
        db_injection = query_knowledge_from_db(prompt_keywords, debug=bool(debug), agent_type=agent_type)
        if db_injection:
            context_output(EVENT_NAME, db_injection).print_and_exit()

        if debug:
            print("[retro] Skipped: no DB results for prompt keywords", file=sys.stderr)
        empty_output(EVENT_NAME).print_and_exit()

    except Exception as e:
        if debug:
            print(f"[retro] Error: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
        else:
            print(f"[retro] Error: {type(e).__name__}: {e}", file=sys.stderr)
        empty_output(EVENT_NAME).print_and_exit()


if __name__ == "__main__":
    main()
