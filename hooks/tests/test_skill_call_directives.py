"""Regression tests for exact, index-safe hook Skill-tool calls."""

from __future__ import annotations

import json
import re
from pathlib import Path

HOOKS = Path(__file__).resolve().parent.parent


def test_static_hook_directives_name_only_indexed_skills(public_index_dir: Path) -> None:
    index = json.loads((public_index_dir / "skills.json").read_text(encoding="utf-8"))["skills"]
    directive = re.compile(r"Call the Skill tool with `([a-z0-9][a-z0-9-]*)`\.")
    emitted = {
        match.group(1) for path in HOOKS.glob("*.py") for match in directive.finditer(path.read_text(encoding="utf-8"))
    }

    assert emitted == {
        "assessment",
        "process",
        "pr-workflow",
        "security",
        "toolkit",
        "writing",
    }
    assert emitted <= set(index)
