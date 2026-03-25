---
name: nano-banana-builder
description: |
  Generate and post-process images using Google Gemini Nano Banana APIs via
  deterministic Python scripts. Covers single generation, batch generation,
  style transfer with reference images, and post-processing (smart crop,
  background removal, watermark cleanup, format conversion). Use for "nano
  banana", "generate image", "gemini image", "batch image generation",
  "sprite generation", "card art", or "image post-processing". Do NOT use
  for non-Gemini models, model fine-tuning, or image classification tasks.
version: 3.0.0
user-invocable: false
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
command: /nano-banana
routing:
  triggers:
    - nano banana
    - gemini image generation
    - AI image generator
    - generate image
    - gemini-2.5-flash-image
    - gemini-3-pro-image-preview
    - batch image generation
    - image post-processing
    - sprite generation
    - generate card art
  pairs_with:
    - python-general-engineer
    - universal-quality-gate
---

# Nano Banana Builder

## Operator Context

This skill orchestrates image generation and post-processing via two deterministic Python scripts. The LLM's job is **prompt crafting** (describing what to generate) and **flag selection** (choosing the right script options). The scripts handle all mechanical operations.

### Architecture

| Component | Path | Purpose |
|-----------|------|---------|
| `nano-banana-generate.py` | `scripts/` | Generate images via Gemini API |
| `nano-banana-process.py` | `scripts/` | Post-process: crop, bg removal, watermarks, format |

**Principle**: "LLMs orchestrate. Programs execute." The skill tells you *when* to call *which script* with *which flags*. The scripts do the work deterministically.

### Hardcoded Behaviors (Always Apply)

- **Scripts Only**: ALL generation and processing goes through the Python scripts. Never write inline image processing code.
- **Exact Model Names Only**: Only two models exist: `flash` (gemini-2.5-flash-image) and `pro` (gemini-3-pro-image-preview). The scripts enforce this.
- **Save Originals**: For any batch or expensive generation, use `--save-original` or `--originals-dir` to preserve raw API output before processing. Re-generating costs money; re-processing a saved original is free.
- **API Key Required**: Scripts read `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) from environment. Validate before running.
- **Rate Limiting**: Use `--delay` for batch operations. Default 2s for flash, 3s for pro.

### Default Behaviors (ON unless disabled)

- **Flash for iterations, Pro for finals**: Use `--model flash` for drafts and experimentation, `--model pro` for final output
- **Skip existing in batch**: Use `--skip-existing` to avoid re-generating images that already exist
- **Top-biased crop for characters**: Use `--bias 0.35` when cropping character/sprite art to preserve heads

---

## Scripts Reference

### nano-banana-generate.py

**Dependencies**: `pip install google-genai pillow`

#### generate — Single image

```bash
python3 ~/.claude/scripts/nano-banana-generate.py generate \
    --prompt "PROMPT" \
    --output OUTPUT_PATH \
    --model flash|pro \
    --aspect-ratio RATIO \
    --save-original ORIGINAL_PATH
```

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--prompt` | Yes | — | Text prompt for generation |
| `--output` | Yes | — | Output file path (.png or .jpg) |
| `--model` | No | flash | `flash` (fast, 2-5s) or `pro` (quality, ~30s) |
| `--aspect-ratio` | No | model default | 1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9 |
| `--reference` | No | — | Reference image for style matching |
| `--save-original` | No | — | Save raw API output to this path |

#### with-reference — Style transfer

```bash
python3 ~/.claude/scripts/nano-banana-generate.py with-reference \
    --prompt "Recreate in this art style" \
    --reference style_ref.png \
    --output styled.png \
    --model flash --aspect-ratio 16:9
```

Same flags as `generate` but `--reference` is required.

#### batch — Multiple images from manifest

```bash
python3 ~/.claude/scripts/nano-banana-generate.py batch \
    --manifest items.json \
    --output-dir staging/sprites/ \
    --originals-dir staging/originals/ \
    --model pro --aspect-ratio 1:1 \
    --skip-existing --variants 3 --delay 3
```

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--manifest` | Yes | — | JSON file: `[{"id": "name", "prompt": "...", "reference": "optional.png"}]` |
| `--output-dir` | Yes | — | Directory for generated images |
| `--originals-dir` | No | — | Save raw API outputs here |
| `--skip-existing` | No | off | Skip items with existing output files |
| `--variants` | No | 1 | Number of variants per item (1-5) |
| `--delay` | No | 2.0 | Seconds between API calls |

### nano-banana-process.py

**Dependencies**: `pip install pillow`

#### crop — Smart crop to dimensions

```bash
python3 ~/.claude/scripts/nano-banana-process.py crop \
    --width 400 --height 218 --bias 0.35 \
    input.png output.png
```

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--width` | Yes | — | Target width in pixels |
| `--height` | Yes | — | Target height in pixels |
| `--bias` | No | 0.5 | 0.0=anchor top, 0.35=keep top, 0.5=center, 1.0=anchor bottom |

#### remove-bg — Background removal

```bash
python3 ~/.claude/scripts/nano-banana-process.py remove-bg \
    --bg-color 3a3a3a --tolerance 30 \
    sprite_raw.png sprite.png
```

| Flag | Default | Description |
|------|---------|-------------|
| `--bg-color` | 3a3a3a | Hex color to make transparent |
| `--tolerance` | 30 | Color variance (0-255) |

Common background colors for Gemini prompts:
- `3a3a3a` — dark gray ("solid dark gray background")
- `ffffff` — white ("solid white background")
- `000000` — black ("solid black background")

#### remove-watermarks — Corner cleanup

```bash
python3 ~/.claude/scripts/nano-banana-process.py remove-watermarks \
    --margin 40 --threshold 180 \
    input.png output.png
```

#### convert — Format conversion

```bash
python3 ~/.claude/scripts/nano-banana-process.py convert \
    --format jpeg --quality 90 \
    input.png output.jpg
```

Formats: `png` (lossless, supports transparency), `jpeg` (smaller, no alpha), `webp` (best compression).

#### pipeline — Full processing chain

Runs all steps in order: watermarks → background → crop → format.

```bash
# Single file
python3 ~/.claude/scripts/nano-banana-process.py pipeline \
    --remove-watermarks --remove-bg --bg-color 3a3a3a \
    --width 256 --height 256 --bias 0.35 \
    --format png \
    input.png output.png

# Batch (input is a directory)
python3 ~/.claude/scripts/nano-banana-process.py pipeline \
    --width 400 --height 218 --bias 0.35 \
    --format jpeg --quality 90 \
    staging/originals/ output/cards/
```

---

## Intent-to-Script Mapping

The LLM's job is to translate user intent into the right script call. Here's the mapping:

| User wants | Script + subcommand | Key flags |
|------------|-------------------|-----------|
| Generate a single image | `nano-banana-generate.py generate` | `--prompt`, `--model`, `--aspect-ratio` |
| Generate a sprite/character | `nano-banana-generate.py generate` | `--model pro`, `--aspect-ratio 1:1` |
| Generate card art | `nano-banana-generate.py generate` | `--model flash`, `--aspect-ratio 16:9` |
| Generate backgrounds | `nano-banana-generate.py generate` | `--model flash`, `--aspect-ratio 9:16` (vertical) or `16:9` (landscape) |
| Style-match a reference | `nano-banana-generate.py with-reference` | `--reference`, `--prompt` |
| Batch generate enemies/items | `nano-banana-generate.py batch` | `--manifest`, `--skip-existing`, `--delay 3` |
| Crop to exact dimensions | `nano-banana-process.py crop` | `--width`, `--height`, `--bias` |
| Make background transparent | `nano-banana-process.py remove-bg` | `--bg-color`, `--tolerance` |
| Clean up watermarks | `nano-banana-process.py remove-watermarks` | `--margin`, `--threshold` |
| Convert format | `nano-banana-process.py convert` | `--format`, `--quality` |
| Full sprite pipeline | `nano-banana-process.py pipeline` | `--remove-bg`, `--remove-watermarks`, crop flags |
| Batch reprocess originals | `nano-banana-process.py pipeline` | directory input, crop + format flags |

### Prompt Crafting Guidelines

The LLM's unique contribution is writing effective prompts. Key patterns:

**Sprites/Characters** (use with `--model pro`):
- Always specify: "solid dark gray background color only" (for bg removal with `--bg-color 3a3a3a`)
- Always specify: "ONE character only, full body visible from head to feet, centered in frame"
- Always specify: "no text, no labels, no background details"
- Describe art style explicitly: "Slay the Spire card game style, heavy ink outlines, golden glowing outline"

**Card Art** (use with `--model flash`):
- Specify composition: "WIDE SHOT, full bodies with space around them"
- Specify style: "sketchy rough painterly, muted desaturated sepia palette"
- Include context: "wrestling ring ropes in background"

**Backgrounds** (use with `--model flash`):
- Specify darkness: "Very dark overall (UI elements need to be readable on top)"
- Specify no characters: "NO text, NO labels, NO characters"
- Match aspect ratio to use: 9:16 for vertical scrolling, 16:9 for landscape arenas

---

## Workflows

### Generate + Process (single image)

```bash
# 1. Generate raw sprite
python3 ~/.claude/scripts/nano-banana-generate.py generate \
    --prompt "Full body warrior, Slay the Spire style, solid dark gray background..." \
    --output staging/warrior_raw.png \
    --model pro --aspect-ratio 1:1 \
    --save-original staging/originals/warrior.png

# 2. Process: remove watermarks, remove bg, crop, save as PNG
python3 ~/.claude/scripts/nano-banana-process.py pipeline \
    --remove-watermarks --remove-bg --bg-color 3a3a3a \
    --width 256 --height 256 --bias 0.35 \
    --format png \
    staging/warrior_raw.png output/warrior.png
```

### Batch Generate + Batch Process

```bash
# 1. Create manifest
cat > enemies.json << 'EOF'
[
    {"id": "goblin", "prompt": "Full body goblin warrior..."},
    {"id": "skeleton", "prompt": "Full body skeleton archer..."}
]
EOF

# 2. Batch generate (saves originals)
python3 ~/.claude/scripts/nano-banana-generate.py batch \
    --manifest enemies.json \
    --output-dir staging/sprites/ \
    --originals-dir staging/originals/ \
    --model pro --skip-existing --delay 3

# 3. Batch process all generated sprites
python3 ~/.claude/scripts/nano-banana-process.py pipeline \
    --remove-watermarks --remove-bg --bg-color 3a3a3a \
    --width 256 --height 256 --bias 0.35 --format png \
    staging/sprites/ output/sprites/
```

### Reprocess from originals (no regeneration cost)

```bash
# Try different crop dimensions without re-generating
python3 ~/.claude/scripts/nano-banana-process.py pipeline \
    --width 400 --height 167 --bias 0.35 --format jpeg --quality 90 \
    staging/originals/ output/cards/
```

---

## Error Handling

### Error: "GEMINI_API_KEY not set"
Solution: `export GEMINI_API_KEY=your_key` or `export GOOGLE_API_KEY=your_key`

### Error: "No image in response"
Cause: Prompt may have triggered content safety filters, or API returned text-only
Solution: Adjust prompt. Check for policy-violating content. Try a different phrasing.

### Error: "Missing dependency: google-genai"
Solution: `pip install google-genai pillow`

### Error: "Rate limit exceeded (429)"
Solution: Increase `--delay` value. Default 2s may be too aggressive for free tier.

---

## Anti-Patterns

### Anti-Pattern 1: Writing Inline Image Processing
**What it looks like**: Writing PIL/sharp code directly instead of calling the scripts
**Why wrong**: Duplicates tested logic, introduces variance, bypasses the deterministic pipeline
**Do instead**: Call `nano-banana-process.py` with the appropriate subcommand and flags

### Anti-Pattern 2: Inventing Model Names
**What it looks like**: Using `gemini-2.5-flash-preview-05-20` or `gemini-2.5-pro-image`
**Why wrong**: These strings don't support image generation. The scripts validate model names.
**Do instead**: Use `--model flash` or `--model pro`. The scripts map to correct API strings.

### Anti-Pattern 3: Not Saving Originals
**What it looks like**: Generating and immediately processing without `--save-original`
**Why wrong**: If the crop/processing is wrong, you must re-generate (costs money + quota)
**Do instead**: Always use `--save-original` or `--originals-dir` for non-trivial generation

### Anti-Pattern 4: Wrong Aspect Ratio for Use Case
**What it looks like**: Generating a 1:1 image then cropping to 16:9 (loses 56% of pixels)
**Why wrong**: Generates detail that gets cropped away. Wastes tokens and quality.
**Do instead**: Match `--aspect-ratio` to the target shape. 16:9 for cards, 1:1 for sprites, 9:16 for vertical maps.
