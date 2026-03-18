#!/usr/bin/env python3
"""UserPromptSubmit hook: inject full capability catalog into /do routing context.

When /do is invoked, this hook runs `list-capabilities.py catalog --compact`
and outputs the result as <available-capabilities> XML so the LLM can see
all skills and agents when making routing decisions.

This is the treatment arm of the context-enrichment A/B test.
See: adr/cli-context-enrichment.md

Performance: ~50ms (reads two JSON index files, no network).
"""

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CATALOG_SCRIPT = REPO_ROOT / "scripts" / "list-capabilities.py"


def main() -> None:
    # Read the prompt from the hook input
    hook_input = json.loads(sys.stdin.read())
    prompt = hook_input.get("prompt", "")

    # Only inject when /do is being invoked
    if not prompt.strip().startswith("/do"):
        return

    # Run the catalog command
    try:
        result = subprocess.run(
            [sys.executable, str(CATALOG_SCRIPT), "catalog", "--compact"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(REPO_ROOT),
        )
        if result.returncode != 0:
            return

        catalog = result.stdout.strip()
        if not catalog:
            return

        # Output as context injection
        print(f"""<available-capabilities>
The following is the complete catalog of all skills and agents available
for routing. Use this to inform your routing decision — skills and agents
listed here may not appear in /do's static routing tables but ARE available.

{catalog}
</available-capabilities>""")

    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass  # Non-blocking: if catalog fails, /do works fine without it


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    finally:
        sys.exit(0)
