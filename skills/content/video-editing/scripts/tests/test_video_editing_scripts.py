"""The video-editing skill carries the scripts its instructions run.

`SKILL.md` (Video Transcript Extraction) and `references/image-to-video.md` used
to call scripts inside the video-transcript and image-to-video husks, which the
installer skips. These tests check that both scripts ship with video-editing and
run from it, offline and without ffmpeg.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
SCRIPTS = SKILL_DIR / "scripts"


def test_skill_docs_call_scripts_that_ship_with_the_skill() -> None:
    skill_md = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    image_ref = (SKILL_DIR / "references" / "image-to-video.md").read_text(encoding="utf-8")

    assert "${CLAUDE_SKILL_DIR}/scripts/vtt_to_paragraph.py" in skill_md
    assert "~/.claude/skills/video-editing/scripts/image_to_video.py" in image_ref
    assert (SCRIPTS / "vtt_to_paragraph.py").is_file()
    assert (SCRIPTS / "image_to_video.py").is_file()


def test_vtt_to_paragraph_cleans_rolling_captions(tmp_path: Path) -> None:
    vtt = tmp_path / "clip.en.vtt"
    vtt.write_text(
        "WEBVTT\n\n"
        "00:00:00.000 --> 00:00:02.000\nhello <c>there</c>\n\n"
        "00:00:02.000 --> 00:00:04.000\nhello there\n[Music]\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "vtt_to_paragraph.py"), str(vtt)],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert "hello there" in result.stdout
    assert "[Music]" not in result.stdout


def test_image_to_video_workspace_stays_inside_the_skill() -> None:
    spec = importlib.util.spec_from_file_location("image_to_video", SCRIPTS / "image_to_video.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.WORKSPACE_DIR == SKILL_DIR / "workspace"
    # The workspace .gitignore keeps user media out of git status.
    assert (SKILL_DIR / "workspace" / ".gitignore").is_file()
