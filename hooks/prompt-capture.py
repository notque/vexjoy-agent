#!/usr/bin/env python3
# hook-version: 1.0.0
# Voice sample capture — records authentic user prompts to learning.db as voice corpus.
"""
UserPromptSubmit Hook: Capture user prompts as voice samples.

User prompts in Claude Code are genuine human writing — never AI-generated.
This hook builds a growing corpus of authentic voice samples that voice
profile skills can reference.

Filter logic:
- Skip < 20 words (too little signal)
- Skip slash commands (/do, /quick, etc.)
- Skip prompts that are mostly file paths or shell commands
- Skip machine prompts: headless `claude -p` jobs and agent-generated task
  specs fire UserPromptSubmit like human turns (see is_machine_prompt)
- Skip if this exact prompt was already captured this session (dedup)

Records to learning.db category=voice, topic=voice-sample.
Silent on skip. Advisory (non-blocking).
"""

import hashlib
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from hook_utils import empty_output, get_session_id, hook_error
from learning_db_v2 import record_learning
from stdin_timeout import read_stdin

EVENT_NAME = "UserPromptSubmit"

# Session-level dedup: keyed by session_id, values are sets of prompt hashes.
# This is in-process only — different hook processes don't share state, so we
# use a hash-based check against the DB instead (see is_duplicate()).
_SEEN_THIS_PROCESS: set[str] = set()

# Patterns that indicate the prompt is mostly technical noise, not natural prose.
_SLASH_CMD_RE = re.compile(r"^\s*/[a-z]", re.IGNORECASE)
_MOSTLY_PATH_RE = re.compile(r"^[\s/~\.\w\-]+(\.py|\.go|\.ts|\.js|\.json|\.yaml|\.yml|\.sh|\.md)\s*$", re.IGNORECASE)

# Heuristic: a prompt is "code-noise" if more than 40% of its tokens look like
# paths, flags, or identifiers rather than natural language words.
_TOKEN_NOISE_RE = re.compile(r"^(/[\w./-]+|--?[\w-]+=?\S*|[\w]+[=:][\S]+|\d+\.?\d*)$")


def prompt_hash(text: str) -> str:
    """Stable 16-char hash for dedup."""
    return hashlib.md5(text[:500].lower().strip().encode()).hexdigest()[:16]


def word_count(text: str) -> int:
    return len(text.split())


def is_slash_command(text: str) -> bool:
    """True if the prompt starts with a slash command."""
    return bool(_SLASH_CMD_RE.match(text))


def is_mostly_path(text: str) -> bool:
    """True if the prompt is just a single file path."""
    return bool(_MOSTLY_PATH_RE.match(text.strip()))


def is_code_noise(text: str) -> bool:
    """True if the prompt reads more like a shell command than natural language.

    Heuristic: split on whitespace; if >40% of tokens look like flags/paths/
    identifiers, treat as code noise. Also catches things like
    'python3 ~/.claude/scripts/foo.py --arg value'.
    """
    tokens = text.split()
    if not tokens:
        return True
    noise_count = sum(1 for t in tokens if _TOKEN_NOISE_RE.match(t))
    return (noise_count / len(tokens)) > 0.4


# Machine-prompt filter (audit: 217/279 voice rows were machine text).
# Three high-precision checks; bias toward rejecting machine-shaped text.

# Substrings that only appear in generated prompts, never in human prose.
_MACHINE_MARKERS = (
    "[do-route]",
    "ROUTING MANIFEST",
    "<command-message>",
    "<command-name>",
    "<skill_content>",
)

# Markdown heading line — skipped before the opener check so prompts like
# "# Autonomous loop check\n\nYou're being invoked..." are still caught.
_MD_HEADING_RE = re.compile(r"^#{1,6}\s")

# Machine prompts assign a role in the second person with proper
# capitalization ("You are running...", "You're being invoked...").
# Case-sensitive on purpose: casual human "you are wrong about..." passes.
_ROLE_OPENER_RE = re.compile(r"^You(?: are|'re)\s")

# Generated task specs and headless job prompts run long. Human prompts in
# the corpus are 20-200 words; above this a prompt is a machine spec or
# paste-dominated — not voice corpus material either way.
_MAX_WORDS = 500


def is_machine_prompt(text: str) -> bool:
    """True if the prompt is machine-generated, not typed by a human.

    Headless `claude -p` jobs (auto-dream, toolkit-evolution, skill analysis)
    and agent dispatch prompts fire UserPromptSubmit exactly like human turns.
    """
    if any(marker in text for marker in _MACHINE_MARKERS):
        return True

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or _MD_HEADING_RE.match(stripped):
            continue  # skip blanks and headings before the opener check
        if _ROLE_OPENER_RE.match(stripped):
            return True
        break  # only the first content line is an opener

    return word_count(text) > _MAX_WORDS


def is_xml_or_structured(text: str) -> bool:
    """True if the prompt is XML, JSON, or internal system payload."""
    stripped = text.strip()
    return stripped.startswith("<") or stripped.startswith("{")


def is_in_git_repo(cwd: str) -> bool:
    """True if the CWD is inside a git repository.

    Walks up from cwd looking for a .git directory. This naturally filters
    out non-repo usage (e.g., kids using Claude Code in home directory or
    scratch folders) while capturing prompts from actual development work.
    """
    path = Path(cwd)
    for parent in [path, *path.parents]:
        if (parent / ".git").exists():
            return True
    return False


def is_natural_language(text: str) -> bool:
    """Composite guard: True if the prompt is worth capturing as a voice sample."""
    stripped = text.strip()

    if is_slash_command(stripped):
        return False

    if is_mostly_path(stripped):
        return False

    if is_xml_or_structured(stripped):
        return False

    if is_machine_prompt(stripped):
        return False

    wc = word_count(stripped)
    if wc < 20:
        return False

    if is_code_noise(stripped):
        return False

    return True


def main():
    try:
        raw = read_stdin(timeout=5)
        if not raw:
            empty_output(EVENT_NAME).print_and_exit()

        hook_input = json.loads(raw)
        prompt = (hook_input.get("prompt") or "").strip()

        if not prompt:
            empty_output(EVENT_NAME).print_and_exit()

        if not is_natural_language(prompt):
            empty_output(EVENT_NAME).print_and_exit()

        # Session-level dedup (in-process)
        key = prompt_hash(prompt)
        if key in _SEEN_THIS_PROCESS:
            empty_output(EVENT_NAME).print_and_exit()
        _SEEN_THIS_PROCESS.add(key)

        cwd = hook_input.get("cwd") or str(Path.cwd())

        # Only capture prompts from git repos — filters out non-dev usage
        # (kids, scratch directories) without requiring a named allowlist.
        if not is_in_git_repo(cwd):
            empty_output(EVENT_NAME).print_and_exit()

        session_id = hook_input.get("session_id") or get_session_id()

        record_learning(
            topic="voice-sample",
            key=key,
            value=prompt[:500],
            category="voice",
            confidence=0.80,
            tags=["source:user-prompt", "authentic"],
            source="hook:prompt-capture",
            source_detail="UserPromptSubmit",
            project_path=cwd,
            session_id=session_id,
        )

        # Silent capture — no output to avoid cluttering the conversation.
        empty_output(EVENT_NAME).print_and_exit()

    except Exception as e:
        hook_error("prompt-capture", e)
    finally:
        sys.exit(0)  # Never block


if __name__ == "__main__":
    main()
