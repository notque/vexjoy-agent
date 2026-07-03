#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PreToolUse:Write Hook: Voice Pipeline Publish Gate

Blocks publishing VexJoy blog posts (draft: false) unless all 13 phases
of the voice-writer pipeline have been completed.

Detection logic:
- Tool is Write (enforced by matcher in settings.json)
- Target path matches content/posts/*.md
- Content sets draft: false

Allow-through conditions:
- File is NOT in content/posts/
- Content has draft: true (still in progress)
- All 13 pipeline phases are complete
- VOICE_GATE_BYPASS=1 env var set

Follows pretool-plan-gate.py pattern exactly.
"""

import json
import os
import re
import subprocess
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import deny_tool_use, hook_error
from stdin_timeout import read_stdin

_BYPASS_ENV = "VOICE_GATE_BYPASS"
_TRACKER = str(Path(__file__).parent / "voice-pipeline-tracker.py")


def _extract_slug(file_path: str) -> str:
    """Extract slug from blog post filename, stripping date prefix and .md suffix.

    Example: content/posts/2025-12-29-my-post.md -> my-post
    """
    name = Path(file_path).stem  # strip .md
    # Strip YYYY-MM-DD- prefix if present
    return re.sub(r"^\d{4}-\d{2}-\d{2}-", "", name)


def _is_blog_post(file_path: str) -> bool:
    """Return True if path is a blog post in content/posts/."""
    normalised = file_path.replace("\\", "/")
    return "content/posts/" in normalised and normalised.endswith(".md")


def _has_draft_false(content: str) -> bool:
    """Return True if content sets draft: false in frontmatter."""
    # Match draft: false in YAML frontmatter
    return bool(re.search(r"^draft:\s*false\s*$", content, re.MULTILINE))


def _check_pipeline(slug: str) -> dict:
    """Query the voice pipeline tracker for status. Returns parsed JSON or None."""
    try:
        result = subprocess.run(
            [sys.executable, _TRACKER, "status", slug],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass
    return None


def main() -> None:
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    raw = read_stdin(timeout=2)
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    # Bypass env var
    if os.environ.get(_BYPASS_ENV) == "1":
        if debug:
            print(f"[voice-publish-gate] Bypassed via {_BYPASS_ENV}=1", file=sys.stderr)
        sys.exit(0)

    tool_input = event.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    # Only gate blog posts
    if not _is_blog_post(file_path):
        if debug:
            print(f"[voice-publish-gate] Not a blog post, allowing: {file_path}", file=sys.stderr)
        sys.exit(0)

    content = tool_input.get("content", "")

    # Draft: true means still in progress — allow through
    if not _has_draft_false(content):
        if debug:
            print("[voice-publish-gate] draft: true or no draft field, allowing", file=sys.stderr)
        sys.exit(0)

    # draft: false — check pipeline completion
    slug = _extract_slug(file_path)
    if debug:
        print(f"[voice-publish-gate] Checking pipeline for slug: {slug}", file=sys.stderr)

    status = _check_pipeline(slug)

    # If tracker fails, fail open
    if status is None:
        if debug:
            print("[voice-publish-gate] Tracker query failed, failing open", file=sys.stderr)
        sys.exit(0)

    if status.get("ready_to_publish", False):
        if debug:
            print(f"[voice-publish-gate] All phases complete for '{slug}', allowing", file=sys.stderr)
        sys.exit(0)

    # Phases missing — block publication
    missing = status.get("phases_missing", [])
    complete = status.get("phases_complete", [])

    reason = (
        f"Voice pipeline incomplete for '{slug}'. "
        f"{len(complete)}/13 phases done. "
        f"Missing: {', '.join(missing)}. "
        f"Complete all phases or set VOICE_GATE_BYPASS=1 to override."
    )

    print(f"[voice-publish-gate] BLOCKED: {reason}", file=sys.stderr)
    deny_tool_use("PreToolUse", reason)
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        hook_error("pretool-voice-publish-gate", e)
    finally:
        sys.exit(0)
