# Gemini Backend Reference

Load when `detect-backend.py` outputs `gemini`.

## Models

Use only these exact strings. Date suffixes valid for text models cause silent failures on image models.

| Alias | Exact model string | Speed | Quality | Use for |
|---|---|---|---|---|
| flash | `gemini-2.5-flash-image` | 2-5s | Draft | Iterations, batch, sprites, cost-sensitive |
| pro | `gemini-3-pro-image-preview` | ~30s | Final | Character art, typography, final assets |

Wrong strings (API returns cryptic errors):
- `gemini-2.5-flash-preview-05-20` — date suffix; not an image model
- `gemini-2.5-pro-image` — does not exist
- `gemini-3-flash-image` — does not exist
- `gemini-pro-vision` — image *input* model, not image *output*

The script reads `GEMINI_API_KEY`, then `GOOGLE_API_KEY`.

## generate_image.py Flags

**Location**: `skills/content/image-gen/scripts/generate_image.py`

| Flag | Required | Default | Description |
|---|---|---|---|
| `--prompt` | Yes* | — | Text prompt for generation |
| `--output` | Yes* | — | Output file path (.png) — use absolute path |
| `--model` | No | `gemini-3-pro-image-preview` | Model string (exact, see table above) |
| `--remove-watermark` | No | off | Remove bright corner pixels |
| `--transparent-bg` | No | off | Make background transparent |
| `--bg-color` | No | `#3a3a3a` | Background hex color for transparency |
| `--bg-tolerance` | No | `30` | Color match tolerance (0-255) |
| `--batch` | No | — | Text file: one prompt per line |
| `--output-dir` | No | — | Directory for batch output |
| `--retries` | No | `3` | Max retry attempts |
| `--delay` | No | `3.0` | Seconds between batch requests |

*Required unless using `--batch` + `--output-dir`.

**Exit codes**: 0 = success, 1 = missing API key, 2 = generation failed, 3 = invalid arguments

## Example

```bash
python3 skills/content/image-gen/scripts/generate_image.py \
  --prompt "Full body character, solid dark gray background (#3a3a3a), no background details" \
  --output /absolute/path/output/character.png \
  --model gemini-3-pro-image-preview \
  --remove-watermark \
  --transparent-bg \
  --bg-color "#3a3a3a" \
  --bg-tolerance 30
```

For transparency, request a uniform background matching `--bg-color`; omit scenery and ground shadows because they survive color-key removal.
