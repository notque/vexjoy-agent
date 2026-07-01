"""Validate that INDEX.json / pipeline-index.json trigger-to-component mappings hold.

STATIC test — no LLM calls, no live router. routing-tables.md was absorbed
into skills/INDEX.json and pipeline-index.json (see
scripts/validate-index-integrity.py); this checks each sample trigger phrase
is still a literal trigger for its expected skill or pipeline entry.

Run with: python3 -m pytest scripts/tests/test_do_routing.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS_INDEX = REPO_ROOT / "skills" / "INDEX.json"
PIPELINE_INDEX = REPO_ROOT / "skills" / "workflow" / "references" / "pipeline-index.json"

# (trigger phrase, expected component name). Component is looked up in
# skills/INDEX.json first, then pipeline-index.json.
TEST_CASES = [
    ("create pull request", "pr-workflow"),
    ("push my changes", "pr-workflow"),
    ("stage and commit", "pr-workflow"),
    ("I am stuck", "workflow-help"),
    ("why is this broken", "systematic-debugging"),
    ("simplify this", "systematic-refactoring"),
    ("full code review", "comprehensive-review"),
    ("debug", "systematic-debugging"),
]


def _load_index(path: Path) -> dict:
    """Load an INDEX JSON file, skipping the test if it hasn't been generated."""
    if not path.exists():
        pytest.skip(f"{path.relative_to(REPO_ROOT)} not generated — run scripts/generate-skill-index.py first")
    return json.loads(path.read_text(encoding="utf-8"))


def _find_entry(name: str, skills: dict, pipelines: dict) -> dict | None:
    """Look up `name` as a skill first, then a pipeline."""
    if name in skills.get("skills", {}):
        return skills["skills"][name]
    return pipelines.get("pipelines", {}).get(name)


@pytest.mark.parametrize("trigger,expected_name", TEST_CASES)
def test_trigger_routes_to_expected_component(trigger: str, expected_name: str) -> None:
    """Each sample trigger must be a literal trigger on its expected component."""
    skills = _load_index(SKILLS_INDEX)
    pipelines = _load_index(PIPELINE_INDEX)

    entry = _find_entry(expected_name, skills, pipelines)
    assert entry is not None, f"'{expected_name}' not in skills/INDEX.json or pipeline-index.json"

    triggers = [t.lower() for t in entry.get("triggers", [])]
    assert trigger.lower() in triggers, f"'{trigger}' not a literal trigger for '{expected_name}' (has: {triggers})"
