#!/usr/bin/env python3
# hook-version: 2.0.0
"""PreCompact Hook: Jev Compaction Evidence

Fires before context compression in both main sessions and subagents.
Loads the session transcript from the event's ``transcript_path`` (JSONL),
runs jev-compact.py to compute per-tool-call keep/drop decisions using Jev,
and records the result as a `compaction_events` row in learning.db. A row
is written even when Jev is skipped (short transcript, import failure),
so every compaction leaves evidence.

PreCompact accepts no context injection: the built-in compactor never reads
this hook's stdout. The priority-labeled guidance below is printed only
where transcript mode shows hook stdout to the user.

Design:
  - Non-blocking: always exits 0
  - Fail-open: any error silently falls through to built-in compaction
  - Uses jev-compact.py as a library (import, not subprocess)
  - Reports stats to stderr, records evidence to learning.db
  - Works in main sessions AND subagents (unlike function-hook plugins)

Output format — priority labels shown in transcript mode:
  CRITICAL KEEP: tool calls whose results are still referenced
  SAFE TO DROP: exploratory reads, listings, superseded calls
  TRUNCATE RESULT: keep the call, drop the output (reproducible)
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import hook_error
from stdin_timeout import read_stdin

# Import jev-compact as a module
_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"


def _import_compact():
    """Import jev-compact.py as a module."""
    if str(_SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS_DIR))
    import importlib.util

    spec = importlib.util.spec_from_file_location("jev_compact", _SCRIPTS_DIR / "jev-compact.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _record_evidence(event: dict, stats: dict, messages_count: int, engine: str = "guidance") -> None:
    """Write this hook's row to learning.db, then ingest the plugin's JSONL
    claims and this session's compact_boundary rows so the engine's own
    record sits next to every claim. Best-effort. `engine` is "guidance"
    when Jev ran and "skipped" when it did not."""
    try:
        from datetime import datetime, timezone

        import learning_db_v2 as ldb

        session_id = event.get("session_id") or os.environ.get("CLAUDE_SESSION_ID") or "unknown"
        ldb.record_compaction_event(
            session_id=session_id,
            ts=datetime.now(timezone.utc).isoformat(),
            source="precompact-hook",
            trigger=event.get("trigger"),
            engine=engine,
            agent_id=event.get("agent_id"),
            messages_before=messages_count,
            reduction_ratio=stats.get("reduction_ratio"),
            dropped_calls=stats.get("dropped_call"),
            truncated_results=stats.get("dropped_result"),
            pinned=stats.get("pinned"),
            prefiltered=stats.get("prefiltered"),
            jev_judged=stats.get("jev_judged"),
            jev_api_calls=stats.get("jev_calls"),
            latency_ms=stats.get("latency_ms"),
        )
    except Exception as e:
        print(f"[jev-compact-hook] evidence write failed: {e}", file=sys.stderr)

    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("jev_compact_evidence", _SCRIPTS_DIR / "jev-compact-evidence.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        transcript = event.get("transcript_path")
        mod.ingest_all(Path(transcript) if transcript else None)
    except Exception as e:
        print(f"[jev-compact-hook] evidence ingest failed: {e}", file=sys.stderr)


MIN_MESSAGES = 10


def _load_messages(event: dict, jev_compact) -> list[dict]:
    """Messages for compact(): the real PreCompact payload carries
    `transcript_path` (JSONL); an inline `messages`/`transcript` list is the
    fallback for synthetic events."""
    transcript = event.get("transcript_path")
    if isinstance(transcript, str) and transcript:
        try:
            messages = jev_compact.load_transcript_jsonl(transcript)
        except Exception as e:
            print(f"[jev-compact-hook] transcript load failed: {e}", file=sys.stderr)
            messages = []
        if messages:
            return messages
    messages = event.get("messages") or event.get("transcript") or []
    return messages if isinstance(messages, list) else []


def run_compact_guidance(event: dict) -> None:
    """Run Jev compaction analysis, record evidence, print guidance."""
    try:
        jev_compact = _import_compact()
    except Exception as e:
        print(f"[jev-compact-hook] import failed: {e}", file=sys.stderr)
        _record_evidence(event, {}, 0, engine="skipped")
        return

    messages = _load_messages(event, jev_compact)
    if not messages:
        print("[jev-compact-hook] no messages in event", file=sys.stderr)
        _record_evidence(event, {}, 0, engine="skipped")
        return

    if len(messages) < MIN_MESSAGES:
        _record_evidence(event, {}, len(messages), engine="skipped")
        return

    try:
        result = jev_compact.compact(messages, timeout=8.0)
    except Exception as e:
        print(f"[jev-compact-hook] compaction failed: {e}", file=sys.stderr)
        _record_evidence(event, {}, len(messages), engine="error")
        return

    stats = result.get("stats", {})

    if stats.get("error"):
        print(f"[jev-compact-hook] error: {stats['error']}", file=sys.stderr)
        _record_evidence(event, stats, len(messages), engine="error")
        return

    total = stats.get("total_calls", 0)
    if total == 0:
        _record_evidence(event, stats, len(messages), engine="skipped")
        return

    kept = stats.get("kept", 0)
    dropped_result = stats.get("dropped_result", 0)
    dropped_call = stats.get("dropped_call", 0)
    ratio = stats.get("reduction_ratio", 0)
    latency = stats.get("latency_ms", 0)
    jev_calls = stats.get("jev_calls", 0)

    print(
        f"[jev-compact-hook] {total} calls: {kept} keep, {dropped_result} truncate, "
        f"{dropped_call} drop | ratio={ratio:.1%} | {latency:.0f}ms ({jev_calls} Jev calls)",
        file=sys.stderr,
    )
    _record_evidence(event, stats, len(messages))

    decisions = result.get("decisions", {})
    if not decisions:
        return

    # Build priority-labeled guidance
    lines = [
        "[jev-compact] Jev-computed compaction guidance (verbatim pruning, zero generation):",
        f"  Total tool calls: {total} | Keep: {kept} | Truncate: {dropped_result} | Drop: {dropped_call}",
        f"  Estimated context reduction: {ratio:.1%}",
        "",
    ]

    # Group by priority label with confidence details
    critical_keeps = []
    safe_drops = []
    truncates = []
    normal_keeps = []

    for seq_id, decision in sorted(decisions.items()):
        action = decision["action"]
        reason = decision.get("reason", "")
        keep_result = decision.get("keep_result", 0)
        referenced = decision.get("referenced", 0)

        if action == "keep" and reason == "pinned":
            critical_keeps.append(f"{seq_id} (pinned)")
        elif action == "keep" and referenced >= 0.6:
            critical_keeps.append(f"{seq_id} (ref={referenced:.2f})")
        elif action == "keep" and keep_result >= 0.7:
            critical_keeps.append(f"{seq_id} (keep={keep_result:.2f})")
        elif action == "keep":
            normal_keeps.append(seq_id)
        elif action == "drop_call":
            safe_drops.append(f"{seq_id} ({reason})")
        elif action == "drop_result":
            truncates.append(f"{seq_id} (keep call, drop {decision.get('keep_result', 0):.2f})")

    if critical_keeps:
        lines.append(f"  CRITICAL KEEP (referenced or high-value): {', '.join(critical_keeps[:25])}")
    if normal_keeps:
        lines.append(f"  KEEP: {', '.join(normal_keeps[:25])}")
    if truncates:
        lines.append(f"  TRUNCATE RESULT (keep call, drop output): {', '.join(truncates[:25])}")
    if safe_drops:
        lines.append(f"  SAFE TO DROP (exploratory, superseded, reproducible): {', '.join(safe_drops[:25])}")

    lines.extend(
        [
            "",
            "  Instructions for compaction:",
            "  - Preserve CRITICAL KEEP tool results verbatim — they are still referenced.",
            "  - For TRUNCATE RESULT entries: keep the tool call and its input, discard the output.",
            "  - SAFE TO DROP entries can be removed entirely (call + result).",
            "  - When space is tight, prefer dropping exploratory reads and listings first.",
            "  - Edit/Write tool results are harder to reproduce — keep them unless marked SAFE TO DROP.",
        ]
    )

    guidance = "\n".join(lines)
    print(guidance)


def main():
    """Run Jev compaction guidance before context compression."""
    try:
        event_data = read_stdin(timeout=5)
        if not event_data:
            return

        event = json.loads(event_data)

        event_type = event.get("hook_event_name") or event.get("type", "")
        if event_type != "PreCompact":
            return

        run_compact_guidance(event)

    except json.JSONDecodeError as e:
        hook_error("jev-compact-precompact", e)
    except Exception as e:
        hook_error("jev-compact-precompact", e)
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()
