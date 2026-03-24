#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PreCompact Hook: Learning Archive

Fires before context compression to extract and archive key learnings
from the current session. Ensures important patterns are preserved
before context is compacted.

Design Principles:
- Extract actionable patterns from session
- Archive to unified learning database (learning_db_v2)
- Identify successful error resolutions
- Update confidence scores for applied patterns
- Non-blocking (always exits 0)

Context Compression Events:
This hook fires when Claude's context window is getting full and needs
to be compressed. We use this opportunity to archive any learnings before
they are lost to compression.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from learning_db_v2 import classify_error, generate_signature, get_stats, record_learning
from stdin_timeout import read_stdin


def inject_adr_anchor(event: dict) -> None:
    """
    Detect active pipeline session and inject ADR survival anchor.

    Looks for .adr-session.json in the project cwd. If found, prints
    a recovery anchor so agents waking up post-compaction know where
    to re-read the ADR, what hash to verify, and what commands to run.
    """
    try:
        # Determine project root: prefer cwd from event, then env var, then os.getcwd()
        cwd = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
        session_file = Path(cwd) / ".adr-session.json"

        if not session_file.exists():
            return

        with open(session_file, "r") as f:
            session = json.load(f)

        adr_path = session.get("adr_path", "")
        adr_hash = session.get("adr_hash", "")
        domain = session.get("domain", "")
        registered_at = session.get("registered_at", "")

        if not adr_path:
            return

        print("[precompact-adr] ==========================================")
        print("[precompact-adr] ACTIVE PIPELINE SESSION — ADR ANCHOR")
        print("[precompact-adr] ==========================================")
        print(f"[precompact-adr] Pipeline domain: {domain}")
        print(f"[precompact-adr] ADR location: {adr_path}")
        print(f"[precompact-adr] ADR hash: {adr_hash}")
        print(f"[precompact-adr] Registered at: {registered_at}")
        print("[precompact-adr]")
        print("[precompact-adr] RECOVERY AFTER COMPACTION:")
        print(f"[precompact-adr]   1. Read this ADR: {adr_path}")
        print(
            f"[precompact-adr]   2. Verify hash:  python3 ~/.claude/scripts/adr-query.py verify --adr {adr_path} --hash {adr_hash}"
        )
        print(
            f"[precompact-adr]   3. Get your context: python3 ~/.claude/scripts/adr-query.py context --adr {adr_path} --role orchestrator"
        )
        print("[precompact-adr]")
        print("[precompact-adr] COMPLIANCE CHECK FOR ANY COMPONENT FILE:")
        print("[precompact-adr]   python3 ~/.claude/scripts/adr-compliance.py check --file {file} \\")
        print("[precompact-adr]     --step-menu ~/.claude/skills/pipeline-scaffolder/references/step-menu.md \\")
        print(
            "[precompact-adr]     --spec-format ~/.claude/skills/pipeline-scaffolder/references/pipeline-spec-format.md"
        )
        print("[precompact-adr] ==========================================")

    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            import traceback

            print(f"[precompact-archive] HOOK-ERROR: {type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)


def extract_error_resolutions(event: dict) -> list[dict]:
    """
    Extract error resolution patterns from the session being compacted.

    Looks for sequences like:
    1. Error occurred
    2. Action taken
    3. Error resolved

    Returns:
        List of resolution patterns to archive
    """
    resolutions = []

    # This is a simplified extraction - in practice, we'd analyze
    # the conversation history more deeply
    conversation = event.get("conversation_history", [])

    # Look for error messages followed by successful actions
    for i, turn in enumerate(conversation):
        content = turn.get("content", "")

        # Look for error indicators
        if any(indicator in content.lower() for indicator in ["error:", "failed", "exception"]):
            # Check if there was a successful resolution afterward
            if i + 2 < len(conversation):
                resolution_turn = conversation[i + 2]
                if "success" in resolution_turn.get("content", "").lower():
                    resolutions.append(
                        {
                            "error_context": content[:500],
                            "resolution": resolution_turn.get("content", "")[:500],
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    )

    return resolutions


def summarize_session_learnings(event: dict) -> dict:
    """
    Summarize what will be preserved from this session.

    Returns:
        Summary dictionary with counts and categories
    """
    summary = {
        "patterns_updated": 0,
        "new_patterns": 0,
        "high_confidence_applied": 0,
        "error_types_seen": set(),
    }

    # Count patterns that were referenced in this session
    conversation = event.get("conversation_history", [])
    for turn in conversation:
        content = str(turn.get("content", ""))

        # Look for learned solution applications
        if "[learned-solution]" in content:
            summary["high_confidence_applied"] += 1

        # Extract error types mentioned
        for error_type in [
            "missing_file",
            "permissions",
            "syntax_error",
            "import_error",
            "type_error",
            "timeout",
            "connection",
            "memory",
        ]:
            if error_type in content.lower():
                summary["error_types_seen"].add(error_type)

    return summary


def main():
    """Archive learnings before context compression."""
    try:
        # Read event data from stdin
        event_data = read_stdin(timeout=2)
        if not event_data:
            return

        event = json.loads(event_data)

        # Only process PreCompact events
        event_type = event.get("hook_event_name") or event.get("type", "")
        if event_type != "PreCompact":
            return

        # Inject ADR survival anchor before archiving learnings
        inject_adr_anchor(event)

        # Extract error resolutions from session
        resolutions = extract_error_resolutions(event)

        # Archive each resolution as a pattern
        cwd = event.get("cwd", str(Path.cwd()))
        new_patterns = 0

        for resolution in resolutions:
            error_msg = resolution["error_context"]
            error_type = classify_error(error_msg)
            signature = generate_signature(error_msg, error_type)
            value = error_msg[:200]
            if resolution["resolution"]:
                value += f" → {resolution['resolution'][:200]}"
            result = record_learning(
                topic=error_type,
                key=signature,
                value=value,
                category="error",
                source="precompact-archive",
                project_path=cwd,
                error_signature=signature,
                error_type=error_type,
            )
            if result.get("is_new"):
                new_patterns += 1

        # Summarize what we're preserving
        summary = summarize_session_learnings(event)
        summary["new_patterns"] = new_patterns

        # Get overall stats
        stats = get_stats()

        # Only print if we found meaningful learnings
        if new_patterns > 0 or summary["high_confidence_applied"] > 0:
            print("[learning-archive] Preserving session learnings before compression")

            if new_patterns > 0:
                print(f"[learning-archive]   New patterns: {new_patterns}")

            if summary["high_confidence_applied"] > 0:
                print(f"[learning-archive]   High-confidence solutions applied: {summary['high_confidence_applied']}")

            if summary["error_types_seen"]:
                error_types = ", ".join(sorted(summary["error_types_seen"]))
                print(f"[learning-archive]   Error types: {error_types}")

            # Show overall learning stats
            total = stats.get("total_learnings", 0)
            high_conf = stats.get("high_confidence", 0)
            if total > 0:
                print(f"[learning-archive]   Total learnings: {high_conf}/{total} high-confidence")

    except json.JSONDecodeError as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            import traceback

            print(f"[precompact-archive] HOOK-ERROR: {type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
    except Exception as e:
        # Log to stderr if debug enabled, but never fail
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            import traceback

            print(f"[precompact-archive] HOOK-ERROR: {type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
    finally:
        # CRITICAL: Always exit 0 to prevent blocking Claude Code
        sys.exit(0)


if __name__ == "__main__":
    main()
