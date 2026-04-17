#!/usr/bin/env python3
# hook-version: 1.0.0
"""UserPromptSubmit hook: inject full capability catalog into /do routing context.

When /do is invoked, this hook runs `list-capabilities.py catalog --compact`
and outputs the result as <available-capabilities> XML so the LLM can see
all skills and agents when making routing decisions.

This is the treatment arm of the context-enrichment A/B test.
See: adr/cli-context-enrichment.md

Performance: ~50ms (reads two JSON index files, no network).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CATALOG_SCRIPT = REPO_ROOT / "scripts" / "list-capabilities.py"


def main() -> None:
    # DISABLED: The /do SKILL.md already contains structured routing tables
    # with triggers, agent pairings, and force-route rules. This hook injected
    # ~52KB of redundant flat JSON on every /do invocation.
    #
    # Originally the "treatment arm" of an A/B test (adr/cli-context-enrichment.md).
    # The /do skill's own tables proved more useful than a flat catalog dump.
    return


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            import traceback

            print(f"[capability-catalog-injector] HOOK-ERROR: {type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
    finally:
        sys.exit(0)
