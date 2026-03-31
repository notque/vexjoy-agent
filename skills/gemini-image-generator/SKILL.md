---
name: gemini-image-generator
description: "Generate images from text prompts via Google Gemini."
version: 2.0.0
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

Generate images from text prompts via CLI using Google Gemini APIs. Supports model selection between fast (`gemini-2.5-flash-image`) and quality (`gemini-3-pro-image-preview`) models, batch generation, watermark removal, and background transparency.

## Instructions

### Step 1: Validate Environment

Verify the API key exists before any generation attempt -- a missing key produces confusing errors that waste time debugging.

```bash
echo "GEMINI_API_KEY is ${GEMINI_API_KEY:+set}"
```

Expect: `GEMINI_API_KEY is set`. If not set, instruct user to configure it and stop.

Verify Python dependencies are available:

```bash
python3 -c "from google import genai; from PIL import Image; print('OK')"
```

If missing, install:
```bash
pip install google-genai Pillow
```

Determine the output path. Always use absolute paths for output files -- relative paths break when scripts run in different working directories. Verify the parent directory exists or will be created.

**Proceed only when**: API key is set, dependencies installed, output path is valid.

### Step 2: Select Model and Compose Prompt

Choose the model based on the use case:

| Scenario | Model | Why |
|----------|-------|-----|
| Iterating on prompt, drafts | `gemini-2.5-flash-image` | Fast feedback (2-5s) |
| Final quality asset | `gemini-3-pro-image-preview` | Best quality, 2K resolution |
| Game sprites, batch work | `gemini-2.5-flash-image` | Cost effective, consistent |
| Text in image, typography | `gemini-3-pro-image-preview` | Better text rendering |
| Product photography | `gemini-3-pro-image-preview` | Detail matters |

Use ONLY these exact model strings -- the API returns cryptic errors for anything else, and date suffixes (valid for text models) do not work for image models:

| Correct (use exactly) | WRONG (never use) |
|------------------------|-------------------|
| `gemini-2.5-flash-image` | `gemini-2.5-flash-preview-05-20` (date suffix) |
| `gemini-3-pro-image-preview` | `gemini-2.5-pro-image` (doesn't exist) |
| | `gemini-3-flash-image` (doesn't exist) |
| | `gemini-pro-vision` (that's image input) |

Compose the prompt using this structure: `[Subject] [Style] [Background] [Constraints]`

For transparent background post-processing, include:
- "solid dark gray background" or "solid uniform gray background (#3a3a3a)"
- "no background elements or scenery"

Always include negative constraints: "no text", "no labels", "character only"

Determine post-processing flags:
- Need watermark removal? Add `--remove-watermark`
- Need transparent background? Add `--transparent-bg`
- Custom background color? Add `--bg-color "#FFFFFF" --bg-tolerance 20`

**Proceed only when**: Model selected, prompt composed, flags determined.

### Step 3: Generate

Always use the provided `generate_image.py` script -- it contains retry logic, rate limiting, post-processing, model validation, and error handling that inline Python would miss.

```bash
python3 $HOME/claude-code-toolkit/skills/gemini-image-generator/scripts/generate_image.py \
  --prompt "YOUR_PROMPT_HERE" \
  --output /absolute/path/to/output.png \
  --model gemini-3-pro-image-preview
```

For batch mode:
```bash
python3 $HOME/claude-code-toolkit/skills/gemini-image-generator/scripts/generate_image.py \
  --batch /path/to/prompts.txt \
  --output-dir /absolute/path/to/output/ \
  --model gemini-2.5-flash-image
```

Display the full script output -- never summarize it, since the user needs to see status, warnings, and any partial failures.

Check for `SUCCESS` or `ERROR` in output. If rate limited (429), the script handles retry automatically with exponential backoff (up to 3 attempts).

**Proceed only when**: Script exited with code 0 and printed SUCCESS.

### Step 4: Verify Output

Confirm the output file exists and has non-zero size -- a zero-byte file means the write succeeded but no image data was returned:

```bash
ls -la /absolute/path/to/output.png
```

Optionally check dimensions:

```bash
python3 -c "from PIL import Image; img = Image.open('/absolute/path/to/output.png'); print(f'Size: {img.size}, Mode: {img.mode}')"
```

**Visual inspection is mandatory.** Read the generated image file using the Read tool to visually inspect it. A file can pass all size and dimension checks but still contain watermarks, wrong composition, excessive padding, or content that doesn't match the prompt.

Check for:
- Content matches the prompt intent (correct subject, layout, composition)
- No unwanted watermarks, logos, or artifacts
- Text renders correctly (if text was requested)
- Appropriate aspect ratio and framing
- No excessive empty space or dark padding that needs cropping

If the image fails visual inspection, regenerate with an adjusted prompt before reporting to the user. Do not commit or deliver images without visual verification.

### Step 5: Report Result

Provide the user with:
- Output file path
- Image dimensions
- Model used
- Visual verification status (what you checked and confirmed)
- Any post-processing applied (cropping, resizing)

Only report what was directly requested -- do not suggest additional generations, style variations, or enhancements the user did not ask for.

---

## Error Handling

### Error: "GEMINI_API_KEY not set"
Cause: Environment variable missing or empty
Solution:
1. Set the variable: `export GEMINI_API_KEY="your-key"`
2. If in a CI/CD environment, check secrets configuration
3. Verify the key is valid by testing with a simple prompt

### Error: "Rate limit exceeded (429)"
Cause: Too many requests to Gemini API in short period
Solution:
1. The script retries automatically with exponential backoff
2. If persistent after retries, wait 60 seconds and try again
3. For batch operations, increase `--delay` to 5-10 seconds
4. Consider switching to `gemini-2.5-flash-image` for higher throughput

### Error: "No image in response"
Cause: API returned text-only response or generation was blocked
Solution:
1. Add more detail to the prompt -- vague prompts sometimes fail
2. Try a different model
3. Check that the prompt does not violate content policy
4. Verify the script sets `response_modalities=["IMAGE", "TEXT"]`

### Error: "Content policy violation (400)"
Cause: Prompt contains restricted content or triggers safety filters
Solution:
1. Remove potentially problematic terms from the prompt
2. Rephrase the request using neutral language
3. This is an API-side restriction and cannot be bypassed

---

## References

### Script Reference: generate_image.py

**Location**: `$HOME/claude-code-toolkit/skills/gemini-image-generator/scripts/generate_image.py`

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

**Effective prompt structure**: `[Subject] [Style] [Background] [Constraints]`

**For transparent background post-processing**:
- Use "solid dark gray background" or "solid uniform gray background (#3a3a3a)"
- Include "no background elements or scenery" and "no ground shadows"
- Combine with `--transparent-bg` flag

**For clean edges**: "clean edges", "sharp outlines", "heavy ink outlines"

**Negative constraints**: Always include "no text", "no labels", "no watermarks", "character only"

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/prompts.md`: Categorized example prompts by use case (game art, characters, product photography, pixel art, icons)
