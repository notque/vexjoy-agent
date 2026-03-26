#!/usr/bin/env python3
"""
Generate images using Google Gemini Nano Banana APIs.

Subcommands:
    generate        Single image from a text prompt
    batch           Multiple images from a JSON manifest
    with-reference  Generate with a reference image for style matching

Models:
    flash   gemini-2.5-flash-image    (fast, 2-5s, standard quality)
    pro     gemini-3-pro-image-preview (slow, ~30s, highest quality)

Aspect ratios:
    1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9

Examples:
    # Single generation
    python3 scripts/nano-banana-generate.py generate \\
        --prompt "A wrestling character in Slay the Spire style" \\
        --output output.png --model flash --aspect-ratio 1:1

    # Batch from manifest
    python3 scripts/nano-banana-generate.py batch \\
        --manifest enemies.json --output-dir staging/sprites/ \\
        --model pro --skip-existing --delay 3

    # With reference image
    python3 scripts/nano-banana-generate.py with-reference \\
        --prompt "Recreate in this style" --reference ref.png \\
        --output styled.png --model flash --aspect-ratio 16:9

Requires: pip install google-genai pillow
Env: GEMINI_API_KEY (or GOOGLE_API_KEY for auto-detection)
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

try:
    import io

    from google import genai
    from google.genai import types
    from PIL import Image
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install with: pip install google-genai pillow")
    sys.exit(1)

VALID_MODELS = {
    "flash": "gemini-2.5-flash-image",
    "pro": "gemini-3-pro-image-preview",
}

VALID_RATIOS = ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"]


def get_client() -> genai.Client:
    """Create Gemini client, preferring GEMINI_API_KEY."""
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("ERROR: Set GEMINI_API_KEY or GOOGLE_API_KEY environment variable")
        sys.exit(1)
    return genai.Client(api_key=api_key)


def generate_single(
    client: genai.Client,
    prompt: str,
    output_path: Path,
    model: str = "flash",
    aspect_ratio: str | None = None,
    reference_path: Path | None = None,
    save_original: Path | None = None,
) -> bool:
    """Generate a single image and save it.

    Args:
        client: Gemini API client
        prompt: Text prompt for generation
        output_path: Where to save the output
        model: "flash" or "pro"
        aspect_ratio: One of VALID_RATIOS (None = model default)
        reference_path: Optional reference image for style matching
        save_original: If set, save raw API output here before any other processing

    Returns:
        True if image was generated and saved successfully
    """
    model_name = VALID_MODELS[model]
    print(f"Generating: {output_path.name} (model={model_name})")
    if aspect_ratio:
        print(f"  Aspect ratio: {aspect_ratio}")

    # Validate reference image if provided
    contents = [prompt]
    if reference_path:
        if not reference_path.exists():
            print(f"  ERROR: Reference image not found: {reference_path}")
            return False
        try:
            ref_image = Image.open(reference_path)
            if ref_image.mode != "RGB":
                ref_image = ref_image.convert("RGB")
            contents = [prompt, ref_image]
            print(f"  Reference: {reference_path.name}")
        except Exception as e:
            print(f"  ERROR: Cannot open reference image {reference_path}: {e}")
            return False

    image_config = None
    if aspect_ratio:
        image_config = types.ImageConfig(aspect_ratio=aspect_ratio)

    # Call Gemini API
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
                image_config=image_config,
            ),
        )
    except Exception as e:
        print(f"  ERROR: API call failed: {e}")
        return False

    # Check for blocked/empty response
    if not response.candidates:
        feedback = getattr(response, "prompt_feedback", None)
        print(f"  ERROR: No candidates returned. Prompt feedback: {feedback}")
        return False

    candidate = response.candidates[0]
    finish_reason = getattr(candidate, "finish_reason", None)
    if finish_reason and str(finish_reason) not in ("STOP", "FinishReason.STOP", "0"):
        print(f"  ERROR: Generation blocked (reason: {finish_reason})")
        return False

    # Extract image from response
    for part in candidate.content.parts:
        if part.inline_data is not None:
            image_data = part.inline_data.data
            try:
                img = Image.open(io.BytesIO(image_data))
            except Exception as e:
                print(f"  ERROR: Cannot decode image from API response: {e}")
                return False

            # Save original (raw API output) if requested
            if save_original:
                try:
                    save_original.parent.mkdir(parents=True, exist_ok=True)
                    img.save(save_original, "PNG")
                    print(f"  Original saved: {save_original} ({img.size[0]}x{img.size[1]})")
                except OSError as e:
                    print(f"  WARNING: Could not save original: {e}")

            # Save output
            try:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                ext = output_path.suffix.lower()
                if ext in (".jpg", ".jpeg"):
                    if img.mode != "RGB":
                        img = img.convert("RGB")
                    img.save(output_path, "JPEG", quality=90)
                else:
                    img.save(output_path, "PNG", optimize=True)
            except OSError as e:
                print(f"  ERROR: Cannot save output {output_path}: {e}")
                return False

            print(f"  Saved: {output_path} ({img.size[0]}x{img.size[1]})")
            return True

    print("  ERROR: No image data in API response")
    return False


def cmd_generate(args: argparse.Namespace) -> int:
    """Handle 'generate' subcommand."""
    client = get_client()
    output = Path(args.output)
    reference = Path(args.reference) if args.reference else None
    original = Path(args.save_original) if args.save_original else None

    success = generate_single(
        client,
        prompt=args.prompt,
        output_path=output,
        model=args.model,
        aspect_ratio=args.aspect_ratio,
        reference_path=reference,
        save_original=original,
    )
    return 0 if success else 1


def cmd_with_reference(args: argparse.Namespace) -> int:
    """Handle 'with-reference' subcommand."""
    client = get_client()
    reference = Path(args.reference)
    if not reference.exists():
        print(f"ERROR: Reference image not found: {reference}")
        return 1

    output = Path(args.output)
    original = Path(args.save_original) if args.save_original else None

    success = generate_single(
        client,
        prompt=args.prompt,
        output_path=output,
        model=args.model,
        aspect_ratio=args.aspect_ratio,
        reference_path=reference,
        save_original=original,
    )
    return 0 if success else 1


def cmd_batch(args: argparse.Namespace) -> int:
    """Handle 'batch' subcommand.

    Manifest JSON format:
    [
        {"id": "enemy_1", "prompt": "A warrior..."},
        {"id": "enemy_2", "prompt": "A mage...", "reference": "ref.png"},
        ...
    ]
    """
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"ERROR: Manifest not found: {manifest_path}")
        return 1

    try:
        with open(manifest_path) as f:
            items = json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in manifest: {e}")
        return 1
    except (PermissionError, OSError) as e:
        print(f"ERROR: Cannot read manifest: {e}")
        return 1

    if not isinstance(items, list):
        print("ERROR: Manifest must be a JSON array")
        return 1

    client = get_client()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    originals_dir = Path(args.originals_dir) if args.originals_dir else None
    if originals_dir:
        originals_dir.mkdir(parents=True, exist_ok=True)

    generated = 0
    skipped = 0
    failed = 0
    failed_ids = []
    total = len(items) * args.variants

    print(f"Batch: {len(items)} items x {args.variants} variant(s) = {total} images")
    print(f"Model: {VALID_MODELS[args.model]}")
    print(f"Output: {output_dir}")
    print()

    for idx, item in enumerate(items):
        if not isinstance(item, dict) or "id" not in item or "prompt" not in item:
            print(f"ERROR: Manifest item {idx} missing 'id' or 'prompt': {item}")
            failed += 1
            failed_ids.append(f"item[{idx}]")
            continue

        item_id = item["id"]
        prompt = item["prompt"]
        reference = Path(item["reference"]) if item.get("reference") else None

        for v in range(1, args.variants + 1):
            suffix = f"_v{v}" if args.variants > 1 else ""
            out_path = output_dir / f"{item_id}{suffix}.png"

            if args.skip_existing and out_path.exists():
                skipped += 1
                print(f"Skipping {item_id}{suffix} — already exists")
                continue

            original_path = None
            if originals_dir:
                original_path = originals_dir / f"{item_id}{suffix}_original.png"

            success = generate_single(
                client,
                prompt=prompt,
                output_path=out_path,
                model=args.model,
                aspect_ratio=args.aspect_ratio,
                reference_path=reference,
                save_original=original_path,
            )

            if success:
                generated += 1
            else:
                failed += 1
                failed_ids.append(f"{item_id}{suffix}")

            if args.delay > 0:
                time.sleep(args.delay)

    print()
    print(f"BATCH COMPLETE: {generated} generated, {skipped} skipped, {failed} failed (of {total})")
    if failed_ids:
        print(f"Failed: {', '.join(failed_ids)}")
    return 0 if failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate images using Gemini Nano Banana APIs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Common arguments
    def add_common_args(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--model",
            choices=["flash", "pro"],
            default="flash",
            help="Model: flash (fast) or pro (quality). Default: flash",
        )
        p.add_argument("--aspect-ratio", choices=VALID_RATIOS, help="Aspect ratio for generation")

    # generate
    gen = subparsers.add_parser("generate", help="Generate a single image")
    gen.add_argument("--prompt", required=True, help="Text prompt")
    gen.add_argument("--output", required=True, help="Output file path")
    gen.add_argument("--reference", help="Optional reference image for style matching")
    gen.add_argument("--save-original", help="Save raw API output before processing")
    add_common_args(gen)
    gen.set_defaults(func=cmd_generate)

    # with-reference
    ref = subparsers.add_parser("with-reference", help="Generate with reference image")
    ref.add_argument("--prompt", required=True, help="Text prompt")
    ref.add_argument("--reference", required=True, help="Reference image path")
    ref.add_argument("--output", required=True, help="Output file path")
    ref.add_argument("--save-original", help="Save raw API output before processing")
    add_common_args(ref)
    ref.set_defaults(func=cmd_with_reference)

    # batch
    bat = subparsers.add_parser("batch", help="Batch generate from JSON manifest")
    bat.add_argument("--manifest", required=True, help="JSON manifest file")
    bat.add_argument("--output-dir", required=True, help="Output directory")
    bat.add_argument("--originals-dir", help="Save raw API outputs here")
    bat.add_argument("--skip-existing", action="store_true", help="Skip items with existing output")
    bat.add_argument("--variants", type=int, default=1, help="Variants per item (default: 1)")
    bat.add_argument("--delay", type=float, default=2.0, help="Seconds between API calls (default: 2.0)")
    add_common_args(bat)
    bat.set_defaults(func=cmd_batch)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
