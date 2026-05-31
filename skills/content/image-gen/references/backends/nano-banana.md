# Nano Banana Backend Reference

Load when the request requires post-processing, series generation, batch from JSON manifest, or style-match from reference images.

## Scripts

**Location**: `skills/content/image-gen/scripts/`

| Script | Role |
|---|---|
| `nano-banana-generate.py` | Image generation: single, with-reference, batch |
| `nano-banana-process.py` | Post-processing: crop, remove-bg, watermarks, convert, pipeline |

Both scripts call the same Gemini image API as `generate_image.py` but add reference-image support, JSON manifests, and chained processing.

## nano-banana-generate.py Subcommands

### generate — single image

```bash
python3 skills/content/image-gen/scripts/nano-banana-generate.py generate \
  --prompt "PROMPT" \
  --output /absolute/path/output.png \
  --model flash|pro \
  --aspect-ratio RATIO \
  --save-original /absolute/path/original.png
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--prompt` | Yes | — | Text prompt |
| `--output` | Yes | — | Output file path |
| `--model` | No | flash | `flash` (2-5s) or `pro` (~30s) |
| `--aspect-ratio` | No | model default | See aspect ratio table |
| `--reference` | No | — | Reference image for style/identity matching |
| `--save-original` | No | — | Save raw API output before processing |

### with-reference — style or identity match

Same flags as `generate` but `--reference` is required. Use for anchor-chain series: pass the previous image as `--reference`.

```bash
python3 skills/content/image-gen/scripts/nano-banana-generate.py with-reference \
  --prompt "Same character, different pose" \
  --reference output/hero-01.png \
  --output output/hero-02.png \
  --model pro --aspect-ratio 1:1
```

### batch — JSON manifest

```bash
python3 skills/content/image-gen/scripts/nano-banana-generate.py batch \
  --manifest enemies.json \
  --output-dir output/sprites/ \
  --originals-dir output/originals/ \
  --model pro --aspect-ratio 1:1 \
  --skip-existing --variants 1 --delay 3
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--manifest` | Yes | — | JSON file: `[{"id": "name", "prompt": "...", "reference": "optional.png"}]` |
| `--output-dir` | Yes | — | Directory for generated images |
| `--originals-dir` | No | — | Save raw API outputs here |
| `--skip-existing` | No | off | Skip items with existing output files |
| `--variants` | No | 1 | Variants per item (1-5) |
| `--delay` | No | 2.0 | Seconds between API calls |

Manifest format:
```json
[
  {"id": "goblin", "prompt": "Full body goblin warrior, Slay the Spire style..."},
  {"id": "skeleton", "prompt": "Full body skeleton archer...", "reference": "path/to/ref.png"}
]
```

## nano-banana-process.py Subcommands

### crop

Use `--bias 0.35` for character/sprite art to preserve heads (default 0.5 centers the crop).

```bash
python3 skills/content/image-gen/scripts/nano-banana-process.py crop \
  --width 256 --height 256 --bias 0.35 \
  input.png output.png
```

| Flag | Default | Description |
|---|---|---|
| `--width` | Required | Target width in pixels |
| `--height` | Required | Target height in pixels |
| `--bias` | 0.5 | 0.0=anchor top, 0.35=keep head, 0.5=center, 1.0=anchor bottom |

### remove-bg

```bash
python3 skills/content/image-gen/scripts/nano-banana-process.py remove-bg \
  --bg-color 3a3a3a --tolerance 30 \
  sprite_raw.png sprite.png
```

| Flag | Default | Description |
|---|---|---|
| `--bg-color` | `3a3a3a` | Hex color to make transparent (without #) |
| `--tolerance` | 30 | Color variance (0-255); increase for noisy backgrounds |

Common background colors:
- `3a3a3a` — dark gray ("solid dark gray background")
- `ffffff` — white
- `000000` — black

### remove-watermarks

Replaces bright corner pixels with the background color.

```bash
python3 skills/content/image-gen/scripts/nano-banana-process.py remove-watermarks \
  --margin 40 --threshold 180 \
  input.png output.png
```

### convert

```bash
python3 skills/content/image-gen/scripts/nano-banana-process.py convert \
  --format jpeg --quality 90 \
  input.png output.jpg
```

Formats: `png` (lossless, supports transparency), `jpeg` (smaller, no alpha), `webp` (best compression)

### pipeline — chained processing

Runs: watermarks → background → crop → format, in order.

```bash
# Single file
python3 skills/content/image-gen/scripts/nano-banana-process.py pipeline \
  --remove-watermarks --remove-bg --bg-color 3a3a3a \
  --width 256 --height 256 --bias 0.35 \
  --format png \
  input.png output.png

# Batch (input is a directory)
python3 skills/content/image-gen/scripts/nano-banana-process.py pipeline \
  --width 400 --height 218 --bias 0.35 \
  --format jpeg --quality 90 \
  staging/originals/ output/cards/
```

## Aspect Ratio Table

| Ratio | Use for |
|---|---|
| `1:1` | Sprites, characters, icons |
| `16:9` | Card art, landscape backgrounds |
| `9:16` | Vertical maps, portrait backgrounds |
| `3:4` | Portrait cards |
| `4:3` | Standard cards |
| `21:9` | Wide banners |
| `2:3`, `3:2`, `4:5`, `5:4` | Specialty uses |

## Model Aliases

| Alias | Exact model string | Notes |
|---|---|---|
| `flash` | `gemini-2.5-flash-image` | Fast (2-5s), cost-effective |
| `pro` | `gemini-3-pro-image-preview` | Quality (~30s), best for final assets |

Pass `--model flash` or `--model pro` to the generate scripts. The scripts reject any other string.

## Prompt Patterns by Asset Type

**Sprites/Characters** (model pro, aspect-ratio 1:1):
- "solid dark gray background color only" → enables remove-bg with `--bg-color 3a3a3a`
- "ONE character only, full body visible from head to feet, centered in frame"
- "no text, no labels, no background details"
- Style example: "Slay the Spire card game style, heavy ink outlines, golden glowing outline"

**Card Art** (model flash, aspect-ratio 16:9):
- "WIDE SHOT, full bodies with space around them"
- "sketchy rough painterly, muted desaturated sepia palette"
- "wrestling ring ropes in background" (context-specific)

**Backgrounds** (model flash, aspect-ratio 9:16 or 16:9):
- "Very dark overall (UI elements need to be readable on top)"
- "no text, no labels, no characters"

## Dependencies

```bash
pip install google-genai pillow
```

Both scripts require `google-genai` (generation) and `pillow` (post-processing). Install together.
