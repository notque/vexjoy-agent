#!/usr/bin/env python3
"""Generate a variant of an agent/skill file using Claude with extended thinking.

Proposes modifications to improve the target file based on the optimization
goal and previous iteration failures. Preserves protected sections marked
with DO NOT OPTIMIZE markers.

Pattern: follows improve_description.py's Claude + extended thinking approach.

Usage:
    python3 skills/agent-comparison/scripts/generate_variant.py \
        --target agents/golang-general-engineer.md \
        --goal "improve error handling instructions" \
        --current-content "..." \
        --failures '[...]' \
        --model claude-sonnet-4-20250514

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
import re
import sys

try:
    import anthropic
except ImportError:  # pragma: no cover - exercised in environments without the SDK
    anthropic = None

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
            "Warning: Protected section count mismatch "
            f"(original={len(orig_sections)}, variant={len(var_sections)}).",
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


def generate_variant(
    client: anthropic.Anthropic,
    target_path: str,
    goal: str,
    current_content: str,
    failures: list[dict],
    model: str,
    history: list[dict] | None = None,
) -> dict:
    """Call Claude to generate a variant of the target file.

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
            history_section += f"  Iteration {h.get('number', '?')}: {h.get('verdict', '?')} — {h.get('change_summary', '')}\n"

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
{failure_section}{history_section}{protected_notice}

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

    try:
        response = client.messages.create(
            model=model,
            max_tokens=16000,
            thinking={
                "type": "enabled",
                "budget_tokens": 10000,
            },
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIStatusError as e:
        print(f"Error: API returned status {e.status_code}: {e.message}", file=sys.stderr)
        sys.exit(1)
    except anthropic.APIConnectionError as e:
        print(f"Error: API connection failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Extract thinking and text
    thinking_text = ""
    text = ""
    for block in response.content:
        if block.type == "thinking":
            thinking_text = block.thinking
        elif block.type == "text":
            text = block.text

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

    tokens_used = response.usage.input_tokens + response.usage.output_tokens

    return {
        "variant": variant,
        "summary": summary,
        "deletion_justification": deletion_justification,
        "reasoning": thinking_text,
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
    parser.add_argument("--model", default="claude-sonnet-4-20250514", help="Model to use")
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

    if anthropic is None:
        print("Error: anthropic SDK is not installed", file=sys.stderr)
        sys.exit(1)

    current_content = (
        open(args.current_content_file, encoding="utf-8").read()
        if args.current_content_file
        else args.current_content
    )

    client = anthropic.Anthropic()
    result = generate_variant(
        client=client,
        target_path=args.target,
        goal=args.goal,
        current_content=current_content,
        failures=failures,
        model=args.model,
        history=history if history else None,
    )

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
