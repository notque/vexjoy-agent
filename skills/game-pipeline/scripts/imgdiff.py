#!/usr/bin/env python3
"""
imgdiff.py — Pixel-level screenshot comparison using RMS difference.

Usage:
    python3 imgdiff.py baseline.png current.png [--tolerance 5.0] [--diff-out diff.png]

Exit codes:
    0 — PASS (RMS difference within tolerance)
    1 — FAIL (RMS difference exceeds tolerance)
    2 — Error (missing file, wrong format, etc.)

Requires: Pillow (pip install Pillow)
"""

import argparse
import math
import sys
from pathlib import Path


def compute_rms(img_a, img_b):
    """
    Compute Root Mean Square pixel difference between two RGBA images.

    Returns float: 0.0 (identical) to 255.0 (fully opposite).
    """
    if img_a.size != img_b.size:
        raise ValueError(
            f"Image sizes differ: {img_a.size} vs {img_b.size}. "
            "Ensure both screenshots were captured at the same viewport size."
        )

    pixels_a = list(img_a.getdata())
    pixels_b = list(img_b.getdata())

    total = 0.0
    channels = len(pixels_a[0]) if isinstance(pixels_a[0], tuple) else 1

    for pa, pb in zip(pixels_a, pixels_b):
        if isinstance(pa, tuple):
            for ca, cb in zip(pa, pb):
                diff = int(ca) - int(cb)
                total += diff * diff
        else:
            diff = int(pa) - int(pb)
            total += diff * diff

    n = len(pixels_a) * channels
    return math.sqrt(total / n) if n > 0 else 0.0


def write_diff_image(img_a, img_b, diff_path):
    """
    Write a diff image where changed pixels are highlighted in red.
    Unchanged pixels are shown in greyscale at reduced opacity.
    """
    from PIL import Image

    w, h = img_a.size
    diff_img = Image.new("RGBA", (w, h))
    pixels_a = img_a.convert("RGBA").load()
    pixels_b = img_b.convert("RGBA").load()
    diff_pixels = diff_img.load()

    for y in range(h):
        for x in range(w):
            ra, ga, ba, aa = pixels_a[x, y]
            rb, gb, bb, ab = pixels_b[x, y]

            channel_diff = abs(int(ra) - int(rb)) + abs(int(ga) - int(gb)) + abs(int(ba) - int(bb))

            if channel_diff > 10:  # changed pixel — highlight red
                diff_pixels[x, y] = (255, 0, 0, 255)
            else:  # unchanged — greyscale at half brightness
                grey = int((ra + ga + ba) / 3 * 0.4)
                diff_pixels[x, y] = (grey, grey, grey, 255)

    diff_img.save(diff_path)


def main():
    parser = argparse.ArgumentParser(
        description="Compare two screenshots using pixel-level RMS difference.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 imgdiff.py baseline.png current.png
  python3 imgdiff.py baseline.png current.png --tolerance 10.0
  python3 imgdiff.py a.png b.png --tolerance 5.0 --diff-out diff.png
        """,
    )
    parser.add_argument("baseline", help="Path to baseline (reference) image")
    parser.add_argument("current", help="Path to current (comparison) image")
    parser.add_argument(
        "--tolerance",
        "-t",
        type=float,
        default=5.0,
        help="RMS tolerance threshold (default: 5.0). Lower = stricter.",
    )
    parser.add_argument(
        "--diff-out",
        "-d",
        default=None,
        metavar="PATH",
        help="Path to write diff image (default: {current_stem}-diff.png next to current image).",
    )

    args = parser.parse_args()

    # Validate inputs
    baseline_path = Path(args.baseline)
    current_path = Path(args.current)

    if not baseline_path.exists():
        print(f"ERROR: Baseline image not found: {baseline_path}", file=sys.stderr)
        sys.exit(2)
    if not current_path.exists():
        print(f"ERROR: Current image not found: {current_path}", file=sys.stderr)
        sys.exit(2)

    # Import Pillow
    try:
        from PIL import Image
    except ImportError:
        print("ERROR: Pillow is required. Install with: pip install Pillow", file=sys.stderr)
        sys.exit(2)

    # Load images
    try:
        img_a = Image.open(baseline_path).convert("RGBA")
        img_b = Image.open(current_path).convert("RGBA")
    except Exception as e:
        print(f"ERROR: Failed to open image: {e}", file=sys.stderr)
        sys.exit(2)

    # Compute RMS
    try:
        rms = compute_rms(img_a, img_b)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)

    passed = rms <= args.tolerance

    # Determine diff output path
    if args.diff_out:
        diff_path = Path(args.diff_out)
    else:
        diff_path = current_path.parent / f"{current_path.stem}-diff.png"

    # Write diff image on failure (or always if explicitly requested)
    if not passed or args.diff_out:
        try:
            write_diff_image(img_a, img_b, diff_path)
            diff_note = f"  diff: {diff_path}"
        except Exception as e:
            diff_note = f"  diff: (failed to write: {e})"
    else:
        diff_note = ""

    # Output result
    verdict = "PASS" if passed else "FAIL"
    print(f"{verdict}  rms={rms:.4f}  tolerance={args.tolerance:.1f}{diff_note}")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
