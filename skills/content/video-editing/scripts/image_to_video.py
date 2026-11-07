#!/usr/bin/env python3
"""
Combine a static image with audio to create an MP4 video.

Uses FFmpeg subprocess for reliable video encoding.
Supports visualization modes: static, waveform, spectrum.

Workspace mode: Place files in workspace/input/, outputs go to workspace/output/,
processed files move to workspace/completed/.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# Workspace directories (relative to script location)
SCRIPT_DIR = Path(__file__).parent.parent
WORKSPACE_DIR = SCRIPT_DIR / "workspace"
INPUT_DIR = WORKSPACE_DIR / "input"
OUTPUT_DIR = WORKSPACE_DIR / "output"
COMPLETED_DIR = WORKSPACE_DIR / "completed"

# Supported file extensions
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}

# Resolution presets
RESOLUTION_PRESETS = {
    "1080p": (1920, 1080),
    "720p": (1280, 720),
    "square": (1080, 1080),
    "vertical": (1080, 1920),
}

# Visualization modes
VISUALIZATION_MODES = ["static", "waveform", "spectrum", "cqt", "bars"]


def check_ffmpeg() -> bool:
    """Check if FFmpeg is available in PATH."""
    return shutil.which("ffmpeg") is not None


def get_audio_duration(audio_path: Path) -> float:
    """Get audio duration in seconds using ffprobe."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError) as e:
        print(f"ERROR: Could not determine audio duration: {e}")
        return 0.0


def build_ffmpeg_command(
    image_path: Path,
    audio_path: Path,
    output_path: Path,
    width: int,
    height: int,
    visualization: str,
) -> list[str]:
    """Build FFmpeg command based on visualization mode."""

    # Base command with image loop and audio input
    cmd = [
        "ffmpeg",
        "-y",  # Overwrite output
        "-loop",
        "1",
        "-i",
        str(image_path),
        "-i",
        str(audio_path),
    ]

    if visualization == "static":
        # Simple static image with audio
        filter_complex = (
            f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black[v]"
        )
        cmd.extend(
            [
                "-filter_complex",
                filter_complex,
                "-map",
                "[v]",
                "-map",
                "1:a",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "23",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-shortest",
                "-pix_fmt",
                "yuv420p",
                str(output_path),
            ]
        )

    elif visualization == "waveform":
        # Modern neon waveform with glow effect
        wave_height = height // 3
        filter_complex = (
            f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,"
            f"eq=brightness=-0.1:saturation=0.9[bg];"
            # Create waveform with gradient colors (cyan to magenta)
            f"[1:a]showwaves=s={width}x{wave_height}:mode=p2p:rate=30:"
            f"colors=0x00ffff@0.9|0xff00ff@0.9:scale=sqrt[wave1];"
            # Add glow by duplicating and blurring
            f"[wave1]split[w1][w2];"
            f"[w2]gblur=sigma=8,colorchannelmixer=aa=0.5[glow];"
            f"[w1][glow]blend=all_mode=screen[wave];"
            # Overlay at bottom with subtle gradient fade
            f"[bg][wave]overlay=0:H-h-40:format=auto[v]"
        )
        cmd.extend(
            [
                "-filter_complex",
                filter_complex,
                "-map",
                "[v]",
                "-map",
                "1:a",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "23",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-shortest",
                "-pix_fmt",
                "yuv420p",
                str(output_path),
            ]
        )

    elif visualization == "spectrum":
        # Vibrant frequency spectrum with modern color scheme
        spec_height = height // 3
        filter_complex = (
            f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,"
            f"eq=brightness=-0.1:saturation=0.9[bg];"
            # Create spectrum with fire/plasma color scheme
            f"[1:a]showspectrum=s={width}x{spec_height}:mode=combined:"
            f"color=fire:scale=log:slide=scroll:saturation=2:gain=1.5[spec1];"
            # Add subtle glow effect
            f"[spec1]split[s1][s2];"
            f"[s2]gblur=sigma=5,colorchannelmixer=aa=0.4[sglow];"
            f"[s1][sglow]blend=all_mode=screen[spec];"
            # Overlay at bottom
            f"[bg][spec]overlay=0:H-h-20:format=auto[v]"
        )
        cmd.extend(
            [
                "-filter_complex",
                filter_complex,
                "-map",
                "[v]",
                "-map",
                "1:a",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "23",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-shortest",
                "-pix_fmt",
                "yuv420p",
                str(output_path),
            ]
        )

    elif visualization == "cqt":
        # Showcqt - stunning musical visualization (piano-roll style)
        # showcqt requires specific height: bar_h + axis_h + sono_h = height
        # Using fullhd=1 forces 1920x1080 with proper proportions
        filter_complex = (
            f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,"
            f"eq=brightness=-0.15[bg];"
            # showcqt with fullhd mode and vibrant colors
            f"[1:a]showcqt=fullhd=1:"
            f"bar_g=3:sono_g=4:"
            f"bar_v=15:sono_v=12:"
            f"count=4:csp=bt709[cqt1];"
            # Add glow effect for modern look
            f"[cqt1]split[c1][c2];"
            f"[c2]gblur=sigma=12,colorchannelmixer=aa=0.35[cglow];"
            f"[c1][cglow]blend=all_mode=screen[cqt];"
            # Overlay on darkened background
            f"[bg][cqt]overlay=0:H-h:format=auto[v]"
        )
        cmd.extend(
            [
                "-filter_complex",
                filter_complex,
                "-map",
                "[v]",
                "-map",
                "1:a",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "20",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-shortest",
                "-pix_fmt",
                "yuv420p",
                str(output_path),
            ]
        )

    elif visualization == "bars":
        # showfreqs - beautiful frequency bar visualization
        bars_height = height // 2
        filter_complex = (
            f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,"
            f"eq=brightness=-0.1[bg];"
            # showfreqs with bar mode and rainbow colors
            f"[1:a]showfreqs=s={width}x{bars_height}:"
            f"mode=bar:cmode=separate:fscale=log:"
            f"ascale=log:colors=cyan|magenta:"
            f"win_size=2048:win_func=hanning[freq1];"
            # Add glow
            f"[freq1]split[f1][f2];"
            f"[f2]gblur=sigma=8,colorchannelmixer=aa=0.4[fglow];"
            f"[f1][fglow]blend=all_mode=screen[freq];"
            # Overlay at bottom
            f"[bg][freq]overlay=0:H-h-20:format=auto[v]"
        )
        cmd.extend(
            [
                "-filter_complex",
                filter_complex,
                "-map",
                "[v]",
                "-map",
                "1:a",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "20",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-shortest",
                "-pix_fmt",
                "yuv420p",
                str(output_path),
            ]
        )

    return cmd


def create_video(
    image_path: Path,
    audio_path: Path,
    output_path: Path,
    resolution: str,
    visualization: str,
) -> bool:
    """Create video from image and audio."""

    # Validate inputs
    if not image_path.exists():
        print(f"ERROR: Image file not found: {image_path}")
        return False

    if not audio_path.exists():
        print(f"ERROR: Audio file not found: {audio_path}")
        return False

    # Get resolution
    if resolution in RESOLUTION_PRESETS:
        width, height = RESOLUTION_PRESETS[resolution]
    else:
        print(f"ERROR: Unknown resolution preset: {resolution}")
        print(f"Valid presets: {', '.join(RESOLUTION_PRESETS.keys())}")
        return False

    # Get audio duration for progress info
    duration = get_audio_duration(audio_path)

    print("Creating video...")
    print(f"  Image: {image_path}")
    print(f"  Audio: {audio_path}")
    print(f"  Output: {output_path}")
    print(f"  Resolution: {width}x{height} ({resolution})")
    print(f"  Visualization: {visualization}")
    print(f"  Duration: {duration:.1f}s")
    print()

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Build and run FFmpeg command
    cmd = build_ffmpeg_command(image_path, audio_path, output_path, width, height, visualization)

    print(f"$ {' '.join(cmd[:6])} ...")
    print()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print("ERROR: FFmpeg failed")
            print(result.stderr)
            return False

        # Verify output
        if output_path.exists():
            size_mb = output_path.stat().st_size / (1024 * 1024)
            print(f"SUCCESS: Created {output_path}")
            print(f"  File size: {size_mb:.2f} MB")
            return True
        else:
            print("ERROR: Output file was not created")
            return False

    except subprocess.CalledProcessError as e:
        print(f"ERROR: FFmpeg command failed: {e}")
        return False


def find_pairs_in_workspace() -> list[tuple[Path, Path]]:
    """Find matching image+audio pairs in workspace/input/ directory."""
    if not INPUT_DIR.exists():
        return []

    # Collect all files by base name
    images: dict[str, Path] = {}
    audios: dict[str, Path] = {}

    for f in INPUT_DIR.iterdir():
        if f.is_file():
            base = f.stem.lower()
            ext = f.suffix.lower()
            if ext in IMAGE_EXTENSIONS:
                images[base] = f
            elif ext in AUDIO_EXTENSIONS:
                audios[base] = f

    # Find matching pairs
    pairs = []
    for base_name in images:
        if base_name in audios:
            pairs.append((images[base_name], audios[base_name]))

    return pairs


def process_workspace(resolution: str, visualization: str) -> int:
    """Process all matching pairs in workspace/input/ directory."""

    # Ensure directories exist
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    COMPLETED_DIR.mkdir(parents=True, exist_ok=True)

    pairs = find_pairs_in_workspace()

    if not pairs:
        print("=" * 60)
        print(" IMAGE-TO-VIDEO WORKSPACE")
        print("=" * 60)
        print()
        print(f" Input directory: {INPUT_DIR}")
        print()
        print(" No matching image+audio pairs found!")
        print()
        print(" To use this skill:")
        print("   1. Place an image file in workspace/input/")
        print("   2. Place an audio file with the SAME base name")
        print()
        print(" Example:")
        print(f"   {INPUT_DIR}/song.png")
        print(f"   {INPUT_DIR}/song.mp3")
        print()
        print(" Supported formats:")
        print(f"   Images: {', '.join(sorted(IMAGE_EXTENSIONS))}")
        print(f"   Audio:  {', '.join(sorted(AUDIO_EXTENSIONS))}")
        print("=" * 60)
        return 0

    print("=" * 60)
    print(f" PROCESSING {len(pairs)} PAIR(S)")
    print("=" * 60)
    print()

    success_count = 0
    fail_count = 0

    for image_path, audio_path in pairs:
        base_name = image_path.stem
        output_path = OUTPUT_DIR / f"{base_name}.mp4"

        print(f"[{success_count + fail_count + 1}/{len(pairs)}] {base_name}")
        print("-" * 40)

        if create_video(image_path, audio_path, output_path, resolution, visualization):
            # Move processed files to completed
            completed_image = COMPLETED_DIR / image_path.name
            completed_audio = COMPLETED_DIR / audio_path.name

            shutil.move(str(image_path), str(completed_image))
            shutil.move(str(audio_path), str(completed_audio))

            print("  → Moved inputs to completed/")
            success_count += 1
        else:
            fail_count += 1

        print()

    print("=" * 60)
    print(f" COMPLETE: {success_count} succeeded, {fail_count} failed")
    print(f" Output: {OUTPUT_DIR}")
    print("=" * 60)

    return 0 if fail_count == 0 else 2


def main():
    parser = argparse.ArgumentParser(
        description="Combine image and audio to create MP4 video",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --process-workspace
  %(prog)s --process-workspace --visualization waveform
  %(prog)s --image cover.png --audio song.mp3 --output video.mp4
  %(prog)s --image cover.png --audio song.mp3 --output video.mp4 --visualization waveform

Workspace Mode:
  Place files in workspace/input/ with matching names:
    song.png + song.mp3 → song.mp4

  Run: %(prog)s --process-workspace

  Output goes to workspace/output/
  Processed files move to workspace/completed/

Resolutions:
  1080p    1920x1080 (YouTube HD, default)
  720p     1280x720  (Standard HD)
  square   1080x1080 (Instagram, social media)
  vertical 1080x1920 (Stories, Reels, TikTok)

Visualizations:
  static   Just the image for the duration (default)
  waveform Neon waveform with glow effect
  spectrum Scrolling frequency spectrum (fire colors)
  cqt      Piano-roll style bars (most impressive!)
  bars     Frequency bar graph (cyan/magenta)
        """,
    )

    # Workspace mode
    parser.add_argument(
        "--process-workspace",
        "-w",
        action="store_true",
        help="Process all matching pairs in workspace/input/",
    )

    # Single file mode
    parser.add_argument(
        "--image",
        "-i",
        help="Input image file (PNG, JPG, etc.)",
    )
    parser.add_argument(
        "--audio",
        "-a",
        help="Input audio file (MP3, WAV, etc.)",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output video file (.mp4)",
    )
    parser.add_argument(
        "--resolution",
        "-r",
        default="1080p",
        choices=list(RESOLUTION_PRESETS.keys()),
        help="Resolution preset (default: 1080p)",
    )
    parser.add_argument(
        "--visualization",
        "-v",
        default="static",
        choices=VISUALIZATION_MODES,
        help="Visualization mode (default: static)",
    )

    args = parser.parse_args()

    # Check FFmpeg availability
    if not check_ffmpeg():
        print("ERROR: FFmpeg is not installed or not in PATH")
        print()
        print("Install FFmpeg:")
        print("  macOS:   brew install ffmpeg")
        print("  Ubuntu:  sudo apt install ffmpeg")
        print("  Windows: choco install ffmpeg")
        print()
        print("Or download from: https://ffmpeg.org/download.html")
        sys.exit(1)

    # Workspace mode
    if args.process_workspace:
        exit_code = process_workspace(args.resolution, args.visualization)
        sys.exit(exit_code)

    # Single file mode - require all arguments
    if not args.image or not args.audio or not args.output:
        print("ERROR: --image, --audio, and --output required (or use --process-workspace)")
        parser.print_help()
        sys.exit(3)

    # Convert to Path objects
    image_path = Path(args.image).resolve()
    audio_path = Path(args.audio).resolve()
    output_path = Path(args.output).resolve()

    # Create video
    success = create_video(
        image_path,
        audio_path,
        output_path,
        args.resolution,
        args.visualization,
    )

    if success:
        print()
        print("DONE")
        sys.exit(0)
    else:
        sys.exit(2)


if __name__ == "__main__":
    main()
