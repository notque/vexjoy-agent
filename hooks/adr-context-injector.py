#!/usr/bin/env python3
# hook-version: 1.0.0
"""
UserPromptSubmit Hook: ADR Context Injector

Automatically injects active ADR session context into every prompt when
.adr-session.json exists in the project directory. This ensures the
adr-query.py command is unavoidably present in every agent context during
an active pipeline session — for the orchestrator AND every sub-agent.

Detection Logic:
- Read userMessage and cwd from stdin JSON
- Look for .adr-session.json in cwd (fallback: CLAUDE_PROJECT_DIR env)
- If not found: no-op (empty_output)
- If found: verify adr_path still exists, check prompt relevance
- If relevant: inject ADR reminder context block

Relevance Keywords (any one triggers injection):
  pipeline, scaffold, subdomain, chain, step, skill, agent, hook,
  adr, compose, orchestrat, create, new, build, implement, design,
  feature, component, write, add, generat, develop

Design Principles:
- Non-blocking (always exits 0)
- Sub-50ms execution (file reads only, no subprocess)
- Graceful degradation on malformed JSON or missing files
"""

import json
import os
import sys
import traceback
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import context_output, empty_output, log_warning
from stdin_timeout import read_stdin

EVENT_NAME = "UserPromptSubmit"

ADR_SESSION_FILE = ".adr-session.json"

# Any one of these keywords in the prompt triggers injection
RELEVANCE_KEYWORDS = [
    "pipeline",
    "scaffold",
    "subdomain",
    "chain",
    "step",
    "skill",
    "agent",
    "hook",
    "adr",
    "compose",
    "orchestrat",
    "create",
    "new",
    "build",
    "implement",
    "design",
    "feature",
    "component",
    "write",
    "add",
    "generat",
    "develop",
]


def is_relevant_prompt(prompt: str) -> bool:
    """Return True if the prompt contains at least one relevance keyword."""
    prompt_lower = prompt.lower()
    return any(kw in prompt_lower for kw in RELEVANCE_KEYWORDS)


def load_adr_session(session_path: Path) -> dict | None:
    """
    Load and parse .adr-session.json.

    Returns None on missing file or malformed JSON (logs warning).
    """
    if not session_path.is_file():
        return None

    try:
        content = session_path.read_text(encoding="utf-8")
        return json.loads(content)
    except json.JSONDecodeError as e:
        log_warning(f"[adr-context-injector] Malformed .adr-session.json: {e}")
        return None
    except OSError as e:
        log_warning(f"[adr-context-injector] Cannot read .adr-session.json: {e}")
        return None


def build_injection(session: dict, base_dir: Path) -> str:
    """Build the ADR reminder context block from session data."""
    adr_path = session.get("adr_path", "")
    adr_hash = session.get("adr_hash", "")
    domain = session.get("domain", "")

    return (
        f"[adr-system] ACTIVE ADR SESSION\n"
        f"[adr-system] ADR: {adr_path}\n"
        f"[adr-system] Hash: {adr_hash}\n"
        f"[adr-system] Domain: {domain}\n"
        f"[adr-system]\n"
        f"[adr-system] MANDATORY BEFORE CREATING ANY PIPELINE COMPONENT:\n"
        f"[adr-system]   python3 ~/.claude/scripts/adr-query.py context --adr {adr_path} --role {{role}}\n"
        f"[adr-system]   Roles: skill-creator | agent-creator | script-creator | chain-composer | orchestrator\n"
        f"[adr-system]\n"
        f"[adr-system] COMPLIANCE CHECK AFTER WRITING ANY COMPONENT FILE:\n"
        f"[adr-system]   python3 ~/.claude/scripts/adr-compliance.py check --file {{file}} \\\n"
        f"[adr-system]     --step-menu ~/.claude/skills/pipeline-scaffolder/references/step-menu.md \\\n"
        f"[adr-system]     --spec-format ~/.claude/skills/pipeline-scaffolder/references/pipeline-spec-format.md\n"
        f"[adr-system]\n"
        f"[adr-system] ADR integrity: python3 ~/.claude/scripts/adr-query.py verify --adr {adr_path} --hash {adr_hash}"
    )


def main() -> None:
    """Main entry point for the hook."""
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    try:
        raw = read_stdin(timeout=2)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {}

        prompt = data.get("userMessage", "")

        # Resolve project directory: prefer data["cwd"], then env var, then "."
        cwd_str = data.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR", ".")
        base_dir = Path(cwd_str).resolve()

        session_path = base_dir / ADR_SESSION_FILE
        session = load_adr_session(session_path)

        if session is None:
            # No active ADR session — no-op
            empty_output(EVENT_NAME).print_and_exit()

        # Verify the ADR file still exists
        adr_path_str = session.get("adr_path", "")
        if adr_path_str:
            adr_file = base_dir / adr_path_str
            if not adr_file.is_file():
                log_warning(f"[adr-context-injector] ADR file not found: {adr_file} — skipping injection")
                empty_output(EVENT_NAME).print_and_exit()

        # Check prompt relevance
        if prompt and not is_relevant_prompt(prompt):
            if debug:
                print(
                    "[adr-context-injector] Prompt not pipeline-relevant — skipping",
                    file=sys.stderr,
                )
            empty_output(EVENT_NAME).print_and_exit()

        # Build and emit injection
        injection = build_injection(session, base_dir)

        if debug:
            print(
                f"[adr-context-injector] Injecting ADR context for domain={session.get('domain', '')}",
                file=sys.stderr,
            )

        context_output(EVENT_NAME, injection).print_and_exit()

    except Exception as e:
        if debug:
            traceback.print_exc(file=sys.stderr)
        else:
            print(
                f"[adr-context-injector] Error: {type(e).__name__}: {e}",
                file=sys.stderr,
            )
        empty_output(EVENT_NAME).print_and_exit()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[adr-context-injector] Fatal: {e}", file=sys.stderr)
    finally:
        sys.exit(0)
