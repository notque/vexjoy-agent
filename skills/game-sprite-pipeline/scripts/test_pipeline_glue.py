#!/usr/bin/env python3
"""Smoke tests for pipeline-glue bugs surfaced on PR #529.

These tests exercise glue code that the in-skill verifier gates (which all
operate on already-rendered images) cannot reach: argv forwarding through
orchestration scripts, mode dispatch in remove-bg, the count-mismatch guard
in extract-frames cell-aware mode, and the aspect-ratio choice in the
portrait-loop generate phase.

Each test is a thin, fast, deterministic check that a specific Codex finding
no longer reproduces. Run:

    python3 skills/game-sprite-pipeline/scripts/test_pipeline_glue.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest import mock

import numpy as np
import pytest
from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import portrait_pipeline
import sprite_pipeline
import sprite_process


# ---------------------------------------------------------------------------
# Bug #4: --style-string must be forwarded through spritesheet orchestration
# ---------------------------------------------------------------------------
def test_sprite_pipeline_forwards_style_string_to_build_character() -> None:
    """build-character (Phase A) call must include --style-string when set."""
    captured: list[list[str]] = []

    def fake_prompt_main(argv: list[str]) -> int:
        captured.append(list(argv))
        # sprite_prompt outputs land in --output paths; create empty stubs so
        # later phases that cat/read them don't blow up before we early-exit.
        for i, tok in enumerate(argv):
            if tok == "--output" and i + 1 < len(argv):
                Path(argv[i + 1]).parent.mkdir(parents=True, exist_ok=True)
                Path(argv[i + 1]).write_text("stub prompt", encoding="utf-8")
        return 0

    with tempfile.TemporaryDirectory() as td:
        argv = [
            "--prompt",
            "wrestler walk cycle",
            "--style",
            "custom",
            "--style-string",
            "neon-noir oil painting",
            "--grid",
            "4x1",
            "--cell-size",
            "256",
            "--output-dir",
            td,
            "--dry-run",
        ]
        with mock.patch.object(sprite_pipeline.sprite_prompt, "main", side_effect=fake_prompt_main):
            sprite_pipeline.main(argv)

    # First captured call is the build-character (Phase A). Walk forward to find it.
    char_calls = [c for c in captured if c and c[0] == "build-character"]
    assert char_calls, f"expected at least one build-character call, got {captured}"
    char_argv = char_calls[0]
    assert "--style-string" in char_argv, f"--style-string missing from build-character: {char_argv}"
    idx = char_argv.index("--style-string")
    assert char_argv[idx + 1] == "neon-noir oil painting", char_argv

    sheet_calls = [c for c in captured if c and c[0] == "build-spritesheet"]
    assert sheet_calls, f"expected build-spritesheet call, got {captured}"
    sheet_argv = sheet_calls[0]
    assert "--style-string" in sheet_argv, f"--style-string missing from build-spritesheet: {sheet_argv}"
    idx = sheet_argv.index("--style-string")
    assert sheet_argv[idx + 1] == "neon-noir oil painting", sheet_argv


# ---------------------------------------------------------------------------
# Bug #5: --style-string must be forwarded through portrait-loop orchestration
# ---------------------------------------------------------------------------
def test_portrait_pipeline_forwards_style_string_to_build_portrait_loop() -> None:
    """portrait-loop's build-portrait-loop call must include --style-string."""
    captured: list[list[str]] = []

    def fake_prompt_main(argv: list[str]) -> int:
        captured.append(list(argv))
        for i, tok in enumerate(argv):
            if tok in ("--output", "--metadata-out") and i + 1 < len(argv):
                Path(argv[i + 1]).parent.mkdir(parents=True, exist_ok=True)
                Path(argv[i + 1]).write_text("stub", encoding="utf-8")
        return 0

    with tempfile.TemporaryDirectory() as td:
        argv = [
            "--mode",
            "portrait-loop",
            "--description",
            "test character",
            "--display-name",
            "Test Loop",
            "--style",
            "custom",
            "--style-string",
            "moody charcoal sketch",
            "--output-dir",
            td,
            "--dry-run",
        ]
        with mock.patch.object(portrait_pipeline.sprite_prompt, "main", side_effect=fake_prompt_main):
            # Don't care if downstream phases fail; we only need the prompt phase to fire.
            try:
                portrait_pipeline.main(argv)
            except SystemExit:
                pass

    loop_calls = [c for c in captured if c and c[0] == "build-portrait-loop"]
    assert loop_calls, f"expected build-portrait-loop call, got {captured}"
    loop_argv = loop_calls[0]
    assert "--style-string" in loop_argv, f"--style-string missing from build-portrait-loop: {loop_argv}"
    idx = loop_argv.index("--style-string")
    assert loop_argv[idx + 1] == "moody charcoal sketch", loop_argv


# ---------------------------------------------------------------------------
# Bug #3: --bg-mode gray-tolerance must reach remove_bg_gray_tolerance
# ---------------------------------------------------------------------------
def test_bg_mode_gray_tolerance_routes_to_gray_tolerance(tmp_path: Path) -> None:
    """A solid #3a3a3a image with --bg-mode gray-tolerance must zero its alpha."""
    # 64x64 of pure #3a3a3a (the default GRAY_BG) on opaque alpha.
    src = tmp_path / "gray_bg.png"
    img = Image.new("RGBA", (64, 64), (0x3A, 0x3A, 0x3A, 255))
    img.save(src)
    dst = tmp_path / "gray_bg_nobg.png"

    rc = sprite_process.main(
        [
            "remove-bg",
            str(src),
            "--output",
            str(dst),
            "--bg-mode",
            "gray-tolerance",
        ]
    )
    assert rc == 0, f"remove-bg returned {rc}"
    out = np.array(Image.open(dst).convert("RGBA"))
    transparent = (out[..., 3] == 0).sum()
    total = out.shape[0] * out.shape[1]
    # Pre-fix: 0 transparent pixels (fell into magenta branch). Post-fix: ~all
    # pixels go transparent, modulo the watermark-margin guard. Require >=80%.
    assert transparent / total >= 0.80, (
        f"gray-tolerance did not zero the #3a3a3a background: "
        f"transparent={transparent}/{total} ({transparent / total:.1%})"
    )


# ---------------------------------------------------------------------------
# Bug #2: --cell-aware count-mismatch guard must fire on missing components
# ---------------------------------------------------------------------------
def test_extract_frames_cell_aware_count_mismatch_is_reachable(tmp_path: Path) -> None:
    """Cell-aware mode must return rc=5 when components < expected grid count.

    Build a 2x2 grid where 3 of 4 cells are empty (no chroma-keyed content). The
    pre-fix outer guard `len(ordered) != expected` was always False in cell-aware
    mode (assign_components_to_cells always returns expected-length list, with
    None for empty cells), so the inner non-None check was unreachable.
    """
    sheet_size = 256
    cell = sheet_size // 2
    # Magenta background everywhere. Place ONE white blob in cell (0, 0).
    arr = np.full((sheet_size, sheet_size, 3), (255, 0, 255), dtype=np.uint8)
    cy, cx = cell // 2, cell // 2
    arr[cy - 8 : cy + 8, cx - 8 : cx + 8] = (255, 255, 255)
    sheet_path = tmp_path / "one_blob.png"
    Image.fromarray(arr, "RGB").save(sheet_path)

    out_dir = tmp_path / "frames"
    rc = sprite_process.main(
        [
            "extract-frames",
            "--input",
            str(sheet_path),
            "--grid",
            "2x2",
            "--output-dir",
            str(out_dir),
            "--cell-aware",
        ]
    )
    assert rc == 5, f"expected rc=5 (count mismatch), got rc={rc}"


def test_extract_frames_cell_aware_full_grid_passes(tmp_path: Path) -> None:
    """Sanity: cell-aware with all 4 cells populated must still pass (rc=0)."""
    sheet_size = 256
    cell = sheet_size // 2
    arr = np.full((sheet_size, sheet_size, 3), (255, 0, 255), dtype=np.uint8)
    for r in range(2):
        for c in range(2):
            cy = r * cell + cell // 2
            cx = c * cell + cell // 2
            arr[cy - 8 : cy + 8, cx - 8 : cx + 8] = (255, 255, 255)
    sheet_path = tmp_path / "full_grid.png"
    Image.fromarray(arr, "RGB").save(sheet_path)

    out_dir = tmp_path / "frames"
    rc = sprite_process.main(
        [
            "extract-frames",
            "--input",
            str(sheet_path),
            "--grid",
            "2x2",
            "--output-dir",
            str(out_dir),
            "--cell-aware",
        ]
    )
    assert rc == 0, f"expected rc=0 (4/4 cells populated), got rc={rc}"


# ---------------------------------------------------------------------------
# Bug #1: portrait-loop generate phase must request a square (1:1) image
# ---------------------------------------------------------------------------
def test_portrait_loop_uses_generate_character_not_generate_portrait() -> None:
    """portrait-loop produces a 2x2 grid; the generate phase must NOT call the
    `generate-portrait` subcommand because it forces 4:5 aspect ratio. It must
    call `generate-character` (1:1) instead so the backend returns a square."""
    captured: list[list[str]] = []

    def fake_generate_main(argv: list[str]) -> int:
        captured.append(list(argv))
        # Synthesize a 1024x1024 square fixture so downstream slicing succeeds.
        for i, tok in enumerate(argv):
            if tok == "--output" and i + 1 < len(argv):
                out = Path(argv[i + 1])
                out.parent.mkdir(parents=True, exist_ok=True)
                Image.new("RGBA", (1024, 1024), (255, 0, 255, 255)).save(out)
        return 0

    def fake_prompt_main(argv: list[str]) -> int:
        for i, tok in enumerate(argv):
            if tok in ("--output", "--metadata-out") and i + 1 < len(argv):
                Path(argv[i + 1]).parent.mkdir(parents=True, exist_ok=True)
                Path(argv[i + 1]).write_text("stub", encoding="utf-8")
        return 0

    with tempfile.TemporaryDirectory() as td:
        argv = [
            "--mode",
            "portrait-loop",
            "--description",
            "test character",
            "--display-name",
            "Aspect Test",
            "--output-dir",
            td,
            # Note: NOT --dry-run, because dry-run skips the generate path.
        ]
        with (
            mock.patch.object(portrait_pipeline.sprite_prompt, "main", side_effect=fake_prompt_main),
            mock.patch.object(portrait_pipeline.sprite_generate, "main", side_effect=fake_generate_main),
        ):
            try:
                portrait_pipeline.main(argv)
            except SystemExit:
                pass

    assert captured, "expected at least one sprite_generate call"
    subcmd = captured[0][0]
    assert subcmd == "generate-character", (
        f"portrait-loop must use generate-character (1:1), got {subcmd!r}. "
        f"generate-portrait forces 4:5 and crops the 2x2 grid."
    )


# ---------------------------------------------------------------------------
# ADR-199: --verify is default-on; --no-verify opts out.
# These tests assert the wiring stays.
# ---------------------------------------------------------------------------
def _stub_prompt_main_factory() -> object:
    """Build a fake sprite_prompt.main that writes stub --output / --metadata-out files."""

    def fake_prompt_main(argv: list[str]) -> int:
        for i, tok in enumerate(argv):
            if tok in ("--output", "--metadata-out") and i + 1 < len(argv):
                Path(argv[i + 1]).parent.mkdir(parents=True, exist_ok=True)
                Path(argv[i + 1]).write_text("stub", encoding="utf-8")
        return 0

    return fake_prompt_main


def test_sprite_pipeline_verify_default_on_emits_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """ADR-199: a default sprite_pipeline run produces a verifier JSON block on stdout."""
    fake_prompt = _stub_prompt_main_factory()
    argv = [
        "--prompt",
        "wrestler walk cycle",
        "--grid",
        "4x1",
        "--cell-size",
        "256",
        "--output-dir",
        str(tmp_path),
        "--dry-run",
    ]
    with mock.patch.object(sprite_pipeline.sprite_prompt, "main", side_effect=fake_prompt):
        sprite_pipeline.main(argv)
    out = capsys.readouterr().out
    assert out.strip().startswith("{") and out.strip().endswith("}"), (
        f"expected verifier JSON block on stdout, got first 200 chars: {out[:200]!r}"
    )
    payload = json.loads(out)
    assert "passed" in payload
    assert "gates_run" in payload and len(payload["gates_run"]) > 0, payload
    # The full spritesheet gate suite (minus pixel_preservation when raw is
    # absent) should be invoked; assert the irreducible four are present.
    for gate in (
        "verify_no_magenta",
        "verify_grid_alignment",
        "verify_frames_have_content",
        "verify_anchor_consistency",
    ):
        assert gate in payload["gates_run"], f"{gate} missing from gates_run: {payload['gates_run']}"
    assert "backends_available" in payload
    assert "elapsed_seconds" in payload


def test_sprite_pipeline_no_verify_skips_gates(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """--no-verify must skip all gates (no JSON on stdout) and exit 0."""
    fake_prompt = _stub_prompt_main_factory()
    argv = [
        "--prompt",
        "wrestler walk cycle",
        "--grid",
        "4x1",
        "--cell-size",
        "256",
        "--output-dir",
        str(tmp_path),
        "--dry-run",
        "--no-verify",
    ]
    with mock.patch.object(sprite_pipeline.sprite_prompt, "main", side_effect=fake_prompt):
        rc = sprite_pipeline.main(argv)
    assert rc == 0, f"expected rc=0 with --no-verify (gates skipped), got {rc}"
    out = capsys.readouterr().out
    assert out.strip() == "", f"expected no JSON on stdout with --no-verify, got: {out!r}"


def test_sprite_pipeline_verify_failure_returns_exit_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The dry-run synthetic fixture has 4 near-identical figures, which trips
    verify_frames_distinct. The pipeline must surface that as exit code 2 and
    a passed=false JSON block (per ADR-199 exit-code contract)."""
    fake_prompt = _stub_prompt_main_factory()
    argv = [
        "--prompt",
        "wrestler walk cycle",
        "--grid",
        "4x1",
        "--cell-size",
        "256",
        "--output-dir",
        str(tmp_path),
        "--dry-run",
    ]
    with mock.patch.object(sprite_pipeline.sprite_prompt, "main", side_effect=fake_prompt):
        rc = sprite_pipeline.main(argv)
    assert rc == sprite_pipeline.VERIFIER_EXIT_CODE == 2, f"expected verifier-failure rc=2, got {rc}"
    payload = json.loads(capsys.readouterr().out)
    assert payload["passed"] is False, payload
    assert payload["failures"], "expected non-empty failures list when passed=false"
    failed_checks = {f["check"] for f in payload["failures"]}
    # The synthetic fixture's most reliable failure is frames_distinct (all
    # 4 cells use rotating colors but identical silhouettes). Other gates
    # may also fail; we only require the dups gate as a stable signal.
    assert "verify_frames_distinct" in failed_checks, (
        f"frames_distinct should fail on synthetic fixture: {failed_checks}"
    )


def test_portrait_pipeline_verify_default_on_emits_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Default portrait run emits the verifier JSON block on stdout."""
    fake_prompt = _stub_prompt_main_factory()
    argv = [
        "--description",
        "test character",
        "--display-name",
        "Verify Default",
        "--style",
        "slay-the-spire-painted",
        "--output-dir",
        str(tmp_path),
        "--dry-run",
    ]
    with mock.patch.object(portrait_pipeline.sprite_prompt, "main", side_effect=fake_prompt):
        portrait_pipeline.main(argv)
    out = capsys.readouterr().out
    assert out.strip().startswith("{"), f"expected JSON on stdout: {out[:200]!r}"
    payload = json.loads(out)
    assert "verify_no_magenta" in payload["gates_run"], payload
    # Portrait mode runs ONLY verify_no_magenta (per the run_pipeline
    # docstring rationale around verify_pixel_preservation).
    assert payload["gates_run"] == ["verify_no_magenta"], payload["gates_run"]


def test_portrait_pipeline_no_verify_skips_gates(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """portrait --no-verify writes no JSON and exits 0."""
    fake_prompt = _stub_prompt_main_factory()
    argv = [
        "--description",
        "test character",
        "--display-name",
        "Verify Skip",
        "--style",
        "slay-the-spire-painted",
        "--output-dir",
        str(tmp_path),
        "--dry-run",
        "--no-verify",
    ]
    with mock.patch.object(portrait_pipeline.sprite_prompt, "main", side_effect=fake_prompt):
        rc = portrait_pipeline.main(argv)
    assert rc == 0, f"expected rc=0 with --no-verify, got {rc}"
    out = capsys.readouterr().out
    assert out.strip() == "", f"expected no JSON on stdout with --no-verify, got: {out!r}"


def test_portrait_loop_verify_default_on_emits_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """portrait-loop default-on emits JSON with all 4 portrait-loop gates."""
    fake_prompt = _stub_prompt_main_factory()
    argv = [
        "--mode",
        "portrait-loop",
        "--description",
        "test character",
        "--display-name",
        "Loop Verify",
        "--style",
        "slay-the-spire-painted",
        "--output-dir",
        str(tmp_path),
        "--dry-run",
    ]
    with mock.patch.object(portrait_pipeline.sprite_prompt, "main", side_effect=fake_prompt):
        portrait_pipeline.main(argv)
    out = capsys.readouterr().out
    assert out.strip().startswith("{"), f"expected JSON on stdout: {out[:200]!r}"
    payload = json.loads(out)
    expected_gates = {
        "verify_no_magenta",
        "verify_frames_have_content",
        "verify_frames_distinct",
        "verify_anchor_consistency",
    }
    assert set(payload["gates_run"]) == expected_gates, (
        f"portrait-loop gates mismatch. expected={expected_gates} got={set(payload['gates_run'])}"
    )


def test_portrait_loop_no_verify_skips_gates(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """portrait-loop --no-verify writes no JSON and exits 0."""
    fake_prompt = _stub_prompt_main_factory()
    argv = [
        "--mode",
        "portrait-loop",
        "--description",
        "test character",
        "--display-name",
        "Loop Skip",
        "--style",
        "slay-the-spire-painted",
        "--output-dir",
        str(tmp_path),
        "--dry-run",
        "--no-verify",
    ]
    with mock.patch.object(portrait_pipeline.sprite_prompt, "main", side_effect=fake_prompt):
        rc = portrait_pipeline.main(argv)
    assert rc == 0, f"expected rc=0 with --no-verify, got {rc}"
    out = capsys.readouterr().out
    assert out.strip() == "", f"expected no JSON on stdout with --no-verify, got: {out!r}"


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------
def main() -> int:
    no_arg_tests = [
        test_sprite_pipeline_forwards_style_string_to_build_character,
        test_portrait_pipeline_forwards_style_string_to_build_portrait_loop,
        test_portrait_loop_uses_generate_character_not_generate_portrait,
    ]
    tmp_tests = [
        test_bg_mode_gray_tolerance_routes_to_gray_tolerance,
        test_extract_frames_cell_aware_count_mismatch_is_reachable,
        test_extract_frames_cell_aware_full_grid_passes,
    ]
    failures: list[tuple[str, str]] = []
    for t in no_arg_tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}")
            failures.append((t.__name__, str(e)))
    for t in tmp_tests:
        with tempfile.TemporaryDirectory() as td:
            try:
                t(Path(td))
                print(f"PASS {t.__name__}")
            except AssertionError as e:
                print(f"FAIL {t.__name__}: {e}")
                failures.append((t.__name__, str(e)))
    if failures:
        print(f"\n{len(failures)} FAIL")
        return 1
    print(f"\nAll {len(no_arg_tests) + len(tmp_tests)} tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
