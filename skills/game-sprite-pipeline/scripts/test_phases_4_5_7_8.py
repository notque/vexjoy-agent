#!/usr/bin/env python3
"""Tests for Phases 4, 5, 7, 8 of the sprite pipeline overhaul.

Covers:
    - Phase 4: row_job_status init/status/mark/list-pending
    - Phase 5: video_select_frames uniform distribution logic
    - Phase 7: qa_artifacts contact sheet generation on synthetic fixture
    - Phase 8: per-frame timing in sprite_assemble

Run:
    python3 -m pytest skills/game-sprite-pipeline/scripts/test_phases_4_5_7_8.py -x -q
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import qa_artifacts
import row_job_status
import video_select_frames
from sprite_assemble import _resolve_frame_durations


# ---------------------------------------------------------------------------
# Phase 4: row_job_status
# ---------------------------------------------------------------------------
class TestRowJobStatus:
    """Tests for row_job_status manifest CRUD."""

    def test_init_creates_manifest(self, tmp_path: Path) -> None:
        """init creates row-jobs.json with all rows pending."""
        manifest = row_job_status.init_manifest("fighter", tmp_path)
        assert manifest["preset"] == "fighter"
        assert manifest["total_rows"] == 9  # fighter has 9 rows
        assert all(j["status"] == "pending" for j in manifest["jobs"])

        # File written to disk
        path = tmp_path / "row-jobs.json"
        assert path.exists()
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded["total_rows"] == 9

    def test_init_all_presets(self, tmp_path: Path) -> None:
        """init works for all known presets."""
        for preset in ["fighter", "rpg-character", "platformer", "pet"]:
            work = tmp_path / preset
            manifest = row_job_status.init_manifest(preset, work)
            assert manifest["total_rows"] > 0
            assert manifest["preset"] == preset

    def test_mark_updates_status(self, tmp_path: Path) -> None:
        """mark transitions a row to the given status."""
        row_job_status.init_manifest("fighter", tmp_path)
        updated = row_job_status.mark_row(tmp_path, 0, "in-progress")
        assert updated["jobs"][0]["status"] == "in-progress"
        assert updated["jobs"][0]["updated_at"] is not None

    def test_mark_done_with_output_path(self, tmp_path: Path) -> None:
        """mark done sets output_path."""
        row_job_status.init_manifest("fighter", tmp_path)
        updated = row_job_status.mark_row(tmp_path, 2, "done", output_path="/tmp/strip.png")
        assert updated["jobs"][2]["status"] == "done"
        assert updated["jobs"][2]["output_path"] == "/tmp/strip.png"

    def test_mark_failed_with_error(self, tmp_path: Path) -> None:
        """mark failed sets error message."""
        row_job_status.init_manifest("fighter", tmp_path)
        updated = row_job_status.mark_row(tmp_path, 1, "failed", error="backend timeout")
        assert updated["jobs"][1]["status"] == "failed"
        assert updated["jobs"][1]["error"] == "backend timeout"

    def test_mark_invalid_status_raises(self, tmp_path: Path) -> None:
        """mark with invalid status raises ValueError."""
        row_job_status.init_manifest("fighter", tmp_path)
        with pytest.raises(ValueError, match="Invalid status"):
            row_job_status.mark_row(tmp_path, 0, "bogus")

    def test_mark_out_of_range_raises(self, tmp_path: Path) -> None:
        """mark with out-of-range row_index raises ValueError."""
        row_job_status.init_manifest("fighter", tmp_path)
        with pytest.raises(ValueError, match="out of range"):
            row_job_status.mark_row(tmp_path, 99, "done")

    def test_status_summary(self, tmp_path: Path) -> None:
        """get_status_summary returns correct counts."""
        row_job_status.init_manifest("fighter", tmp_path)
        row_job_status.mark_row(tmp_path, 0, "done")
        row_job_status.mark_row(tmp_path, 1, "in-progress")
        row_job_status.mark_row(tmp_path, 2, "failed")

        manifest = row_job_status.load_manifest(tmp_path)
        summary = row_job_status.get_status_summary(manifest)
        assert summary["done"] == 1
        assert summary["in-progress"] == 1
        assert summary["failed"] == 1
        assert summary["pending"] == 6  # 9 - 3

    def test_list_pending_returns_pending_and_failed(self, tmp_path: Path) -> None:
        """list_pending includes both pending and failed rows."""
        row_job_status.init_manifest("fighter", tmp_path)
        row_job_status.mark_row(tmp_path, 0, "done")
        row_job_status.mark_row(tmp_path, 1, "failed")
        row_job_status.mark_row(tmp_path, 2, "in-progress")

        manifest = row_job_status.load_manifest(tmp_path)
        pending = row_job_status.list_pending_rows(manifest)
        states = {j["row_index"] for j in pending}
        assert 1 in states  # failed
        assert 0 not in states  # done
        assert 2 not in states  # in-progress
        assert len(pending) == 7  # 6 pending + 1 failed

    def test_load_missing_manifest_raises(self, tmp_path: Path) -> None:
        """load_manifest raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            row_job_status.load_manifest(tmp_path)

    def test_cli_init(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """CLI init subcommand works."""
        rc = row_job_status.main(["init", "--preset", "fighter", "--output-dir", str(tmp_path)])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["action"] == "init"
        assert out["summary"]["pending"] == 9

    def test_cli_status(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """CLI status subcommand works."""
        row_job_status.init_manifest("fighter", tmp_path)
        rc = row_job_status.main(["status", "--work-dir", str(tmp_path)])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["preset"] == "fighter"

    def test_cli_mark(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """CLI mark subcommand works."""
        row_job_status.init_manifest("fighter", tmp_path)
        rc = row_job_status.main(["mark", "--work-dir", str(tmp_path), "--row", "0", "--status", "done"])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["status"] == "done"

    def test_cli_list_pending(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """CLI list-pending subcommand works."""
        row_job_status.init_manifest("fighter", tmp_path)
        rc = row_job_status.main(["list-pending", "--work-dir", str(tmp_path)])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["pending_count"] == 9


# ---------------------------------------------------------------------------
# Phase 5: video_select_frames
# ---------------------------------------------------------------------------
class TestVideoSelectFrames:
    """Tests for video_select_frames frame selection logic."""

    def test_uniform_selection_count(self) -> None:
        """Uniform selection returns exactly N frames."""
        frames = [Path(f"frame_{i:04d}.png") for i in range(100)]
        indices = video_select_frames.select_uniform(frames, 8)
        assert len(indices) == 8

    def test_uniform_selection_evenly_spaced(self) -> None:
        """Uniform selection produces evenly spaced indices."""
        frames = [Path(f"frame_{i:04d}.png") for i in range(100)]
        indices = video_select_frames.select_uniform(frames, 5)
        # step = 99/4 = 24.75; indices: 0, 25, 50, 74, 99
        assert indices[0] == 0
        assert indices[-1] == 99
        assert len(indices) == 5
        # Verify roughly even spacing (within 1)
        gaps = [indices[i + 1] - indices[i] for i in range(len(indices) - 1)]
        assert max(gaps) - min(gaps) <= 1

    def test_uniform_selection_single(self) -> None:
        """Selecting 1 frame returns the middle frame."""
        frames = [Path(f"frame_{i:04d}.png") for i in range(100)]
        indices = video_select_frames.select_uniform(frames, 1)
        assert indices == [50]

    def test_uniform_selection_exceeds_count(self) -> None:
        """When count >= total, return all indices."""
        frames = [Path(f"frame_{i:04d}.png") for i in range(5)]
        indices = video_select_frames.select_uniform(frames, 10)
        assert indices == [0, 1, 2, 3, 4]

    def test_uniform_selection_empty(self) -> None:
        """Zero count returns empty list."""
        frames = [Path(f"frame_{i:04d}.png") for i in range(10)]
        indices = video_select_frames.select_uniform(frames, 0)
        assert indices == []

    def test_manual_selection_clamps(self) -> None:
        """Manual selection clamps out-of-range indices."""
        frames = [Path(f"frame_{i:04d}.png") for i in range(10)]
        indices = video_select_frames.select_manual(frames, [-1, 5, 99])
        assert indices == [0, 5, 9]

    def test_beat_labels_cycle(self) -> None:
        """Beat labels cycle through the label list."""
        labels = video_select_frames.assign_beat_labels(8)
        assert len(labels) == 8
        assert labels[0] == "anticipation"
        assert labels[1] == "contact"
        assert labels[4] == "anticipation"  # cycles

    def test_select_frames_creates_manifest(self, tmp_path: Path) -> None:
        """select_frames writes selection.json and copies frames."""
        input_dir = tmp_path / "frames"
        input_dir.mkdir()
        for i in range(20):
            img = Image.new("RGBA", (64, 64), (i * 10, 100, 200, 255))
            img.save(input_dir / f"frame_{i:04d}.png")

        output_dir = tmp_path / "selected"
        manifest = video_select_frames.select_frames(
            input_dir=input_dir,
            output_dir=output_dir,
            count=4,
            method="uniform",
        )

        assert manifest["selected_count"] == 4
        assert manifest["total_source_frames"] == 20
        assert len(manifest["frames"]) == 4
        assert (output_dir / "selection.json").exists()
        assert len(list(output_dir.glob("selected_*.png"))) == 4

    def test_select_frames_manual(self, tmp_path: Path) -> None:
        """select_frames with manual method uses specified indices."""
        input_dir = tmp_path / "frames"
        input_dir.mkdir()
        for i in range(10):
            Image.new("RGBA", (32, 32), (i * 25, 0, 0, 255)).save(input_dir / f"frame_{i:04d}.png")

        output_dir = tmp_path / "selected"
        manifest = video_select_frames.select_frames(
            input_dir=input_dir,
            output_dir=output_dir,
            count=3,
            method="manual",
            indices=[0, 5, 9],
        )
        assert manifest["selected_count"] == 3
        source_indices = [f["source_index"] for f in manifest["frames"]]
        assert source_indices == [0, 5, 9]


# ---------------------------------------------------------------------------
# Phase 7: qa_artifacts
# ---------------------------------------------------------------------------
class TestQArtifacts:
    """Tests for qa_artifacts contact sheet / previews / report."""

    @pytest.fixture()
    def synthetic_sheet(self, tmp_path: Path) -> tuple[Path, int, int, int]:
        """Create a synthetic 4x2 spritesheet fixture."""
        cols, rows, cell = 4, 2, 64
        sheet = Image.new("RGBA", (cols * cell, rows * cell), (255, 0, 255, 255))
        from PIL import ImageDraw

        draw = ImageDraw.Draw(sheet)
        for r in range(rows):
            for c in range(cols):
                cx = c * cell + cell // 2
                cy = r * cell + cell // 2
                color = ((r * cols + c) * 30, 100, 200, 255)
                draw.ellipse((cx - 10, cy - 10, cx + 10, cy + 10), fill=color)
        path = tmp_path / "sheet.png"
        sheet.save(path)
        return path, cols, rows, cell

    def test_make_contact_sheet(self, synthetic_sheet: tuple[Path, int, int, int], tmp_path: Path) -> None:
        """Contact sheet is created with correct dimensions."""
        path, cols, rows, cell = synthetic_sheet
        output = tmp_path / "contact.png"
        result = qa_artifacts.make_contact_sheet(
            input_path=path,
            output_path=output,
            cols=cols,
            rows=rows,
            cell_size=cell,
        )
        assert result.exists()
        img = Image.open(result)
        assert img.width > 0
        assert img.height > 0

    def test_make_contact_sheet_with_preset(self, tmp_path: Path) -> None:
        """Contact sheet uses preset state names."""
        cols, rows, cell = 8, 9, 32
        sheet = Image.new("RGBA", (cols * cell, rows * cell), (100, 100, 100, 255))
        from PIL import ImageDraw

        draw = ImageDraw.Draw(sheet)
        for r in range(rows):
            for c in range(cols):
                cx = c * cell + cell // 2
                cy = r * cell + cell // 2
                draw.rectangle((cx - 5, cy - 5, cx + 5, cy + 5), fill=(200, 200, 200, 255))
        path = tmp_path / "fighter_sheet.png"
        sheet.save(path)

        output = tmp_path / "contact.png"
        qa_artifacts.make_contact_sheet(
            input_path=path,
            output_path=output,
            cols=cols,
            rows=rows,
            cell_size=cell,
            preset_name="fighter",
        )
        assert output.exists()

    def test_render_preview_videos(self, synthetic_sheet: tuple[Path, int, int, int], tmp_path: Path) -> None:
        """Preview GIFs are created for non-empty rows."""
        path, cols, rows, cell = synthetic_sheet
        output_dir = tmp_path / "previews"
        paths = qa_artifacts.render_preview_videos(
            input_path=path,
            output_dir=output_dir,
            cols=cols,
            rows=rows,
            cell_size=cell,
        )
        assert len(paths) > 0
        for p in paths:
            assert p.exists()
            assert p.suffix == ".gif"

    def test_generate_qa_report(self, synthetic_sheet: tuple[Path, int, int, int], tmp_path: Path) -> None:
        """QA report is created with per-row metrics."""
        path, cols, rows, cell = synthetic_sheet
        output = tmp_path / "review.json"
        report = qa_artifacts.generate_qa_report(
            input_path=path,
            output_path=output,
            cols=cols,
            rows=rows,
            cell_size=cell,
        )
        assert output.exists()
        assert "rows" in report
        assert len(report["rows"]) == rows
        for row_report in report["rows"]:
            assert "frame_count" in row_report
            assert "identity_consistency" in row_report
            assert "overall_status" in row_report


# ---------------------------------------------------------------------------
# Phase 8: per-frame timing
# ---------------------------------------------------------------------------
class TestPerFrameTiming:
    """Tests for _resolve_frame_durations."""

    def test_uniform_timing_no_dict(self) -> None:
        """Without timing dict, returns uniform durations."""
        durations = _resolve_frame_durations(fps=10, timing=None, grid_cols=4, grid_rows=1, valid_count=4)
        assert durations == [100, 100, 100, 100]

    def test_timing_from_dict(self) -> None:
        """With timing dict, returns per-frame durations."""
        timing = {"idle": [200, 100, 100, 300]}
        durations = _resolve_frame_durations(
            fps=10,
            timing=timing,
            grid_cols=4,
            grid_rows=1,
            valid_count=4,
            state_names=["idle"],
        )
        assert durations == [200, 100, 100, 300]

    def test_timing_multi_row(self) -> None:
        """Multi-row timing flattens correctly."""
        timing = {"idle": [200, 100], "walk": [80, 120]}
        durations = _resolve_frame_durations(
            fps=10,
            timing=timing,
            grid_cols=2,
            grid_rows=2,
            valid_count=4,
            state_names=["idle", "walk"],
        )
        assert durations == [200, 100, 80, 120]

    def test_timing_fallback_for_missing_state(self) -> None:
        """States not in timing dict fall back to uniform."""
        timing = {"idle": [200, 100]}
        durations = _resolve_frame_durations(
            fps=10,
            timing=timing,
            grid_cols=2,
            grid_rows=2,
            valid_count=4,
            state_names=["idle", "unknown"],
        )
        # idle: 200, 100; unknown: 100, 100 (uniform fallback)
        assert durations == [200, 100, 100, 100]
