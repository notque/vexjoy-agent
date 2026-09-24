"""Pinned core triggers (`validate-index-integrity.py` Check 7).

The repo check runs in CI; these tests prove it resolves skills then pipelines
and catches a dropped trigger or a missing component.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
integrity = importlib.import_module("validate-index-integrity")

SKILLS = {"skills": {"pr-workflow": {"triggers": ["Create Pull Request"]}}}
PIPELINES = {"pipelines": {"systematic-debugging": {"triggers": ["debug"]}}}


def test_pinned_triggers_resolve_skill_then_pipeline() -> None:
    pinned = [("create pull request", "pr-workflow"), ("debug", "systematic-debugging")]
    assert integrity.check_pinned_triggers(SKILLS, PIPELINES, pinned) == ([], [])


def test_pinned_trigger_dropped_or_component_missing_fails() -> None:
    pinned = [("push my changes", "pr-workflow"), ("I am stuck", "workflow-help")]
    errors, _ = integrity.check_pinned_triggers(SKILLS, PIPELINES, pinned)
    assert errors == [
        "'push my changes' is no longer a trigger of 'pr-workflow' (pinned core route)",
        "pinned component 'workflow-help' is in neither skills/INDEX.json nor pipeline-index.json",
    ]
