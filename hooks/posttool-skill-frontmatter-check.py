#!/usr/bin/env python3
# hook-version: 1.0.1
"""
PostToolUse Hook: Skill Frontmatter Validation

After Write or Edit operations on skills/**/SKILL.md files, runs the
frontmatter validator and injects errors as context if validation fails.

Advisory hook — always exits 0.
"""

import sys  # vexjoy-pyguard

if sys.version_info < (3, 10):  # vexjoy-pyguard advisory
    sys.stderr.write(
        "[vexjoy] hook %s needs Python 3.10+, got %s (%s); rerun ./install.sh in vexjoy-agent\n"
        % (__file__.rsplit("/", 1)[-1], sys.version.split()[0], sys.executable)
    )
    sys.exit(0)

import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from stdin_timeout import read_stdin

# Pattern matching skill SKILL.md files (flat and nested category layouts)
SKILL_FILE_RE = re.compile(r"skills/(?:[^/]+/)+SKILL\.md$")


_BYPASS_ENV = "POSTTOOL_SKILL_FRONTMATTER_CHECK_BYPASS"


def main():
    """Process PostToolUse hook event."""
    if os.environ.get(_BYPASS_ENV) == "1":
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            print(
                "[posttool-skill-frontmatter-check] Bypassed via POSTTOOL_SKILL_FRONTMATTER_CHECK_BYPASS=1",
                file=sys.stderr,
            )
        sys.exit(0)

    try:
        event_data = read_stdin(timeout=2)
        if not event_data.strip():
            return
        event = json.loads(event_data)

        # Get the file path from tool input
        tool_input = event.get("tool_input", {})
        file_path = tool_input.get("file_path", "")

        if not file_path:
            return

        # Only act on skills/**/SKILL.md files
        if not SKILL_FILE_RE.search(file_path):
            return

        # Check the file exists
        if not Path(file_path).exists():
            return

        # Find the validator script relative to this hook
        hook_dir = Path(__file__).resolve().parent
        # The validator is at scripts/validate-skill-frontmatter.py relative to repo root.
        # hooks/ is at the repo root level, so go up one level.
        repo_root = hook_dir.parent
        validator = repo_root / "scripts" / "validate-skill-frontmatter.py"

        if not validator.exists():
            return

        # Run the validator
        result = subprocess.run(
            [sys.executable, str(validator), file_path],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0 and result.stdout.strip():
            # Inject validation errors as context
            print(f"[skill-frontmatter] Validation failed for {Path(file_path).name}:")
            for line in result.stdout.strip().splitlines():
                if line.strip():
                    print(f"  {line.strip()}")
            print("[skill-frontmatter] Fix frontmatter before proceeding.")

    except Exception as e:
        print(f"[skill-frontmatter] hook error: {e}", file=sys.stderr)
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()
