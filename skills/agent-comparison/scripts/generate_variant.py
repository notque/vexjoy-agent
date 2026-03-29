#!/usr/bin/env python3
"""Generate a variant of an agent/skill file using Claude Code.

Proposes modifications to improve the target file based on the optimization
goal and previous iteration failures. Preserves protected sections marked
with DO NOT OPTIMIZE markers.

Pattern: uses `claude -p` so generation runs through Claude Code directly.

Usage:
    python3 skills/agent-comparison/scripts/generate_variant.py \
        --target agents/golang-general-engineer.md \
        --goal "improve error handling instructions" \
        --current-content "..." \
        --failures '[...]' \
        --model claude-opus-4-6

Output (JSON to stdout):
    {
        "variant": "full file content...",
        "summary": "Added CRITICAL warning for error wrapping",
        "deletion_justification": "",
        "reasoning": "Extended thinking content...",
        "tokens_used": 12345
    }

See ADR-131 for safety rules.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Protected section handling
# ---------------------------------------------------------------------------

_PROTECTED_RE = re.compile(
    r"(<!--\s*DO NOT OPTIMIZE\s*-->.*?<!--\s*END DO NOT OPTIMIZE\s*-->)",
    re.DOTALL,
)


def extract_protected(content: str) -> list[str]:
    """Extract all protected sections from content."""
    return _PROTECTED_RE.findall(content)


def restore_protected(original: str, variant: str) -> str:
    """Restore protected sections from original into variant."""
    orig_sections = extract_protected(original)
    var_sections = extract_protected(variant)

    if len(orig_sections) != len(var_sections):
        print(
            f"Warning: Protected section count mismatch (original={len(orig_sections)}, variant={len(var_sections)}).",
            file=sys.stderr,
        )
        return variant

    result = variant
    for orig_sec, var_sec in zip(orig_sections, var_sections):
        result = result.replace(var_sec, orig_sec, 1)

    return result


# ---------------------------------------------------------------------------
# Deletion detection
# ---------------------------------------------------------------------------


def detect_deletions(original: str, variant: str) -> list[str]:
    """Find sections that exist in original but are missing from variant.

    Returns list of deleted section headings. Only checks ## headings.
    """
    orig_headings = set(re.findall(r"^##\s+(.+)$", original, re.MULTILINE))
    var_headings = set(re.findall(r"^##\s+(.+)$", variant, re.MULTILINE))
    return sorted(orig_headings - var_headings)


# ---------------------------------------------------------------------------
# Variant generation
# ---------------------------------------------------------------------------


def _find_project_root() -> Path:
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / ".claude").is_dir():
            return parent
    print("Warning: .claude/ directory not found, using cwd as project root", file=sys.stderr)
    return current


def _run_claude_code(prompt: str, model: str | None) -> tuple[str, str, int]:
    """Run Claude Code and return (response_text, raw_result_text, tokens_used)."""
    cmd = ["claude", "-p", prompt, "--output-format", "json", "--print"]
    if model:
        cmd.extend(["--model", model])

    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(_find_project_root()),
        env=env,
        timeout=300,
    )
    if result.returncode != 0:
        print(f"Error: claude -p failed with code {result.returncode}", file=sys.stderr)
        if result.stderr:
            print(result.stderr.strip(), file=sys.stderr)
        sys.exit(1)

    try:
        events = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        print(f"Error: could not parse claude -p JSON output: {exc}", file=sys.stderr)
        sys.exit(1)

    assistant_text = ""
    raw_result_text = ""
    tokens_used = 0
    for event in events:
        if event.get("type") == "assistant":
            message = event.get("message", {})
            for content in message.get("content", []):
                if content.get("type") == "text":
                    assistant_text += content.get("text", "")
        elif event.get("type") == "result":
            raw_result_text = event.get("result", "")
            usage = event.get("usage", {})
            tokens_used = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)

    return assistant_text or raw_result_text, raw_result_text, tokens_used


def generate_variant(
    target_path: str,
    goal: str,
    current_content: str,
    failures: list[dict],
    model: str | None,
    history: list[dict] | None = None,
    diversification_note: str | None = None,
) -> dict:
    """Call Claude Code to generate a variant of the target file.

    Returns dict with variant content, summary, reasoning, and token count.
    """
    # Build the prompt
    failure_section = ""
    if failures:
        failure_section = "\n\nFailed tasks from the last iteration:\n"
        for f in failures:
            failure_section += f"  - {f.get('name', 'unnamed')}: {f.get('details', 'failed')}\n"

    history_section = ""
    if history:
        history_section = "\n\nPrevious attempts (do NOT repeat — try structurally different approaches):\n"
        for h in history:
            history_section += (
                f"  Iteration {h.get('number', '?')}: {h.get('verdict', '?')} — {h.get('change_summary', '')}\n"
            )

    diversification_section = ""
    if diversification_note:
        diversification_section = f"\n\nSearch diversification instruction:\n{diversification_note}\n"

    protected_sections = extract_protected(current_content)
    protected_notice = ""
    if protected_sections:
        protected_notice = f"""

CRITICAL SAFETY RULE: The file contains {len(protected_sections)} protected section(s) marked with
<!-- DO NOT OPTIMIZE --> and <!-- END DO NOT OPTIMIZE --> markers.
You MUST preserve these sections EXACTLY as they are — character for character.
Do not add, remove, or modify anything between these markers.
This is non-negotiable: protected sections contain safety gates that must not be
removed even if removing them would improve test scores."""

    prompt = f"""You are optimizing an agent/skill file to improve its performance.

Target file: {target_path}
Optimization goal: {goal}

Current content of the file:
<current_content>
{current_content}
</current_content>
{failure_section}{history_section}{diversification_section}{protected_notice}

SAFETY RULES:
1. Do NOT delete sections without replacing them with equivalent or better content.
   If you remove a section heading that exists in the original, you must explain what
   replaces the removed functionality. Pure deletion degrades unmeasured capabilities.

2. Do NOT change the tools, SDKs, or interfaces the agent uses. The variant must work
   in the same environment as the original (no switching from SDK to curl, etc.).

3. Keep YAML frontmatter structure intact (name, description, routing, etc.).

4. Focus on making the agent/skill better at achieving the stated goal. Common
   improvements include:
   - Moving critical information to more prominent positions (CRITICAL banners)
   - Adding explicit planning steps before code generation
   - Improving error handling instructions with specific patterns
   - Adding concrete examples for ambiguous instructions
   - Restructuring for clarity when sections are dense

Please respond with the complete modified file content inside <variant> tags,
and a brief summary of what you changed and why inside <summary> tags.

If you removed any existing `##` section heading, include a brief justification
inside <deletion_justification> tags. If you did not remove a section, return
empty tags.

<variant>
[complete file content here]
</variant>

<summary>
[1-2 sentence description of the change]
</summary>

<deletion_justification>
[why any removed section was replaced safely, or leave blank]
</deletion_justification>"""

    text, raw_result_text, tokens_used = _run_claude_code(prompt, model)

    # Parse variant content
    variant_match = re.search(r"<variant>(.*?)</variant>", text, re.DOTALL)
    if not variant_match:
        print("Error: No <variant> tags in response", file=sys.stderr)
        sys.exit(1)

    variant = variant_match.group(1).strip()

    # Parse summary
    summary_match = re.search(r"<summary>(.*?)</summary>", text, re.DOTALL)
    summary = summary_match.group(1).strip() if summary_match else "No summary provided"

    deletion_match = re.search(r"<deletion_justification>(.*?)</deletion_justification>", text, re.DOTALL)
    deletion_justification = deletion_match.group(1).strip() if deletion_match else ""

    # Restore protected sections (safety net)
    variant = restore_protected(current_content, variant)

    # Check for unauthorized deletions
    deletions = detect_deletions(current_content, variant)
    if deletions:
        print(f"Warning: Deleted sections: {deletions}", file=sys.stderr)

    return {
        "variant": variant,
        "summary": summary,
        "deletion_justification": deletion_justification,
        "reasoning": raw_result_text,
        "tokens_used": tokens_used,
        "deletions": deletions,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Generate agent/skill variant using Claude")
    parser.add_argument("--target", required=True, help="Path to target file (for context)")
    parser.add_argument("--goal", required=True, help="Optimization goal")
    content_group = parser.add_mutually_exclusive_group(required=True)
    content_group.add_argument("--current-content", help="Current file content")
    content_group.add_argument("--current-content-file", help="Path to a file containing the current content")
    parser.add_argument("--failures", default="[]", help="JSON list of failed tasks")
    parser.add_argument("--history", default="[]", help="JSON list of previous iterations")
    parser.add_argument("--diversification-note", default=None, help="Optional search diversification hint")
    parser.add_argument("--model", default=None, help="Optional Claude Code model override")
    args = parser.parse_args()

    try:
        failures = json.loads(args.failures)
    except json.JSONDecodeError as e:
        print(f"Error: --failures is not valid JSON: {e}", file=sys.stderr)
        sys.exit(1)
    try:
        history = json.loads(args.history)
    except json.JSONDecodeError as e:
        print(f"Error: --history is not valid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    current_content = (
        Path(args.current_content_file).read_text(encoding="utf-8")
        if args.current_content_file
        else args.current_content
    )

    result = generate_variant(
        target_path=args.target,
        goal=args.goal,
        current_content=current_content,
        failures=failures,
        model=args.model,
        history=history if history else None,
        diversification_note=args.diversification_note,
    )

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
