#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PreToolUse Hook: Config Protection (ADR-115)

Blocks Write/Edit/MultiEdit calls that target linter and formatter config files.
Claude tends to weaken linter rules rather than fixing the underlying source code.
This hook intercepts those attempts and redirects the agent to fix the source instead.

Protected set: ESLint (12 variants), Prettier (10), Biome (2), Ruff (2),
               Shell/Style/Markdown (7), golangci-lint (4), setup.cfg — 38 files total.

Exit 2 = block. Exit 0 = allow. Entire main() wrapped in try/except to fail OPEN.
Bypass: CONFIG_PROTECTION_BYPASS=1 env var.
Performance: <50ms (no subprocess, pure set lookup).
"""

import json
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from stdin_timeout import read_stdin

_BYPASS_ENV = "CONFIG_PROTECTION_BYPASS"

# Maximum stdin size before we block rather than parse (truncation safety).
_MAX_STDIN_BYTES = 1 * 1024 * 1024  # 1 MB

# Protected config file basenames — exact match only (not path prefix).
_PROTECTED_CONFIGS: frozenset[str] = frozenset(
    [
        # ESLint — legacy formats
        ".eslintrc",
        ".eslintrc.js",
        ".eslintrc.cjs",
        ".eslintrc.json",
        ".eslintrc.yml",
        ".eslintrc.yaml",
        # ESLint — v9 flat config
        "eslint.config.js",
        "eslint.config.mjs",
        "eslint.config.cjs",
        "eslint.config.ts",
        "eslint.config.mts",
        "eslint.config.cts",
        # Prettier
        ".prettierrc",
        ".prettierrc.js",
        ".prettierrc.cjs",
        ".prettierrc.mjs",
        ".prettierrc.json",
        ".prettierrc.yml",
        ".prettierrc.yaml",
        "prettier.config.js",
        "prettier.config.cjs",
        "prettier.config.mjs",
        # Biome
        "biome.json",
        "biome.jsonc",
        # Ruff (Python) — pyproject.toml intentionally excluded
        ".ruff.toml",
        "ruff.toml",
        # Shell / Style / Markdown
        ".shellcheckrc",
        ".stylelintrc",
        ".stylelintrc.json",
        ".stylelintrc.yml",
        ".markdownlint.json",
        ".markdownlint.yaml",
        ".markdownlintrc",
        # Go linters
        ".golangci.yml",
        ".golangci.yaml",
        ".golangci.json",
        ".golangci.toml",
        # Python (beyond Ruff)
        "setup.cfg",
    ]
)


def _is_protected(file_path: str) -> bool:
    """Return True if the basename of file_path is in the protected set."""
    return Path(file_path).name in _PROTECTED_CONFIGS


def _block(file_path: str) -> None:
    """Print a block message to stderr and exit 2."""
    print(
        f"[config-protection] BLOCKED: Modifying linter/formatter config: {file_path}\n"
        "[config-protection] Fix the source code to satisfy the linter rather than weakening the config.\n"
        "[config-protection] To allow a legitimate config change: set CONFIG_PROTECTION_BYPASS=1",
        file=sys.stderr,
    )
    sys.exit(2)


def main() -> None:
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    if os.environ.get(_BYPASS_ENV) == "1":
        if debug:
            print("[config-protection] Bypassed via CONFIG_PROTECTION_BYPASS=1", file=sys.stderr)
        sys.exit(0)

    raw = read_stdin(timeout=2)

    # Truncation safety: oversized payloads are blocked rather than parsed.
    if len(raw.encode("utf-8", errors="replace")) > _MAX_STDIN_BYTES:
        print(
            "[config-protection] BLOCKED: stdin payload exceeds 1 MB limit — cannot safely parse.",
            file=sys.stderr,
        )
        sys.exit(2)

    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = event.get("tool_name") or event.get("tool", "")
    tool_input = event.get("tool_input", event.get("input", {}))

    if tool_name not in ("Write", "Edit", "MultiEdit"):
        sys.exit(0)

    if tool_name == "MultiEdit":
        # MultiEdit payload: tool_input has no top-level file_path.
        # Files live in tool_input["edits"] as [{file_path, ...}, ...].
        edits = tool_input.get("edits", [])
        for edit in edits:
            fp = edit.get("file_path", "")
            if fp and _is_protected(fp):
                if debug:
                    print(f"[config-protection] MultiEdit hit on protected file: {fp}", file=sys.stderr)
                _block(fp)
    else:
        # Write or Edit — single file_path at top level.
        file_path = tool_input.get("file_path", "")
        if not file_path:
            sys.exit(0)
        if _is_protected(file_path):
            if debug:
                print(f"[config-protection] {tool_name} hit on protected file: {file_path}", file=sys.stderr)
            _block(file_path)

    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise  # Let sys.exit(2) propagate for blocks
    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            traceback.print_exc(file=sys.stderr)
        else:
            print(f"[config-protection] Error: {type(e).__name__}: {e}", file=sys.stderr)
        # A crashed hook must fail OPEN — never exit 2 on unexpected errors.
        sys.exit(0)
