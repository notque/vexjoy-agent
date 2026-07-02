#!/usr/bin/env python3
# hook-version: 1.0.0
"""SessionStart Hook: hash-gated /do routing-manifest cache.

ADR router-improvement-program C5. Verifies (or rebuilds) the disk cache of
`routing-manifest.py` output so /do Phase 2 reads a file instead of starting
Python. Freshness = sha256 sidecar over the generator's inputs — see
hooks/lib/manifest_cache.py for the input list and digest contract.

Paths:
- Cache:   ~/.claude/cache/routing-manifest.txt
- Sidecar: ~/.claude/cache/routing-manifest.hash

Behavior:
- Inputs unchanged: no generator run, injects the cache path (fresh path
  measured <50ms).
- Inputs changed or cache absent: runs the generator once, rewrites cache +
  sidecar atomically (bounded by the 20s settings timeout, like the INDEX
  sync hooks).
- Generator failure or no deployed scripts dir: silent, /do Phase 2 falls
  back to running routing-manifest.py itself.
- Advisory: always exits 0.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import context_output, empty_output
from manifest_cache import CACHE_FILE, refresh, resolve_scripts_dir

EVENT_NAME = "SessionStart"


def main() -> None:
    scripts_dir = resolve_scripts_dir()
    if scripts_dir is None:
        # No deployed toolkit — nothing to cache.
        empty_output(EVENT_NAME).print_and_exit()
        return

    status = refresh(scripts_dir)
    if status.startswith("failed"):
        print(f"[manifest-cache] {status}; /do falls back to routing-manifest.py", file=sys.stderr)
        empty_output(EVENT_NAME).print_and_exit()
        return

    context_output(EVENT_NAME, f"[manifest-cache] {status}: {CACHE_FILE}").print_and_exit()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise  # Let print_and_exit's sys.exit(0) propagate normally
    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            import traceback

            traceback.print_exc(file=sys.stderr)
        else:
            print(f"[manifest-cache] Error: {type(e).__name__}: {e}", file=sys.stderr)
        # Crashed hook must fail open — never block session start.
    finally:
        sys.exit(0)
