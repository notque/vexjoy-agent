#!/usr/bin/env python3
"""Validate model policy for agents, skills, workflow references, and dispatch scripts.

Anthropic model policy (owner, 2026-11-01; Fable tier added 2026-11-09): Opus
does code, edits, debugging, deciding reviews, and decisions; Fable takes the
hardest work (major refactors, architecture, leading a many-agent fan-out, or
when Opus at high fell short); Haiku does read-only gathering that a stronger
thread judges; Sonnet is no task's default. So a component may pin ``opus``,
``fable``, or ``inherit``, may pin ``haiku`` only when its ``tools`` list holds
no tool that can change files, and may pin anything else (``sonnet`` included)
only through EXEMPT_COMPONENTS.

Only ``tools`` counts: Claude Code enforces it for subagents, ignores
``allowed-tools`` on agents, and treats ``allowed-tools`` on skills as a grant,
so a read-only ``allowed-tools`` list still leaves Edit, Write, and Bash in reach.

Dispatch scripts (``.js`` and ``.mjs`` workflow scripts) hold no literal model
string. They call ``modelFor(role, override)`` from ``workflow-helpers.js``,
the one file in MODEL_TABLE_FILES that may name models. Comments are not
scanned.
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
ALLOWED_MODELS = {"opus", "fable", "inherit"}
READ_ONLY_MODELS = {"haiku"}
# Tools that can change files. Bash counts: a shell can write anything. Agent and
# Task count: the subagent they start can write.
WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit", "Bash", "Agent", "Task"}
EXEMPT_COMPONENTS: set[tuple[str, str]] = {
    ("skill", "do"),
    # image-generation skill; its Gemini image model is legitimate
    ("skill", "image-gen"),
}

# Dispatch scripts: every .js/.mjs in WORKFLOW_SCRIPT_DIR, plus any under
# DISPATCH_SCRIPT_ROOTS that calls agent(...).
WORKFLOW_SCRIPT_DIR = "skills/process/workflow/references"
DISPATCH_SCRIPT_ROOTS = ("skills", "agents")
DISPATCH_SCRIPT_SUFFIXES = {".js", ".mjs"}
AGENT_CALL_RE = re.compile(r"\bagent\s*\(")
# The one place a dispatch script may name a model: the modelFor() role table.
MODEL_TABLE_FILES = {f"{WORKFLOW_SCRIPT_DIR}/workflow-helpers.js"}
# `model: "x"`, `model = 'x'`, or a template literal: any string bound to `model`.
JS_MODEL_BINDING_RE = re.compile(r"\bmodel\s*[:=]\s*(?P<quote>[\"'`])(?P<value>[^\"'`\n]*)(?P=quote)")
# A whole string literal that is a Claude model name, wherever it sits (a
# ternary, a lookup table, a default argument).
JS_MODEL_NAME_RE = re.compile(
    r"(?P<quote>[\"'`])(?P<value>(?:opus|sonnet|haiku|fable|opusplan|claude-[\w.\-]+)(?:\[1m\])?)(?P=quote)"
)


@dataclass
class Violation:
    component_type: str
    component: str
    file: str
    issue: str
    line: int | None = None


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
    for path in dispatch_scripts():
        targets.append(("dispatch_script", path.stem, path))
    return targets


def dispatch_scripts() -> list[Path]:
    """Scripts that dispatch agents, without the files in MODEL_TABLE_FILES."""
    found: set[Path] = set()
    workflow_dir = REPO_ROOT / WORKFLOW_SCRIPT_DIR
    for root in DISPATCH_SCRIPT_ROOTS:
        base = REPO_ROOT / root
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if path.suffix not in DISPATCH_SCRIPT_SUFFIXES or not path.is_file():
                continue
            if "node_modules" in path.parts:
                continue
            if path.parent == workflow_dir or AGENT_CALL_RE.search(path.read_text(encoding="utf-8", errors="ignore")):
                found.add(path)
    return sorted(p for p in found if p.relative_to(REPO_ROOT).as_posix() not in MODEL_TABLE_FILES)


def strip_js_comments(text: str) -> str:
    """Blank out ``//`` and ``/* */`` comments, keeping strings and line numbers.

    A quote or ``//`` inside a string stays put. A ``'`` or ``"`` string ends at
    the line break, so one stray quote cannot hide the rest of the file.
    """
    out: list[str] = []
    i, n = 0, len(text)
    quote: str | None = None
    while i < n:
        ch = text[i]
        if quote:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == quote or (ch == "\n" and quote != "`"):
                quote = None
            i += 1
        elif ch in "\"'`":
            quote = ch
            out.append(ch)
            i += 1
        elif text.startswith("//", i):
            end = text.find("\n", i)
            i = n if end == -1 else end
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            end = n if end == -1 else end + 2
            out.append("\n" * text.count("\n", i, end))
            i = end
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def js_model_literals(text: str) -> list[tuple[int, str]]:
    """Return (line, model string) for each literal model string in a script."""
    hits: set[tuple[int, str]] = set()
    code = strip_js_comments(text)
    for pattern in (JS_MODEL_BINDING_RE, JS_MODEL_NAME_RE):
        for match in pattern.finditer(code):
            hits.add((code.count("\n", 0, match.start()) + 1, match.group("value")))
    return sorted(hits)


def declared_tools(text: str) -> list[str] | None:
    """Tool names from frontmatter ``tools``; None when it is not set.

    ``allowed-tools`` is ignored on purpose (see the module docstring). Accepts a
    YAML list or a comma/space separated string. ``Bash(git diff:*)`` counts as
    ``Bash``.
    """
    frontmatter, _ = parse_frontmatter(text)
    if not frontmatter:
        return None
    raw = frontmatter.get("tools")
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
            return (
                f"model '{model}' is for read-only gathering; declare a read-only `tools:` list "
                "(without one the component keeps Edit and Write; allowed-tools does not restrict them)"
            )
        writers = sorted(set(tools) & WRITE_TOOLS)
        if writers:
            return f"model '{model}' is for read-only gathering; this component declares {', '.join(writers)}"
        return None
    if model == "sonnet":
        return "model 'sonnet' is no task's default (owner policy 2026-11-01); use 'opus', 'fable', or 'inherit', or add an EXEMPT_COMPONENTS entry with the reason"
    return f"model '{model}' is not allowed; use 'opus', 'fable', 'inherit', or 'haiku' on a read-only component"


def validate_models() -> list[Violation]:
    violations: list[Violation] = []
    for component_type, component, path in scan_targets():
        if (component_type, component) in EXEMPT_COMPONENTS or ("skill", component) in EXEMPT_COMPONENTS:
            continue

        text = path.read_text(encoding="utf-8", errors="ignore")
        relative = str(path.relative_to(REPO_ROOT))
        if component_type == "dispatch_script":
            for line, value in js_model_literals(text):
                violations.append(
                    Violation(
                        component_type=component_type,
                        component=component,
                        file=relative,
                        issue=(
                            f"literal model string '{value}'; call modelFor(role, modelOverride) "
                            "from workflow-helpers.js, the only script that names models"
                        ),
                        line=line,
                    )
                )
            continue

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
                file=relative,
                issue=issue,
            )
        )
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate component model policy")
    parser.add_argument("--json", dest="json_output", action="store_true", help="Emit JSON output")
    args = parser.parse_args()

    targets = scan_targets()
    empty = sorted({"agent", "skill", "workflow_ref", "dispatch_script"} - {kind for kind, _, _ in targets})
    if empty:
        print(f"error: no files found for target class(es): {', '.join(empty)}", file=sys.stderr)
        return 2

    violations = validate_models()
    payload = {"scanned": len(targets), "count": len(violations), "violations": [asdict(v) for v in violations]}
    if args.json_output:
        print(json.dumps(payload, indent=2))
    else:
        for violation in violations:
            where = violation.file if violation.line is None else f"{violation.file}:{violation.line}"
            print(f"{where}: {violation.issue}")
        print(f"scanned: {len(targets)}")
        print(f"count: {len(violations)}")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
