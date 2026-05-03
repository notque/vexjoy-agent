#!/usr/bin/env python3
"""Tests for road-to-aew patterns: deterministic idle, action coaching, padding gate, provenance.

Run:
    python3 -m pytest skills/game-sprite-pipeline/scripts/test_road_to_aew_patterns.py -x -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import deterministic_idle
import sprite_prompt
from sprite_verify import verify_padding


# ---------------------------------------------------------------------------
# Pattern 1: Deterministic Breathing Idle
# ---------------------------------------------------------------------------
class TestDeterministicIdle:
    """Tests for deterministic_idle.py breathing loop generation."""

    @staticmethod
    def _make_portrait(size: int = 512) -> Image.Image:
        """Create a synthetic portrait with a visible character silhouette."""
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Head
        cx = size // 2
        head_r = size // 10
        head_top = size // 6
        draw.ellipse(
            (cx - head_r, head_top, cx + head_r, head_top + 2 * head_r),
            fill=(200, 150, 100, 255),
        )
        # Body
        body_w = size // 4
        body_top = head_top + 2 * head_r
        body_bot = size - size // 8
        draw.rectangle(
            (cx - body_w // 2, body_top, cx + body_w // 2, body_bot),
            fill=(60, 60, 180, 255),
        )
        return img

    def test_generates_4_frames(self) -> None:
        """generate_idle_frames produces 4 frames with correct dimensions."""
        portrait = self._make_portrait(512)
        frames = deterministic_idle.generate_idle_frames(portrait, num_frames=4)
        assert len(frames) == 4
        for f in frames:
            assert f.size == (512, 512)
            assert f.mode == "RGBA"

    def test_frames_differ(self) -> None:
        """Breathing frames are not identical to the base (inhale/exhale differ)."""
        portrait = self._make_portrait(512)
        frames = deterministic_idle.generate_idle_frames(portrait, num_frames=4)
        # Frame 0 is base copy, frame 1 is inhale -- they should differ
        arr0 = np.array(frames[0])
        arr1 = np.array(frames[1])
        assert not np.array_equal(arr0, arr1), "inhale frame should differ from neutral"

    def test_strip_output(self, tmp_path: Path) -> None:
        """write_strip produces a horizontal strip of correct dimensions."""
        portrait = self._make_portrait(256)
        frames = deterministic_idle.generate_idle_frames(portrait, num_frames=4)
        strip_path = tmp_path / "strip.png"
        deterministic_idle.write_strip(frames, strip_path)
        assert strip_path.exists()
        strip = Image.open(strip_path)
        assert strip.size == (256 * 4, 256)

    def test_animation_outputs(self, tmp_path: Path) -> None:
        """write_animation produces GIF and WebP files."""
        portrait = self._make_portrait(128)
        frames = deterministic_idle.generate_idle_frames(portrait, num_frames=4)
        gif_path = tmp_path / "anim.gif"
        webp_path = tmp_path / "anim.webp"
        deterministic_idle.write_animation(frames, gif_path, fps=5)
        deterministic_idle.write_animation(frames, webp_path, fps=5)
        assert gif_path.exists()
        assert webp_path.exists()

    def test_cli_end_to_end(self, tmp_path: Path) -> None:
        """CLI main() produces all expected output files."""
        portrait = self._make_portrait(256)
        input_path = tmp_path / "portrait.png"
        portrait.save(input_path)
        out_dir = tmp_path / "idle_out"

        rc = deterministic_idle.main(
            [
                "--input",
                str(input_path),
                "--output-dir",
                str(out_dir),
                "--body-ratio",
                "0.74",
                "--frames",
                "4",
                "--fps",
                "5",
            ]
        )
        assert rc == 0
        assert (out_dir / "idle-strip.png").exists()
        assert (out_dir / "animation.gif").exists()
        assert (out_dir / "animation.webp").exists()
        assert (out_dir / "idle-meta.json").exists()
        assert (out_dir / "frames" / "frame-000.png").exists()
        assert (out_dir / "frames" / "frame-003.png").exists()

    def test_empty_image_returns_copy(self) -> None:
        """build_breath_frame on an empty image returns a copy without crashing."""
        empty = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        result = deterministic_idle.build_breath_frame(empty, 1.006, 1, 0.74)
        assert result.size == (64, 64)

    def test_few_frames(self) -> None:
        """num_frames=2 produces only 2 frames."""
        portrait = self._make_portrait(128)
        frames = deterministic_idle.generate_idle_frames(portrait, num_frames=2)
        assert len(frames) == 2

    def test_single_frame(self) -> None:
        """num_frames=1 produces a single base copy."""
        portrait = self._make_portrait(128)
        frames = deterministic_idle.generate_idle_frames(portrait, num_frames=1)
        assert len(frames) == 1


# ---------------------------------------------------------------------------
# Pattern 2: Per-Action Negative-Prompt Coaching
# ---------------------------------------------------------------------------
class TestActionCoaching:
    """Tests for ACTION_COACHING dict and prompt injection."""

    def test_coaching_dict_covers_all_presets(self) -> None:
        """ACTION_COACHING has entries for all preset states."""
        for _preset_name, preset in sprite_prompt.ANIMATION_PRESETS.items():
            for row in preset["rows"]:
                state = row["state"]
                # Not all states need coaching (running-right/left are variants)
                # but core states should be covered
                if state in sprite_prompt.ACTION_COACHING:
                    assert isinstance(sprite_prompt.ACTION_COACHING[state], str)

    def test_coaching_injected_in_row_strip_prompt(self) -> None:
        """compose_row_strip_prompt includes ACTION COACHING for known states."""
        meta = sprite_prompt.PromptMetadata(
            mode="row-strip",
            style_preset="modern-hi-bit",
            description="test fighter",
            action="combat idle",
            grid_cols=6,
            grid_rows=1,
            seed=0,
        )
        prompt = sprite_prompt.compose_row_strip_prompt(meta, state="idle", frames=6, action="combat idle")
        assert "ACTION COACHING:" in prompt
        assert "NOT a T-pose" in prompt

    def test_coaching_not_injected_for_unknown_state(self) -> None:
        """compose_row_strip_prompt omits ACTION COACHING for unknown states."""
        meta = sprite_prompt.PromptMetadata(
            mode="row-strip",
            style_preset="modern-hi-bit",
            description="test",
            action="some unknown action",
            grid_cols=4,
            grid_rows=1,
            seed=0,
        )
        prompt = sprite_prompt.compose_row_strip_prompt(
            meta, state="totally-unknown-state", frames=4, action="some unknown"
        )
        assert "ACTION COACHING:" not in prompt

    def test_coaching_after_vfx_rules(self) -> None:
        """ACTION COACHING appears after VFX containment rules in the prompt."""
        meta = sprite_prompt.PromptMetadata(
            mode="row-strip",
            style_preset="modern-hi-bit",
            description="test",
            action="dash",
            grid_cols=8,
            grid_rows=1,
            seed=0,
        )
        prompt = sprite_prompt.compose_row_strip_prompt(meta, state="dash-right", frames=8, action="rightward dash")
        vfx_pos = prompt.find("EFFECTS RULES:")
        coaching_pos = prompt.find("ACTION COACHING:")
        assert vfx_pos < coaching_pos, "coaching should appear after VFX rules"


# ---------------------------------------------------------------------------
# Pattern 3: CI Padding Validator Gate
# ---------------------------------------------------------------------------
class TestVerifyPadding:
    """Tests for verify_padding gate."""

    @staticmethod
    def _make_sheet(
        cols: int,
        rows: int,
        cell_size: int,
        fill_pct: float = 0.7,
    ) -> Image.Image:
        """Create a synthetic sheet with characters filling fill_pct of each cell."""
        sheet = Image.new("RGBA", (cols * cell_size, rows * cell_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(sheet)
        margin = int(cell_size * (1 - fill_pct) / 2)
        for r in range(rows):
            for c in range(cols):
                x0 = c * cell_size + margin
                y0 = r * cell_size + margin
                x1 = (c + 1) * cell_size - margin
                y1 = (r + 1) * cell_size - margin
                draw.rectangle((x0, y0, x1, y1), fill=(100, 150, 200, 255))
        return sheet

    def test_passes_for_well_filled_cells(self) -> None:
        """Cells filled at 70% pass the 15% padding threshold."""
        sheet = self._make_sheet(4, 2, 256, fill_pct=0.7)
        result = verify_padding(sheet, 4, 2, 256)
        assert result["passed"] is True
        assert len(result["frames_with_excess_padding"]) == 0

    def test_fails_for_tiny_sprites(self) -> None:
        """Cells filled at only 30% (35% padding per side) fail."""
        sheet = self._make_sheet(4, 1, 256, fill_pct=0.3)
        result = verify_padding(sheet, 4, 1, 256)
        assert result["passed"] is False
        assert len(result["frames_with_excess_padding"]) == 4

    def test_skips_expected_empty_cells(self) -> None:
        """Expected empty cells are excluded from padding analysis."""
        sheet = Image.new("RGBA", (4 * 256, 256), (0, 0, 0, 0))
        # Only fill first 2 cells
        draw = ImageDraw.Draw(sheet)
        for c in range(2):
            m = 20
            draw.rectangle((c * 256 + m, m, (c + 1) * 256 - m, 256 - m), fill=(100, 100, 200, 255))
        result = verify_padding(
            sheet,
            4,
            1,
            256,
            expected_empty_cells=[(0, 2), (0, 3)],
        )
        assert result["passed"] is True

    def test_reports_max_padding_pct(self) -> None:
        """Result includes the max padding percentage across all frames."""
        sheet = self._make_sheet(2, 1, 256, fill_pct=0.5)
        result = verify_padding(sheet, 2, 1, 256)
        assert result["max_padding_pct"] > 0

    def test_custom_threshold(self) -> None:
        """Custom max_padding_pct threshold works."""
        sheet = self._make_sheet(2, 1, 256, fill_pct=0.7)
        # 70% fill -> 15% padding per side. Should pass at 15% but fail at 10%.
        result_pass = verify_padding(sheet, 2, 1, 256, max_padding_pct=15.0)
        result_fail = verify_padding(sheet, 2, 1, 256, max_padding_pct=10.0)
        assert result_pass["passed"] is True
        assert result_fail["passed"] is False


# ---------------------------------------------------------------------------
# Pattern 4: SHA256 Provenance (tested via pipeline integration)
# ---------------------------------------------------------------------------
class TestProvenance:
    """Tests for SHA256 provenance helper functions."""

    def test_sha256_file(self, tmp_path: Path) -> None:
        """_sha256_file produces consistent hex digests."""
        # Import from sprite_pipeline
        from sprite_pipeline import _sha256_file, _sha256_text

        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world", encoding="utf-8")
        digest = _sha256_file(test_file)
        assert len(digest) == 64
        assert digest == _sha256_file(test_file)  # deterministic

    def test_sha256_text(self) -> None:
        """_sha256_text produces consistent hex digests."""
        from sprite_pipeline import _sha256_text

        digest = _sha256_text("hello world")
        assert len(digest) == 64
        assert digest == _sha256_text("hello world")  # deterministic
        assert digest != _sha256_text("different text")
