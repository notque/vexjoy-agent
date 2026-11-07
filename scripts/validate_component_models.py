#!/usr/bin/env python3
"""Validate model policy for agents, skills, and workflow pipeline references.

Anthropic model policy (owner, 2026-11-01): Opus does all code, edits,
debugging, deciding reviews, and decisions; Haiku does read-only gathering that
an Opus thread judges; Sonnet is no task's default. So a component may pin
``opus`` or ``inherit``, may pin ``haiku`` only when its declared tool list
(``tools`` or ``allowed-tools``) holds no tool that can change files, and may
pin anything else (``sonnet`` included) only through EXEMPT_COMPONENTS.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.lib.frontmatter import parse_frontmatter

MODEL_RE = re.compile(r"^model:\s*(.+)$", re.MULTILINE)
ALLOWED_MODELS = {"opus", "inherit"}
READ_ONLY_MODELS = {"haiku"}
# Tools that can change files. Bash counts: a shell can write anything.
WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit", "Bash"}
EXEMPT_COMPONENTS: set[tuple[str, str]] = {
    ("skill", "do"),
    # image-generation skill; its Gemini image model is legitimate
    ("skill", "image-gen"),
}


@dataclass
class Violation:
    component_type: str
    component: str
    file: str
    issue: str


def scan_targets() -> list[tuple[str, str, Path]]:
    targets: list[tuple[str, str, Path]] = []
    for path in sorted((REPO_ROOT / "agents").glob("*.md")):
        if path.name == "README.md":
            continue
        targets.append(("agent", path.stem, path))
    for path in sorted((REPO_ROOT / "skills").glob("*/*/SKILL.md")):
        targets.append(("skill", path.parent.name, path))
    for path in sorted((REPO_ROOT / "skills" / "process" / "workflow" / "references").glob("*.md")):
        targets.append(("workflow_ref", path.stem, path))
    return targets


def declared_tools(text: str) -> list[str] | None:
    """Tool names from frontmatter ``tools`` or ``allowed-tools``; None when neither is set.

    Accepts a YAML list or a comma/space separated string. ``Bash(git diff:*)``
    counts as ``Bash``.
    """
    frontmatter, _ = parse_frontmatter(text)
    if not frontmatter:
        return None
    raw = frontmatter.get("tools", frontmatter.get("allowed-tools"))
    if raw is None:
        return None
    items = raw if isinstance(raw, list) else re.split(r"[,\s]+", str(raw))
    return [str(item).split("(", 1)[0].strip() for item in items if str(item).strip()]


def model_issue(model: str, text: str) -> str | None:
    """Return why *model* breaks the policy for this component, or None when it is allowed."""
    if model in ALLOWED_MODELS:
        return None
    if model in READ_ONLY_MODELS:
        tools = declared_tools(text)
        if tools is None:
            return f"model '{model}' is for read-only gathering; declare a read-only tools list (no tools list inherits Edit and Write)"
        writers = sorted(set(tools) & WRITE_TOOLS)
        if writers:
            return f"model '{model}' is for read-only gathering; this component declares {', '.join(writers)}"
        return None
    if model == "sonnet":
        return "model 'sonnet' is no task's default (owner policy 2026-11-01); use 'opus' or 'inherit', or add an EXEMPT_COMPONENTS entry with the reason"
    return f"model '{model}' is not allowed; use 'opus', 'inherit', or 'haiku' on a read-only component"


def validate_models() -> list[Violation]:
    violations: list[Violation] = []
    for component_type, component, path in scan_targets():
        if (component_type, component) in EXEMPT_COMPONENTS or ("skill", component) in EXEMPT_COMPONENTS:
            continue

        text = path.read_text(encoding="utf-8", errors="ignore")
        match = MODEL_RE.search(text)
        if not match:
            continue

        issue = model_issue(match.group(1).strip(), text)
        if issue is None:
            continue

        violations.append(
            Violation(
                component_type=component_type,
                component=component,
                file=str(path.relative_to(REPO_ROOT)),
                issue=issue,
            )
        )
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate component model policy")
    parser.add_argument("--json", dest="json_output", action="store_true", help="Emit JSON output")
    args = parser.parse_args()

    targets = scan_targets()
    empty = sorted({"agent", "skill", "workflow_ref"} - {kind for kind, _, _ in targets})
    if empty:
        print(f"error: no files found for target class(es): {', '.join(empty)}", file=sys.stderr)
        return 2

    violations = validate_models()
    payload = {"scanned": len(targets), "count": len(violations), "violations": [asdict(v) for v in violations]}
    if args.json_output:
        print(json.dumps(payload, indent=2))
    else:
        for violation in violations:
            print(f"{violation.file}: {violation.issue}")
        print(f"scanned: {len(targets)}")
        print(f"count: {len(violations)}")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
