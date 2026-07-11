"""Target-project behavior for the skill index sync hook."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "posttooluse-sync-skill-index.py"
SOURCE_INDEX = HOOK.parent.parent / "skills" / "INDEX.json"


def test_regen_targets_event_project_without_touching_source_checkout(tmp_path: Path) -> None:
    skill = tmp_path / "skills" / "testing" / "isolated-skill" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\nname: isolated-skill\ndescription: Isolated index sync fixture.\nuser-invocable: false\n---\n",
        encoding="utf-8",
    )
    before = SOURCE_INDEX.read_bytes() if SOURCE_INDEX.exists() else None
    event = {
        "hook_event_name": "PostToolUse",
        "cwd": str(tmp_path),
        "tool_input": {"file_path": str(skill)},
    }

    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        cwd="/",
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    index = tmp_path / "skills" / "INDEX.json"
    assert index.is_file(), result.stderr
    assert "isolated-skill" in json.loads(index.read_text(encoding="utf-8"))["skills"]
    after = SOURCE_INDEX.read_bytes() if SOURCE_INDEX.exists() else None
    assert after == before
