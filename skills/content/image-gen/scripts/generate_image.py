#!/usr/bin/env python3
"""
Generate images using Google Gemini APIs.

Uses gemini-3-pro-image-preview (quality) or gemini-2.5-flash-image (speed).
Supports optional post-processing: watermark removal and background transparency.
"""

import argparse
import os
import sys
import time
from pathlib import Path

# Valid model names - DO NOT ADD DATE SUFFIXES
VALID_MODELS = [
    "gemini-2.5-flash-image",
    "gemini-3-pro-image-preview",
]

# Default post-processing settings
DEFAULT_BG_COLOR = (58, 58, 58)  # #3a3a3a
DEFAULT_BG_TOLERANCE = 30
WATERMARK_MARGIN = 40

# Defer import checks until after argument parsing (allows --help to work)
genai = None
types = None
Image = None
PIL_AVAILABLE = False


def _check_imports():
    """Import required packages, checking availability."""
    global genai, types, Image, PIL_AVAILABLE

    try:
        from google import genai as _genai
        from google.genai import types as _types

        genai = _genai
        types = _types
    except ImportError:
        print("ERROR: google-genai package not installed")
        print("Install with: pip install google-genai")
        sys.exit(1)

    try:
        from PIL import Image as _Image

        Image = _Image
        PIL_AVAILABLE = True
    except ImportError:
        PIL_AVAILABLE = False


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color string to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def remove_watermark(img, bg_color: tuple[int, int, int]):
    """Remove watermarks from corners by replacing bright pixels with background."""
    img = img.convert("RGBA")
    pixels = img.load()
    width, height = img.size

    corners = [
        (0, 0, WATERMARK_MARGIN, WATERMARK_MARGIN),
        (width - WATERMARK_MARGIN, 0, width, WATERMARK_MARGIN),
        (0, height - WATERMARK_MARGIN, WATERMARK_MARGIN, height),
        (width - WATERMARK_MARGIN, height - WATERMARK_MARGIN, width, height),
    ]

    removed = 0
    for x1, y1, x2, y2 in corners:
        for y in range(y1, y2):
            for x in range(x1, x2):
                if 0 <= x < width and 0 <= y < height:
                    r, g, b, _a = pixels[x, y]
                    brightness = (r + g + b) / 3
                    if brightness > 180:
                        pixels[x, y] = (bg_color[0], bg_color[1], bg_color[2], 255)
                        removed += 1

    if removed > 0:
        print(f"  Removed {removed} watermark pixels")
    return img


def make_background_transparent(img, bg_color: tuple[int, int, int], tolerance: int):
    """Make pixels matching background color transparent."""
    img = img.convert("RGBA")
    pixels = img.load()
    width, height = img.size

    transparent_count = 0
    for y in range(height):
        for x in range(width):
            r, g, b, _a = pixels[x, y]
            if (
                abs(r - bg_color[0]) <= tolerance
                and abs(g - bg_color[1]) <= tolerance
                and abs(b - bg_color[2]) <= tolerance
            ):
                pixels[x, y] = (r, g, b, 0)
                transparent_count += 1

    print(f"  Made {transparent_count} background pixels transparent")
    return img


def process_image(
    input_path: Path,
    output_path: Path,
    remove_wm: bool,
    transparent: bool,
    bg_color: tuple[int, int, int],
    bg_tolerance: int,
) -> bool:
    """Apply post-processing to generated image."""
    if not PIL_AVAILABLE:
        print("WARNING: Pillow not installed, skipping post-processing")
        print("Install with: pip install Pillow")
        return False

    try:
        img = Image.open(input_path)
        print(f"  Processing {input_path.name} ({img.size[0]}x{img.size[1]})")

        if remove_wm:
            img = remove_watermark(img, bg_color)

        if transparent:
            img = make_background_transparent(img, bg_color, bg_tolerance)

        img.save(output_path, "PNG", optimize=True)
        print(f"  Saved: {output_path}")
        return True

    except Exception as e:
        print(f"  Error processing: {e}")
        return False


def generate_image(
    prompt: str,
    output_path: Path,
    model: str,
    retries: int = 3,
) -> bool:
    """Generate an image using Gemini API."""
    client = genai.Client()

    print("Generating image...")
    print(f"  Model: {model}")
    print(f"  Prompt: {prompt[:80]}{'...' if len(prompt) > 80 else ''}")
    print(f"  Output: {output_path}")

    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"],
                ),
            )

            # Extract image from response
            if not response.candidates:
                print("  ERROR: No candidates in response")
                return False

            parts = getattr(response.candidates[0].content, "parts", None)
            if not parts:
                print("  ERROR: No parts in response")
                return False

            for part in parts:
                if part.inline_data is not None:
                    image_data = part.inline_data.data
                    with open(output_path, "wb") as f:
                        f.write(image_data)
                    print(f"  SUCCESS: Saved to {output_path}")
                    return True

            print("  ERROR: No image in response")
            return False

        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "rate" in error_str.lower():
                wait_time = (attempt + 1) * 5
                print(f"  Rate limited, waiting {wait_time}s (attempt {attempt + 1}/{retries})")
                time.sleep(wait_time)
            elif "400" in error_str:
                print("  ERROR: Content policy violation or invalid request")
                print(f"  Details: {e}")
                return False
            else:
                if attempt < retries - 1:
                    wait_time = (attempt + 1) * 2
                    print(f"  Error: {e}")
                    print(f"  Retrying in {wait_time}s (attempt {attempt + 1}/{retries})")
                    time.sleep(wait_time)
                else:
                    print(f"  ERROR after {retries} attempts: {e}")
                    return False

    return False


def generate_batch(
    prompt_file: Path,
    output_dir: Path,
    model: str,
    delay: float,
    retries: int,
    process_opts: dict,
) -> tuple[int, int]:
    """Generate multiple images from a prompt file."""
    if not prompt_file.exists():
        print(f"ERROR: Prompt file not found: {prompt_file}")
        return 0, 0

    output_dir.mkdir(parents=True, exist_ok=True)

    prompts = []
    with open(prompt_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                prompts.append(line)

    print(f"Batch generation: {len(prompts)} prompts")
    print(f"Output directory: {output_dir}")
    print()

    success = 0
    failed = 0

    for i, prompt in enumerate(prompts, 1):
        output_path = output_dir / f"output_{i:03d}.png"
        print(f"[{i}/{len(prompts)}] Generating...")

        if generate_image(prompt, output_path, model, retries):
            # Post-processing if requested
            if process_opts["remove_wm"] or process_opts["transparent"]:
                process_image(
                    output_path,
                    output_path,
                    process_opts["remove_wm"],
                    process_opts["transparent"],
                    process_opts["bg_color"],
                    process_opts["bg_tolerance"],
                )
            success += 1
        else:
            failed += 1

        # Rate limiting between requests
        if i < len(prompts):
            print(f"  Waiting {delay}s before next request...")
            time.sleep(delay)

        print()

    return success, failed


def main():
    parser = argparse.ArgumentParser(
        description="Generate images using Google Gemini APIs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --prompt "A cute cat" --output cat.png
  %(prog)s --prompt "Game sprite" --output sprite.png --model gemini-2.5-flash-image
  %(prog)s --prompt "Character art" --output char.png --remove-watermark --transparent-bg
  %(prog)s --batch prompts.txt --output-dir ./images/

Models:
  gemini-2.5-flash-image     Fast iterations, drafts, high volume
  gemini-3-pro-image-preview Quality output, text rendering, 2K resolution
        """,
    )

    # Generation options
    parser.add_argument("--prompt", help="Text prompt for image generation")
    parser.add_argument("--output", help="Output file path (.png)")
    parser.add_argument(
        "--model",
        default="gemini-3-pro-image-preview",
        choices=VALID_MODELS,
        help="Model to use (default: gemini-3-pro-image-preview)",
    )

    # Batch options
    parser.add_argument("--batch", help="File with prompts (one per line)")
    parser.add_argument("--output-dir", help="Directory for batch output")

    # Post-processing options
    parser.add_argument(
        "--remove-watermark",
        action="store_true",
        help="Remove watermarks from corners",
    )
    parser.add_argument(
        "--transparent-bg",
        action="store_true",
        help="Make background transparent",
    )
    parser.add_argument(
        "--bg-color",
        default="#3a3a3a",
        help="Background color for transparency (hex, default: #3a3a3a)",
    )
    parser.add_argument(
        "--bg-tolerance",
        type=int,
        default=DEFAULT_BG_TOLERANCE,
        help=f"Color matching tolerance (default: {DEFAULT_BG_TOLERANCE})",
    )

    # Retry/timing options
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Max retry attempts (default: 3)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=3.0,
        help="Delay between batch requests in seconds (default: 3)",
    )

    args = parser.parse_args()

    # Now check imports (after --help can work)
    _check_imports()

    # Validate API key
    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY environment variable not set")
        print("Set with: export GEMINI_API_KEY='your-api-key'")
        sys.exit(1)

    # Parse background color
    try:
        bg_color = hex_to_rgb(args.bg_color)
    except (ValueError, IndexError):
        print(f"ERROR: Invalid background color: {args.bg_color}")
        print("Use hex format: #RRGGBB")
        sys.exit(3)

    process_opts = {
        "remove_wm": args.remove_watermark,
        "transparent": args.transparent_bg,
        "bg_color": bg_color,
        "bg_tolerance": args.bg_tolerance,
    }

    # Batch mode
    if args.batch:
        if not args.output_dir:
            print("ERROR: --output-dir required with --batch")
            sys.exit(3)

        success, failed = generate_batch(
            Path(args.batch),
            Path(args.output_dir),
            args.model,
            args.delay,
            args.retries,
            process_opts,
        )

        print("=" * 40)
        print(f"BATCH COMPLETE: {success} succeeded, {failed} failed")
        sys.exit(0 if failed == 0 else 2)

    # Single image mode
    if not args.prompt or not args.output:
        print("ERROR: --prompt and --output required (or use --batch)")
        parser.print_help()
        sys.exit(3)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate image
    if not generate_image(args.prompt, output_path, args.model, args.retries):
        sys.exit(2)

    # Post-processing
    if args.remove_watermark or args.transparent_bg:
        if not process_image(
            output_path,
            output_path,
            args.remove_watermark,
            args.transparent_bg,
            bg_color,
            args.bg_tolerance,
        ):
            print("WARNING: Post-processing failed, raw image saved")

    print()
    print("DONE")
    sys.exit(0)


if __name__ == "__main__":
    main()
