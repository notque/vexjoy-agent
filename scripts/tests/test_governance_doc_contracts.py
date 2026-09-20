"""Focused contracts for governance documentation that drives execution."""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_support_directory_detection_is_shape_based() -> None:
    hook = (REPO_ROOT / "hooks/sync-to-user-claude.py").read_text()

    assert "def _is_support_dir(item: Path) -> bool:" in hook
    assert "has_md and not has_nested_skill" in hook
    assert "child.is_dir() and _is_support_dir(child)" in hook


def test_content_pipeline_targets_resolve() -> None:
    """Public content routes cannot depend on files outside this repository."""
    index = json.loads((REPO_ROOT / "skills/process/workflow/references/pipeline-index.json").read_text())
    for name, pipeline in index["pipelines"].items():
        if pipeline.get("category") == "content":
            assert (REPO_ROOT / pipeline["file"]).is_file(), f"pipeline {name}: {pipeline['file']}"
