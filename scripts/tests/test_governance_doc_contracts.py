"""Focused contracts for governance documentation that drives execution."""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_every_non_skill_dir_in_skills_root_is_a_support_or_data_dir() -> None:
    """The installer (scripts/vexinstall) installs only SUPPORT_DIRS next to skills.

    A new top-level skills/ dir that holds neither a SKILL.md nor nested skills
    must be registered in SUPPORT_DIRS or DATA_DIRS, or it silently stops
    reaching runtimes.
    """
    import sys

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from vexinstall.common import DATA_DIRS, SUPPORT_DIRS

    unknown = []
    for top in sorted((REPO_ROOT / "skills").iterdir()):
        if not top.is_dir() or top.name.startswith(".") or top.name == "__pycache__":
            continue
        if (top / "SKILL.md").is_file() or any((c / "SKILL.md").is_file() for c in top.iterdir() if c.is_dir()):
            continue
        if top.name not in SUPPORT_DIRS | DATA_DIRS:
            unknown.append(top.name)
    assert unknown == [], f"register in vexinstall SUPPORT_DIRS or DATA_DIRS: {unknown}"


def test_content_pipeline_targets_resolve() -> None:
    """Public content routes cannot depend on files outside this repository."""
    index = json.loads((REPO_ROOT / "skills/process/workflow/references/pipeline-index.json").read_text())
    for name, pipeline in index["pipelines"].items():
        if pipeline.get("category") == "content":
            assert (REPO_ROOT / pipeline["file"]).is_file(), f"pipeline {name}: {pipeline['file']}"
