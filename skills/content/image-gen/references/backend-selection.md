# Backend Selection

Always-load reference. Use to pick the right script and mode for every generation request.

## Decision Table

| Request type | Backend | Script | Subcommand |
|---|---|---|---|
| Single image, no post-processing | Gemini | `scripts/generate_image.py` | (default) |
| Single image, transparent bg or watermark removal | Gemini | `scripts/generate_image.py` | `--transparent-bg` / `--remove-watermark` |
| Batch from text file (one prompt per line) | Gemini | `scripts/generate_image.py` | `--batch` |
| Single image with advanced post-processing | Nano Banana | `scripts/nano-banana-generate.py` | `generate` |
| Style match from reference image | Nano Banana | `scripts/nano-banana-generate.py` | `with-reference` |
| Batch from JSON manifest | Nano Banana | `scripts/nano-banana-generate.py` | `batch` |
| Series (anchor chain, 2+ images) | Nano Banana | `scripts/nano-banana-generate.py` | `generate` then `with-reference` |
| Crop, resize, format convert | Nano Banana | `scripts/nano-banana-process.py` | `crop` / `convert` |
| Background removal (chromakey) | Nano Banana | `scripts/nano-banana-process.py` | `remove-bg` |
| Watermark removal | Nano Banana | `scripts/nano-banana-process.py` | `remove-watermarks` |
| Full sprite pipeline (chain) | Nano Banana | `scripts/nano-banana-process.py` | `pipeline` |

## Script Selection Guide

### Use `generate_image.py` when:
- Single prompt, single output
- Batch from a plain text file
- Built-in post-processing is enough (watermark removal, transparent bg)
- No reference image needed

### Use `nano-banana-generate.py` when:
- Series requiring anchor chain
- Style-match from an existing image
- Batch from JSON manifest (with per-item prompts and optional per-item references)
- Need variants per item

### Use `nano-banana-process.py` when:
- Post-processing already-generated images without re-generating
- Need crop, remove-bg, watermark removal, format conversion, or pipeline chain

## Prompt File Format

All prompt files follow this structure:

```markdown
---
model: gemini-3-pro-image-preview
aspect-ratio: 1:1
flags: []
---

[prompt body — explicit subject, style, background, constraints]
```

Valid frontmatter fields:
- `model`: `gemini-2.5-flash-image` (fast/draft) or `gemini-3-pro-image-preview` (quality/final)
- `aspect-ratio`: one of `1:1`, `2:3`, `3:2`, `3:4`, `4:3`, `4:5`, `5:4`, `9:16`, `16:9`, `21:9`
- `flags`: list of extra flags to pass to the script (e.g. `[--save-original path]`)

## Model Selection

| Scenario | Model |
|---|---|
| Draft iterations, testing prompt | `gemini-2.5-flash-image` (fast: 2-5s) |
| Final asset, character art, high quality | `gemini-3-pro-image-preview` (quality: ~30s) |
| Game sprites (batch, cost matters) | `gemini-2.5-flash-image` |
| Typography, text in image | `gemini-3-pro-image-preview` (better text rendering) |

## Aspect Ratio by Use Case

| Asset type | Aspect ratio |
|---|---|
| Sprites / characters | `1:1` |
| Card art | `16:9` |
| Vertical backgrounds / maps | `9:16` |
| Landscape arenas | `16:9` |
| Portrait cards | `3:4` |
| Wide banners | `21:9` |

Generate at the target aspect ratio. Generating 1:1 and cropping to 16:9 loses 56% of pixels — use the right ratio from the start.
