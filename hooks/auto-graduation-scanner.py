#!/usr/bin/env python3
"""
SessionStart Hook: Surface high-scoring retro entries ready for graduation.

Runs retro-graduate.py scan --threshold 7 and prints structured messages
for candidates with a clear target (single matching agent). Does NOT
auto-graduate -- only surfaces candidates for intentional action.

Design Principles:
- Silent when no candidates found (no noise)
- Non-blocking (always exits 0)
- once: true (runs once per session)
- 3-second timeout (scan reads markdown files, fast I/O)
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def main():
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    try:
        # Locate retro-graduate.py relative to this hook
        script_path = Path(__file__).parent.parent / "scripts" / "retro-graduate.py"
        if not script_path.exists():
            if debug:
                print(f"[graduation-scanner] Script not found: {script_path}", file=sys.stderr)
            return

        result = subprocess.run(
            ["python3", str(script_path), "scan", "--threshold", "7"],
            capture_output=True,
            text=True,
            timeout=3,
        )

        if result.returncode != 0:
            if debug:
                print(f"[graduation-scanner] scan failed: {result.stderr[:200]}", file=sys.stderr)
            return

        data = json.loads(result.stdout)
        candidates = data.get("candidates", [])

        if not candidates:
            return

        for candidate in candidates:
            matching = candidate.get("matching_agents", [])
            topic = candidate.get("topic", "?")
            key = candidate.get("key", "?")
            score = candidate.get("score", 0)

            if len(matching) == 1:
                print(f"[graduation-ready] {topic}/{key} -> {matching[0]} (score: {score})")
            elif debug and len(matching) > 1:
                print(
                    f"[graduation-scanner] {topic}/{key} has {len(matching)} targets, skipping",
                    file=sys.stderr,
                )

    except subprocess.TimeoutExpired:
        if debug:
            print("[graduation-scanner] scan timed out after 3s", file=sys.stderr)
    except (json.JSONDecodeError, Exception) as e:
        if debug:
            print(f"[graduation-scanner] Error: {e}", file=sys.stderr)
    finally:
        sys.exit(0)  # Never block


if __name__ == "__main__":
    main()
