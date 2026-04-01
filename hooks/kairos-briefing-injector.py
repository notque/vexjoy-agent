#!/usr/bin/env python3
# hook-version: 1.0.0
"""
SessionStart Hook: KAIROS-lite Briefing Injector

Injects the most recent KAIROS monitoring briefing into session context.
Opt-in: requires CLAUDE_KAIROS_ENABLED=true environment variable.
Graceful degradation: always exits 0, never blocks session start.
"""

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import context_output, empty_output

EVENT_NAME = "SessionStart"
MAX_BRIEFING_AGE_HOURS = 24
MAX_INJECTION_CHARS = 1600  # ~400 tokens


def _debug(message: str) -> None:
    """Write debug message to stderr only when CLAUDE_HOOK_DEBUG is set."""
    if os.environ.get("CLAUDE_HOOK_DEBUG"):
        print(f"[kairos-briefing] {message}", file=sys.stderr)


def _find_most_recent_briefing(state_dir: Path) -> Path | None:
    """Return the most recently modified briefing-*.md file, or None."""
    try:
        candidates = list(state_dir.glob("briefing-*.md"))
    except OSError as e:
        _debug(f"Failed to glob {state_dir}: {e}")
        return None

    if not candidates:
        return None

    # Sort by mtime descending; pick first
    try:
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError as e:
        _debug(f"Failed to stat briefing candidates: {e}")
        return None

    return candidates[0]


def _extract_action_required(content: str) -> str:
    """Extract the '## Action Required' section from briefing content."""
    lines = content.splitlines()
    in_section = False
    collected: list[str] = []

    for line in lines:
        if line.strip() == "## Action Required":
            in_section = True
            collected.append(line)
            continue
        if in_section and line.startswith("##"):
            break
        if in_section:
            collected.append(line)

    return "\n".join(collected).strip()


def _write_sidecar(briefing_path: Path) -> None:
    """Write injection metadata sidecar file. Informational only — never raises."""
    try:
        session_id = os.environ.get("CLAUDE_SESSION_ID", "unknown")
        injected_at = datetime.now(timezone.utc).isoformat()
        sidecar_path = briefing_path.parent / (briefing_path.name + ".meta.json")

        import json

        payload = {"injected_at": injected_at, "session_id": session_id}
        # Atomic write: temp file then rename
        tmp_path = sidecar_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload))
        tmp_path.replace(sidecar_path)
    except Exception as e:
        _debug(f"Sidecar write failed (non-fatal): {e}")


def main() -> None:
    """Inject KAIROS briefing into session context if enabled and fresh."""
    try:
        # Opt-in gate
        if os.environ.get("CLAUDE_KAIROS_ENABLED", "").lower() != "true":
            _debug("CLAUDE_KAIROS_ENABLED not set; skipping")
            empty_output(EVENT_NAME).print_and_exit()
            return

        state_dir = Path.home() / ".claude" / "state"
        if not state_dir.is_dir():
            _debug(f"State directory not found: {state_dir}")
            empty_output(EVENT_NAME).print_and_exit()
            return

        briefing_path = _find_most_recent_briefing(state_dir)
        if briefing_path is None:
            _debug("No briefing files found")
            empty_output(EVENT_NAME).print_and_exit()
            return

        # Staleness check
        try:
            age_hours = (time.time() - briefing_path.stat().st_mtime) / 3600
        except OSError as e:
            _debug(f"Could not stat briefing file: {e}")
            empty_output(EVENT_NAME).print_and_exit()
            return

        if age_hours > MAX_BRIEFING_AGE_HOURS:
            _debug(f"Briefing too old ({age_hours:.1f}h > {MAX_BRIEFING_AGE_HOURS}h); skipping")
            empty_output(EVENT_NAME).print_and_exit()
            return

        # Read content
        try:
            content = briefing_path.read_text().strip()
        except OSError as e:
            _debug(f"Could not read briefing file: {e}")
            empty_output(EVENT_NAME).print_and_exit()
            return

        if not content:
            _debug("Briefing file is empty")
            empty_output(EVENT_NAME).print_and_exit()
            return

        # Truncate if needed, preferring the Action Required section
        if len(content) > MAX_INJECTION_CHARS:
            _debug(f"Content exceeds {MAX_INJECTION_CHARS} chars; extracting Action Required section")
            action_section = _extract_action_required(content)
            if action_section:
                content = action_section + f"\n\nFull briefing: {briefing_path}"
            else:
                content = content[:MAX_INJECTION_CHARS] + f"\n\nFull briefing: {briefing_path}"

        _debug(f"Injecting briefing from {briefing_path} (age={age_hours:.1f}h)")
        _write_sidecar(briefing_path)
        context_output(EVENT_NAME, f"<kairos-briefing>\n{content}\n</kairos-briefing>").print_and_exit()

    except Exception as e:
        _debug(f"Unexpected error: {type(e).__name__}: {e}")
        empty_output(EVENT_NAME).print_and_exit()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        if os.environ.get("CLAUDE_HOOK_DEBUG"):
            print(f"[kairos-briefing] Fatal: {type(e).__name__}: {e}", file=sys.stderr)
    finally:
        sys.exit(0)  # ALWAYS exit 0 — non-blocking requirement
