#!/usr/bin/env python3
"""
UserPromptSubmit Hook: Retro Knowledge Auto-Injection

Automatically injects accumulated L1/L2 knowledge from completed features
into agent context when the current task is structurally similar.

Benchmark results (7 trials):
- Win rate: 67% when retro knowledge is relevant
- Avg margin: +5.3 points (8-dimension rubric)
- Knowledge Transfer dimension: 5-0 win record
- Token efficiency: 23.5K vs 34.5K (retro agents use LESS context)

Key finding: Loading full SKILL.md hurts (-11 points), but compact L1/L2
retro summaries help (+5.3 avg). The relevance gate is critical — when
prior knowledge isn't structurally similar, overhead hurts (-10 JWT, -4 logging).

Design:
- L1 (~20 lines): Always loaded when ANY relevance detected (cheap)
- L2 (~50 lines each): Only loaded when tag-level similarity exceeds threshold
- Relevance gate: keyword matching between prompt and L2 tags
- Fast path: skip entirely for trivial prompts (< 5 words)
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

# Minimum tag matches to load an L2 file
L2_RELEVANCE_THRESHOLD = 2

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

# Language tags that indicate language-specific knowledge
LANGUAGE_TAGS = {"go", "golang", "python", "typescript", "javascript", "rust", "java"}

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
# Knowledge Store
# =============================================================================


def find_retro_dir() -> Path | None:
    """Find the retro knowledge directory.

    Searches in order:
    1. CLAUDE_RETRO_DIR env var (explicit override)
    2. agents/retro/ relative to this hook's location
    3. .feature/context/ in the project dir (active feature knowledge)
    """
    # Explicit override
    env_dir = os.environ.get("CLAUDE_RETRO_DIR")
    if env_dir:
        p = Path(env_dir)
        if p.is_dir():
            return p

    # Relative to hook location (agents/retro/)
    hook_dir = Path(__file__).resolve().parent.parent
    retro_dir = hook_dir / "retro"
    if retro_dir.is_dir():
        return retro_dir

    return None


def read_l1(retro_dir: Path) -> str | None:
    """Read L1 summary file. Returns content or None."""
    l1_file = retro_dir / "L1.md"
    if l1_file.is_file():
        try:
            content = l1_file.read_text().strip()
            if content:
                return content
        except OSError:
            pass
    return None


def read_l2_files(retro_dir: Path) -> list[dict]:
    """Read all L2 knowledge files with their tags.

    Returns list of dicts with keys: name, tags, content
    """
    l2_dir = retro_dir / "L2"
    if not l2_dir.is_dir():
        return []

    results = []
    try:
        for f in sorted(l2_dir.glob("*.md")):
            try:
                content = f.read_text().strip()
                if not content:
                    continue

                # Extract tags from **Tags**: line
                tags = set()
                for line in content.split("\n"):
                    if line.startswith("**Tags**:"):
                        tag_str = line.split(":", 1)[1].strip()
                        tags = {t.strip().lower() for t in tag_str.split(",")}
                        break

                results.append({
                    "name": f.stem,
                    "tags": tags,
                    "content": content,
                })
            except OSError:
                continue
    except OSError:
        pass

    return results


# =============================================================================
# Relevance Gate
# =============================================================================


def extract_prompt_keywords(prompt: str) -> set[str]:
    """Extract meaningful keywords from the prompt for relevance matching."""
    # Normalize and split
    words = set(re.findall(r"\b[a-z][a-z0-9_-]+\b", prompt.lower()))
    # Remove very common stop words
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "this", "that", "these", "those", "it", "its", "and", "or",
        "but", "not", "for", "with", "from", "into", "can", "will",
        "should", "would", "could", "have", "has", "had", "do", "does",
        "did", "to", "of", "in", "on", "at", "by", "as", "if", "so",
        "up", "out", "about", "all", "some", "any", "no", "my", "your",
        "we", "us", "our", "they", "them", "their", "me", "you", "he",
        "she", "him", "her", "also", "just", "like", "need", "want",
        "make", "new", "use", "using", "please", "let", "get",
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
    for pattern in SKIP_PREFIXES:
        if pattern.search(prompt):
            return True

    return False


def detect_project_languages() -> set[str]:
    """Detect primary language(s) of the current project from file extensions."""
    cwd = Path(os.environ.get("CLAUDE_WORKING_DIR", os.getcwd()))
    lang_map = {".go": "go", ".py": "python", ".ts": "typescript", ".js": "javascript", ".rs": "rust"}
    langs = set()
    for ext, lang in lang_map.items():
        # Check top-level and one level deep only (fast)
        if list(cwd.glob(f"*{ext}"))[:1] or list(cwd.glob(f"*/*{ext}"))[:1]:
            langs.add(lang)
    return langs


def score_l2_relevance(l2_tags: set[str], prompt_keywords: set[str], project_langs: set[str] | None = None) -> int:
    """Score how relevant an L2 file is to the current prompt.

    Returns number of matching tags, with penalty for cross-language matches.
    """
    if not l2_tags:
        return 0
    base_score = len(l2_tags & prompt_keywords)

    # Penalize cross-language matches
    if project_langs:
        l2_langs = l2_tags & LANGUAGE_TAGS
        if l2_langs and not (l2_langs & project_langs):
            base_score -= 1  # Language mismatch penalty

    return base_score


# =============================================================================
# Injection Builder
# =============================================================================


def strip_graduated_entries(content: str) -> str:
    """Remove ### entries marked as [GRADUATED] from L2 content.

    Graduated entries have been embedded into specific agents/skills
    and should not be re-injected via the broad hook.
    """
    # Remove entire sections from ### heading with [GRADUATED] to next ### or EOF
    return re.sub(
        r"^### .+\[GRADUATED[^\]]*\].*?(?=\n### |\Z)",
        "",
        content,
        flags=re.MULTILINE | re.DOTALL,
    ).strip()


def build_injection(l1_content: str, relevant_l2: list[dict]) -> str:
    """Build the context injection string."""
    parts = [
        "<retro-knowledge>",
        "**Accumulated knowledge from prior features.** Use these patterns where applicable.",
        "Adapt, don't copy. Note where patterns do NOT apply to the current task.",
        "",
        l1_content,
    ]

    if relevant_l2:
        parts.append("")
        parts.append("---")
        parts.append("")
        parts.append("## Detailed Learnings (from structurally similar features)")
        for l2 in relevant_l2:
            # Filter out graduated entries (already embedded in agents)
            filtered_content = strip_graduated_entries(l2["content"])
            if filtered_content:
                parts.append("")
                parts.append(filtered_content)

    parts.append("")
    parts.append("</retro-knowledge>")

    return "\n".join(parts)


# =============================================================================
# SQLite-based injection (learning_db_v2)
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

        # PRIMARY: Try SQLite-based injection first
        db_injection = query_knowledge_from_db(prompt_keywords, debug=bool(debug), agent_type=agent_type)
        if db_injection:
            context_output(EVENT_NAME, db_injection).print_and_exit()

        # FALLBACK: File-based injection (original behavior)
        retro_dir = find_retro_dir()
        if not retro_dir:
            if debug:
                print("[retro] Skipped: no retro/ directory and no DB results", file=sys.stderr)
            empty_output(EVENT_NAME).print_and_exit()

        # Read L1
        l1_content = read_l1(retro_dir)
        if not l1_content:
            if debug:
                print("[retro] Skipped: no L1 content", file=sys.stderr)
            empty_output(EVENT_NAME).print_and_exit()

        # Read and filter L2 by relevance
        project_langs = detect_project_languages()
        l2_files = read_l2_files(retro_dir)
        relevant_l2 = []
        for l2 in l2_files:
            score = score_l2_relevance(l2["tags"], prompt_keywords, project_langs)
            if score >= L2_RELEVANCE_THRESHOLD:
                relevant_l2.append({**l2, "score": score})
                if debug:
                    print(f"[retro] L2 relevant: {l2['name']} (score={score}, tags={l2['tags'] & prompt_keywords})", file=sys.stderr)
            elif debug:
                print(f"[retro] L2 skipped: {l2['name']} (score={score})", file=sys.stderr)

        # Sort by relevance score (highest first)
        relevant_l2 = sorted(relevant_l2, key=lambda x: x.get("score", 0), reverse=True)

        # Build and inject
        injection = build_injection(l1_content, relevant_l2)

        if debug:
            l2_names = [l2["name"] for l2 in relevant_l2]
            print(f"[retro] Injecting L1 + {len(relevant_l2)} L2 files: {l2_names}", file=sys.stderr)

        context_output(EVENT_NAME, injection).print_and_exit()

    except Exception as e:
        if debug:
            print(f"[retro] Error: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
        else:
            print(f"[retro] Error: {type(e).__name__}: {e}", file=sys.stderr)
        empty_output(EVENT_NAME).print_and_exit()


if __name__ == "__main__":
    main()
