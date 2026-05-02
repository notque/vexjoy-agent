---
name: gemini-image-generator
description: "Generate images from text prompts via Google Gemini."
agent: python-general-engineer
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
command: /generate-image
routing:
  triggers:
    - generate image
    - create image with AI
    - gemini image
    - text to image
    - python image generation
    - create sprite
    - generate character art
  pairs_with:
    - python-general-engineer
    - workflow
  complexity: simple
  category: image-generation
---

# Gemini Image Generator

Generate images from text prompts via Google Gemini APIs. Supports model selection (`gemini-2.5-flash-image` for speed, `gemini-3-pro-image-preview` for quality), batch generation, watermark removal, and background transparency.

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| tasks related to this reference | `prompts.md` | Loads detailed guidance from `prompts.md`. |

## Instructions

### Step 1: Validate Environment

```bash
echo "GEMINI_API_KEY is ${GEMINI_API_KEY:+set}"
```

Expect: `GEMINI_API_KEY is set`. If not set, instruct user to configure it and stop.

```bash
python3 -c "from google import genai; from PIL import Image; print('OK')"
```

If missing: `pip install google-genai Pillow`

Use absolute paths for all output files. Verify the parent directory exists.

**Proceed only when**: API key set, dependencies installed, output path valid.

### Step 2: Select Model and Compose Prompt

| Scenario | Model | Why |
|----------|-------|-----|
| Iterating on prompt, drafts | `gemini-2.5-flash-image` | Fast feedback (2-5s) |
| Final quality asset | `gemini-3-pro-image-preview` | Best quality, 2K resolution |
| Game sprites, batch work | `gemini-2.5-flash-image` | Cost effective, consistent |
| Text in image, typography | `gemini-3-pro-image-preview` | Better text rendering |
| Product photography | `gemini-3-pro-image-preview` | Detail matters |

Use ONLY these exact model strings — date suffixes and other variants return cryptic errors:

| Correct (use exactly) | WRONG (never use) |
|------------------------|-------------------|
| `gemini-2.5-flash-image` | `gemini-2.5-flash-preview-05-20` (date suffix) |
| `gemini-3-pro-image-preview` | `gemini-2.5-pro-image` (doesn't exist) |
| | `gemini-3-flash-image` (doesn't exist) |
| | `gemini-pro-vision` (that's image input) |

Prompt structure: `[Subject] [Style] [Background] [Constraints]`

For transparent background post-processing, include "solid dark gray background" or "solid uniform gray background (#3a3a3a)" and "no background elements or scenery".

Always include negative constraints: "no text", "no labels", "character only"

Post-processing flags: `--remove-watermark`, `--transparent-bg`, `--bg-color "#FFFFFF" --bg-tolerance 20`.

**Proceed only when**: Model selected, prompt composed, flags determined.

### Step 3: Generate

Always use the provided script — it contains retry logic, rate limiting, post-processing, model validation, and error handling.

```bash
python3 $HOME/vexjoy-agent/skills/gemini-image-generator/scripts/generate_image.py \
  --prompt "YOUR_PROMPT_HERE" \
  --output /absolute/path/to/output.png \
  --model gemini-3-pro-image-preview
```

Batch mode:
```bash
python3 $HOME/vexjoy-agent/skills/gemini-image-generator/scripts/generate_image.py \
  --batch /path/to/prompts.txt \
  --output-dir /absolute/path/to/output/ \
  --model gemini-2.5-flash-image
```

Display full script output — never summarize it. Check for `SUCCESS` or `ERROR`. Rate limit (429) retries are automatic with exponential backoff (up to 3 attempts).

**Proceed only when**: Script exited 0 and printed SUCCESS.

### Step 4: Verify Output

Confirm output exists with non-zero size:
```bash
ls -la /absolute/path/to/output.png
```

Check dimensions:
```bash
python3 -c "from PIL import Image; img = Image.open('/absolute/path/to/output.png'); print(f'Size: {img.size}, Mode: {img.mode}')"
```

**Visual inspection is mandatory.** Read the generated image with the Read tool. Check for: correct subject/composition, no unwanted watermarks/artifacts, correct text rendering (if requested), appropriate aspect ratio, no excessive empty space.

If visual inspection fails, regenerate with adjusted prompt before reporting. Do not deliver unverified images.

### Step 5: Report Result

Provide: output file path, dimensions, model used, visual verification status, any post-processing applied.

Only report what was requested — do not suggest additional generations or variations.

## Error Handling

### Error: "GEMINI_API_KEY not set"
Set the variable: `export GEMINI_API_KEY="your-key"`. In CI/CD, check secrets configuration.

### Error: "Rate limit exceeded (429)"
Script retries automatically. If persistent, wait 60s. For batch, increase `--delay` to 5-10s. Consider `gemini-2.5-flash-image` for higher throughput.

### Error: "No image in response"
Add more detail to the prompt. Try a different model. Check content policy compliance. Verify `response_modalities=["IMAGE", "TEXT"]` is set.

### Error: "Content policy violation (400)"
Remove problematic terms, rephrase with neutral language. API-side restriction, cannot be bypassed.

## References

### Script Reference: generate_image.py

**Location**: `$HOME/vexjoy-agent/skills/gemini-image-generator/scripts/generate_image.py`

| Argument | Required | Description |
|----------|----------|-------------|
| `--prompt` | Yes* | Text prompt for image generation |
| `--output` | Yes* | Output file path (.png) |
| `--model` | No | Model name (default: gemini-3-pro-image-preview) |
| `--remove-watermark` | No | Remove watermarks from corners |
| `--transparent-bg` | No | Make background transparent |
| `--bg-color` | No | Background color hex (default: #3a3a3a) |
| `--bg-tolerance` | No | Color matching tolerance (default: 30) |
| `--batch` | No | File with prompts (one per line) |
| `--output-dir` | No | Directory for batch output |
| `--retries` | No | Max retry attempts (default: 3) |
| `--delay` | No | Delay between batch requests in seconds (default: 3) |

*Required unless using `--batch` + `--output-dir`

**Exit Codes**: 0 = success, 1 = missing API key, 2 = generation failed, 3 = invalid arguments

### Prompt Engineering Quick Reference

**Structure**: `[Subject] [Style] [Background] [Constraints]`

**For transparent background**: "solid dark gray background" or "#3a3a3a", "no background elements", combine with `--transparent-bg`

**For clean edges**: "clean edges", "sharp outlines", "heavy ink outlines"

**Negative constraints**: "no text", "no labels", "no watermarks", "character only"

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/prompts.md`: Categorized example prompts by use case
