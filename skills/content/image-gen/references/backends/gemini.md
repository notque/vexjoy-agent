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

## Environment Variables

The script reads these in order; set either one:

```bash
export GEMINI_API_KEY=your_key
# or
export GOOGLE_API_KEY=your_key
```

Verify before calling any script:

```bash
echo "GEMINI_API_KEY: ${GEMINI_API_KEY:+set (last4: ${GEMINI_API_KEY: -4})}"
```

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

## Example: Single Image

```bash
python3 skills/content/image-gen/scripts/generate_image.py \
  --prompt "Full body warrior, Slay the Spire style, solid dark gray background, no text" \
  --output /absolute/path/output/warrior.png \
  --model gemini-3-pro-image-preview
```

## Example: With Post-Processing

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

## Example: Batch from Text File

```bash
# prompts.txt: one prompt per line, # for comments
python3 skills/content/image-gen/scripts/generate_image.py \
  --batch prompts.txt \
  --output-dir /absolute/path/output/ \
  --model gemini-2.5-flash-image \
  --delay 3
```

## Error Codes and Fixes

| Error | Cause | Fix |
|---|---|---|
| `GEMINI_API_KEY not set` | Env var missing | `export GEMINI_API_KEY=your_key` |
| `No image in response` | Safety filter or text-only response | Adjust prompt; remove policy-adjacent content |
| `Content policy violation (400)` | Restricted content | Rephrase using neutral language |
| `Rate limit exceeded (429)` | Too many requests | Script retries automatically; increase `--delay` if persistent |
| `No candidates in response` | API returned empty | Retry with a different prompt |
| `Missing dependency: google-genai` | Package absent | `pip install google-genai pillow` |
| Model not found | Wrong model string | Use exact strings from the table above |

## Prompt Engineering

**Structure**: `[Subject] [Style] [Background] [Constraints]`

Background phrases for post-processing:
- `solid dark gray background` → remove-bg with `--bg-color "#3a3a3a"`
- `solid uniform gray background (#3a3a3a)` → same
- `solid white background` → remove-bg with `--bg-color "#ffffff"`

Constraint phrases to include:
- `no text, no labels, no watermarks` — always include
- `character only` / `subject only` — removes unwanted props
- `no background elements or scenery` — for transparent-bg prep
- `no ground shadows` — shadows survive bg removal and look wrong

Style anchors: "Slay the Spire card game style", "Hollow Knight art style", "Borderlands cel-shaded style", "Studio Ghibli aesthetic"
