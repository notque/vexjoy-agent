#!/usr/bin/env python3
# hook-version: 2.0.0
"""
SessionStart Hook: Retro Knowledge Auto-Injection

Fires ONCE per session. Queries learning.db for the top N highest-confidence
patterns and injects them into agent context for cross-feature learning.

Design:
- Fires once at SessionStart — injected content is static and cache-stable
- No prompt keyword matching (no prompt exists at SessionStart)
- Selection: top 20 entries by confidence DESC, last_seen DESC as tiebreak
- Token budget: ~2000 tokens (~8000 chars) to stay cache-friendly
- Noise topics filtered (worktree-branches telemetry, etc.)
- Output: same <retro-knowledge> block format as before

Benchmark results (from UserPromptSubmit era, still valid):
- Win rate: 67% when retro knowledge is relevant
- Avg margin: +5.3 points (8-dimension rubric)
- Knowledge Transfer dimension: 5-0 win record
- Token efficiency: 23.5K vs 34.5K (retro agents use LESS context)
"""

import json
import os
import sys
import traceback
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import context_output, empty_output, get_session_id
from stdin_timeout import read_stdin

# Try to import learning_db_v2 for SQLite-based injection
try:
    from learning_db_v2 import query_learnings as _query_learnings
    from learning_db_v2 import sanitize_for_context as _sanitize_for_context

    _HAS_LEARNING_DB = True
except ImportError:
    _HAS_LEARNING_DB = False

# =============================================================================
# Configuration
# =============================================================================

EVENT_NAME = "SessionStart"

# Maximum entries to select from learning.db
TOP_N = 20

# Token budget: ~2000 tokens ≈ 8000 chars
TOKEN_BUDGET_CHARS = 8000

# Topics to filter out as low-signal noise
NOISE_TOPICS = {"worktree-branches"}

# Minimum confidence to include an entry
MIN_CONFIDENCE = 0.55


# =============================================================================
# Knowledge Query
# =============================================================================


def query_top_patterns(debug: bool = False) -> str | None:
    """Query the top N highest-confidence patterns from learning.db.

    Uses confidence DESC as primary sort and last_seen DESC as tiebreak so
    recently-updated entries appear first among equals. No FTS5 / no prompt
    required — results are fully deterministic for cache stability.

    Returns the <retro-knowledge> injection string, or None if nothing useful.
    """
    if not _HAS_LEARNING_DB:
        return None

    try:
        results = _query_learnings(
            min_confidence=MIN_CONFIDENCE,
            exclude_graduated=True,
            order_by="confidence DESC",
            limit=TOP_N,
        )

        if not results:
            if debug:
                print("[retro] No results above confidence threshold", file=sys.stderr)
            return None

        # Filter noise topics
        results = [r for r in results if r.get("topic") not in NOISE_TOPICS]

        if not results:
            if debug:
                print("[retro] All results filtered as noise", file=sys.stderr)
            return None

        parts = [
            "<retro-knowledge>",
            "**Accumulated knowledge from prior features.** Use these patterns where applicable.",
            "Adapt, don't copy. Note where patterns do NOT apply to the current task.",
            "",
        ]

        chars_used = 0
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
                first_line = _sanitize_for_context(e["value"]).split("\n")[0][:150]
                parts.append(f"- {e['key']}{obs}: {first_line}")
            parts.append("")

        parts.append("</retro-knowledge>")

        if debug:
            print(
                f"[retro] Injecting {len(selected)} entries from {len(by_topic)} topics",
                file=sys.stderr,
            )

        return "\n".join(parts)

    except Exception as e:
        if debug:
            print(f"[retro] Query error: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
        return None


# =============================================================================
# Main
# =============================================================================


def main():
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    try:
        # Parse hook input (SessionStart sends minimal JSON — just consume it)
        try:
            raw = read_stdin(timeout=2)
            hook_input = json.loads(raw) if raw.strip() else {}
            if not isinstance(hook_input, dict):
                hook_input = {}
        except (json.JSONDecodeError, Exception):
            hook_input = {}

        # Query top patterns — no prompt needed
        injection = query_top_patterns(debug=bool(debug))

        if injection:
            # Set marker for record-activation.py ROI tracking (ADR-032)
            try:
                session_id = get_session_id()
                marker = Path("/tmp") / f"claude-retro-active-{session_id}"
                marker.write_text("1")
            except OSError:
                pass  # Non-critical — don't block injection
            context_output(EVENT_NAME, injection).print_and_exit()

        if debug:
            print("[retro] Skipped: no patterns above threshold", file=sys.stderr)
        empty_output(EVENT_NAME).print_and_exit()

    except Exception as e:
        if debug:
            print(f"[retro] Error: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
        else:
            print(f"[retro] Error: {type(e).__name__}: {e}", file=sys.stderr)
        empty_output(EVENT_NAME).print_and_exit()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[retro] Fatal: {type(e).__name__}: {e}", file=sys.stderr)
    finally:
        sys.exit(0)  # ALWAYS exit 0 — non-blocking requirement
