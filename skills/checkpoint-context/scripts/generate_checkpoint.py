#!/usr/bin/env python3
"""
Generate checkpoint files for session context preservation.

Creates structured markdown checkpoints with task state, file context,
decisions, debugging state, and next steps optimized for LLM restoration.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def get_git_modified_files() -> list[dict]:
    """Get list of modified files from git status."""
    try:
        result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return []

        files = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            status = line[:2].strip()
            filepath = line[3:].strip()

            status_map = {"M": "modified", "A": "added", "D": "deleted", "R": "renamed", "??": "untracked"}

            files.append({"path": filepath, "status": status_map.get(status, status)})
        return files
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def get_git_branch() -> str:
    """Get current git branch name."""
    try:
        result = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return "unknown"


def get_recent_commit() -> str:
    """Get most recent commit hash and message."""
    try:
        result = subprocess.run(["git", "log", "-1", "--oneline"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return "unknown"


def slugify(text: str, max_length: int = 50) -> str:
    """Convert text to URL-friendly slug."""
    # Lowercase and replace spaces/special chars with hyphens
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower())
    # Remove leading/trailing hyphens
    slug = slug.strip("-")
    # Truncate to max length
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip("-")
    return slug or "checkpoint"


def generate_timestamp() -> tuple[str, str]:
    """Generate ISO timestamp and filename-safe timestamp."""
    now = datetime.now()
    iso = now.strftime("%Y-%m-%dT%H:%M:%S")
    filename = now.strftime("%Y%m%d-%H%M%S")
    return iso, filename


def generate_checkpoint_content(
    task: str,
    progress: str,
    trigger: str,
    files_read: list[dict] | None = None,
    files_modified: list[dict] | None = None,
    decisions: list[dict] | None = None,
    debugging_state: dict | None = None,
    patterns: list[dict] | None = None,
    next_steps: list[str] | None = None,
    session_id: str | None = None,
) -> str:
    """Generate checkpoint markdown content."""

    iso_timestamp, _ = generate_timestamp()

    # Get git context
    modified_from_git = get_git_modified_files()
    branch = get_git_branch()
    recent_commit = get_recent_commit()

    # Merge git-detected files with provided files
    if files_modified is None:
        files_modified = []

    # Add git-detected modified files if not already present
    existing_paths = {f.get("path") for f in files_modified}
    for git_file in modified_from_git:
        if git_file["path"] not in existing_paths:
            files_modified.append(
                {
                    "path": git_file["path"],
                    "status": git_file["status"],
                    "summary": f"[Auto-detected: {git_file['status']}]",
                }
            )

    # Default empty lists
    files_read = files_read or []
    decisions = decisions or []
    patterns = patterns or []
    next_steps = next_steps or ["[No next steps specified - add during checkpoint]"]

    # Default debugging state
    if debugging_state is None:
        debugging_state = {"current_error": "N/A", "hypotheses": [], "current_hypothesis": "N/A", "attempts": []}

    # Build markdown content
    lines = [
        f"# Context Checkpoint: {task}",
        "",
        f"**Created**: {iso_timestamp}",
        f"**Session ID**: {session_id or 'N/A'}",
        f"**Trigger**: {trigger}",
        f"**Branch**: {branch}",
        f"**Recent Commit**: {recent_commit}",
        "",
        "## Task State",
        "",
        f"- **Current task**: {task}",
        f"- **Progress**: {progress}",
        "- **Blockers**: None specified",
        "",
        "## Files Context",
        "",
        "### Read Files",
        "",
    ]

    if files_read:
        for f in files_read:
            path = f.get("path", "unknown")
            insight = f.get("insight", "No insight recorded")
            lines.append(f"- `{path}` - {insight}")
    else:
        lines.append("*No files explicitly tracked as read*")

    lines.extend(["", "### Modified Files", ""])

    if files_modified:
        for f in files_modified:
            path = f.get("path", "unknown")
            summary = f.get("summary", f.get("status", "modified"))
            lines.append(f"- `{path}` - {summary}")
    else:
        lines.append("*No files modified*")

    lines.extend(["", "## Decisions Made", ""])

    if decisions:
        for i, d in enumerate(decisions, 1):
            decision = d.get("decision", "Unknown decision")
            rationale = d.get("rationale", "No rationale recorded")
            lines.append(f"{i}. **{decision}**: {rationale}")
    else:
        lines.append("*No decisions recorded*")

    lines.extend(
        [
            "",
            "## Debugging State",
            "",
            f"- **Current error**: {debugging_state.get('current_error', 'N/A')}",
            "- **Hypotheses tested**:",
        ]
    )

    hypotheses = debugging_state.get("hypotheses", [])
    if hypotheses:
        for h in hypotheses:
            hypothesis = h.get("hypothesis", "Unknown")
            result = h.get("result", "unknown")
            lines.append(f"  - {hypothesis} - {result}")
    else:
        lines.append("  - *No hypotheses tested*")

    lines.extend(
        [f"- **Current hypothesis**: {debugging_state.get('current_hypothesis', 'N/A')}", "- **Attempts made**:"]
    )

    attempts = debugging_state.get("attempts", [])
    if attempts:
        for a in attempts:
            lines.append(f"  - {a}")
    else:
        lines.append("  - *No attempts recorded*")

    lines.extend(["", "## Discovered Patterns", ""])

    if patterns:
        for p in patterns:
            name = p.get("name", "Unknown pattern")
            description = p.get("description", "No description")
            lines.append(f"- **{name}**: {description}")
    else:
        lines.append("*No patterns recorded*")

    lines.extend(["", "## Next Steps", ""])

    for i, step in enumerate(next_steps, 1):
        lines.append(f"{i}. {step}")

    # LLM-optimized section
    lines.extend(
        [
            "",
            "## Raw Context (for LLM)",
            "",
            "```",
            f"TASK: {task}",
            f"PROGRESS: {progress}",
            f"BRANCH: {branch}",
            f"CURRENT_ERROR: {debugging_state.get('current_error', 'none')}",
            f"HYPOTHESIS: {debugging_state.get('current_hypothesis', 'none')}",
            "",
            "FILES_READ:",
        ]
    )

    if files_read:
        for f in files_read:
            lines.append(f"- {f.get('path', 'unknown')}: {f.get('insight', 'no insight')}")
    else:
        lines.append("- none")

    lines.append("")
    lines.append("FILES_MODIFIED:")

    if files_modified:
        for f in files_modified:
            lines.append(f"- {f.get('path', 'unknown')}: {f.get('summary', 'modified')}")
    else:
        lines.append("- none")

    lines.append("")
    lines.append("DECISIONS:")

    if decisions:
        for d in decisions:
            lines.append(f"- {d.get('decision', 'unknown')}: {d.get('rationale', 'no rationale')}")
    else:
        lines.append("- none")

    lines.append("")
    lines.append("PATTERNS:")

    if patterns:
        for p in patterns:
            lines.append(f"- {p.get('name', 'unknown')}: {p.get('description', 'no description')}")
    else:
        lines.append("- none")

    lines.append("")
    lines.append("NEXT:")

    for i, step in enumerate(next_steps, 1):
        lines.append(f"{i}. {step}")

    lines.append("```")

    return "\n".join(lines)


def write_checkpoint(content: str, task: str, checkpoints_dir: str) -> str:
    """Write checkpoint to file and return path."""
    _, filename_timestamp = generate_timestamp()
    slug = slugify(task)
    filename = f"{filename_timestamp}-{slug}.md"

    # Ensure directory exists
    Path(checkpoints_dir).mkdir(parents=True, exist_ok=True)

    filepath = os.path.join(checkpoints_dir, filename)

    with open(filepath, "w") as f:
        f.write(content)

    return filepath


def main():
    parser = argparse.ArgumentParser(description="Generate checkpoint files for session context preservation")
    parser.add_argument("--task", required=True, help="Current task description")
    parser.add_argument("--progress", default="unknown", help="Progress (percentage or phase)")
    parser.add_argument(
        "--trigger", choices=["manual", "pre-compact", "auto"], default="manual", help="What triggered this checkpoint"
    )
    parser.add_argument("--session-id", help="Session identifier (if available)")
    parser.add_argument("--context-json", help="JSON file with full context (files_read, decisions, etc.)")
    parser.add_argument("--checkpoints-dir", default="plan/checkpoints", help="Directory to write checkpoint files")
    parser.add_argument("--dry-run", action="store_true", help="Print checkpoint content without writing file")
    parser.add_argument(
        "--output-format",
        choices=["path", "content", "json"],
        default="path",
        help="Output format: path (default), content, or json",
    )

    args = parser.parse_args()

    # Load additional context from JSON if provided
    context = {}
    if args.context_json:
        try:
            with open(args.context_json) as f:
                context = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Warning: Could not load context JSON: {e}", file=sys.stderr)

    # Generate checkpoint content
    content = generate_checkpoint_content(
        task=args.task,
        progress=args.progress,
        trigger=args.trigger,
        session_id=args.session_id,
        files_read=context.get("files_read"),
        files_modified=context.get("files_modified"),
        decisions=context.get("decisions"),
        debugging_state=context.get("debugging_state"),
        patterns=context.get("patterns"),
        next_steps=context.get("next_steps"),
    )

    if args.dry_run:
        print(content)
        return

    # Write checkpoint file
    filepath = write_checkpoint(content, args.task, args.checkpoints_dir)

    # Output based on format
    if args.output_format == "path":
        print(filepath)
    elif args.output_format == "content":
        print(content)
    elif args.output_format == "json":
        result = {
            "filepath": filepath,
            "task": args.task,
            "progress": args.progress,
            "trigger": args.trigger,
            "timestamp": generate_timestamp()[0],
        }
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
