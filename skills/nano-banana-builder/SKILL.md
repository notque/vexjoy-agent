---
name: nano-banana-builder
description: "Image generation and post-processing via Gemini Nano Banana APIs."
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

Image generation and post-processing via two deterministic Python scripts (`nano-banana-generate.py` and `nano-banana-process.py`). Your job is prompt crafting and flag selection; the scripts handle all mechanical operations.

## Instructions

### 1. Validate the environment

Before any generation call, confirm the API key is set. The scripts read `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) from the environment and will fail without it. Checking this first avoids wasted time on API calls that will error immediately.

### 2. Choose the right script and subcommand

Translate user intent into the correct script call. Always call the scripts — never write inline PIL/sharp/image-processing code, because that duplicates tested logic and bypasses the deterministic pipeline.

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

### 3. Select the model

Only two model aliases exist: `flash` (gemini-2.5-flash-image) and `pro` (gemini-3-pro-image-preview). The scripts enforce this — never pass raw Gemini model strings like `gemini-2.5-flash-preview-05-20`, because they don't support image generation and the call will fail. Use `--model flash` for drafts and iteration (fast, 2-5s). Use `--model pro` for final output (higher quality, ~30s).

### 4. Match aspect ratio to target shape

Set `--aspect-ratio` to match the final use so the generated image fills the frame. Generating 1:1 then cropping to 16:9 loses 56% of pixels and wastes quality. Valid ratios: 1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9.

- **Sprites/characters**: 1:1
- **Card art**: 16:9
- **Vertical maps/backgrounds**: 9:16
- **Landscape arenas**: 16:9

### 5. Save originals

For any batch or expensive generation, use `--save-original` (single) or `--originals-dir` (batch) to preserve raw API output before processing. Re-generating costs money and quota; re-processing a saved original is free. This enables experimentation with different crop/bg-removal settings without re-invoking the API.

### 6. Craft the prompt

Your unique contribution is writing effective prompts for the Gemini API.

**Sprites/Characters** (use with `--model pro`):
- Always specify: "solid dark gray background color only" (enables bg removal with `--bg-color 3a3a3a`)
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

### 7. Generate

#### Single image

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
| `--prompt` | Yes | -- | Text prompt for generation |
| `--output` | Yes | -- | Output file path (.png or .jpg) |
| `--model` | No | flash | `flash` (fast, 2-5s) or `pro` (quality, ~30s) |
| `--aspect-ratio` | No | model default | 1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9 |
| `--reference` | No | -- | Reference image for style matching |
| `--save-original` | No | -- | Save raw API output to this path |

#### Style transfer (with-reference)

```bash
python3 ~/.claude/scripts/nano-banana-generate.py with-reference \
    --prompt "Recreate in this art style" \
    --reference style_ref.png \
    --output styled.png \
    --model flash --aspect-ratio 16:9
```

Same flags as `generate` but `--reference` is required.

#### Batch generation

Use `--delay` to stay within rate limits (default 2s for flash, 3s for pro). Use `--skip-existing` to avoid re-generating images that already exist.

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
| `--manifest` | Yes | -- | JSON file: `[{"id": "name", "prompt": "...", "reference": "optional.png"}]` |
| `--output-dir` | Yes | -- | Directory for generated images |
| `--originals-dir` | No | -- | Save raw API outputs here |
| `--skip-existing` | No | off | Skip items with existing output files |
| `--variants` | No | 1 | Number of variants per item (1-5) |
| `--delay` | No | 2.0 | Seconds between API calls |

### 8. Post-process

Dependencies: `pip install pillow` (generation also needs `pip install google-genai pillow`).

#### Crop

Use `--bias 0.35` when cropping character/sprite art to preserve heads (default 0.5 centers the crop).

```bash
python3 ~/.claude/scripts/nano-banana-process.py crop \
    --width 400 --height 218 --bias 0.35 \
    input.png output.png
```

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--width` | Yes | -- | Target width in pixels |
| `--height` | Yes | -- | Target height in pixels |
| `--bias` | No | 0.5 | 0.0=anchor top, 0.35=keep top, 0.5=center, 1.0=anchor bottom |

#### Background removal

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
- `3a3a3a` -- dark gray ("solid dark gray background")
- `ffffff` -- white ("solid white background")
- `000000` -- black ("solid black background")

#### Watermark removal

```bash
python3 ~/.claude/scripts/nano-banana-process.py remove-watermarks \
    --margin 40 --threshold 180 \
    input.png output.png
```

#### Format conversion

```bash
python3 ~/.claude/scripts/nano-banana-process.py convert \
    --format jpeg --quality 90 \
    input.png output.jpg
```

Formats: `png` (lossless, supports transparency), `jpeg` (smaller, no alpha), `webp` (best compression).

#### Full pipeline (chained processing)

Runs all steps in order: watermarks -> background -> crop -> format.

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

### 9. End-to-end workflow examples

#### Generate + Process (single image)

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

#### Batch Generate + Batch Process

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

#### Reprocess from originals (no regeneration cost)

```bash
# Try different crop dimensions without re-generating
python3 ~/.claude/scripts/nano-banana-process.py pipeline \
    --width 400 --height 167 --bias 0.35 --format jpeg --quality 90 \
    staging/originals/ output/cards/
```

## Error Handling

### Error: "GEMINI_API_KEY not set"
Solution: `export GEMINI_API_KEY=your_key` or `export GOOGLE_API_KEY=your_key`

### Error: "No image in response"
Cause: Prompt may have triggered content safety filters, or API returned text-only.
Solution: Adjust prompt. Check for policy-violating content. Try a different phrasing.

### Error: "Missing dependency: google-genai"
Solution: `pip install google-genai pillow`

### Error: "Rate limit exceeded (429)"
Solution: Increase `--delay` value. Default 2s may be too aggressive for free tier.

## References

| Script | Path | Dependencies |
|--------|------|-------------|
| `nano-banana-generate.py` | `~/.claude/scripts/nano-banana-generate.py` | `google-genai`, `pillow` |
| `nano-banana-process.py` | `~/.claude/scripts/nano-banana-process.py` | `pillow` |
