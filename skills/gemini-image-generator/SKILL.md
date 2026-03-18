---
name: gemini-image-generator
description: |
  CLI-based image generation from text prompts using Google Gemini APIs via
  Python. Use when user needs "generate image", "create image with AI",
  "gemini image", "text to image", "create sprite", or "generate character
  art". Supports model selection, batch generation, watermark removal, and
  background transparency. Do NOT use for web app image features (use
  nano-banana-builder), video/audio generation, or non-Gemini models.
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
    - workflow-orchestrator
  complexity: simple
  category: image-generation
---

# Gemini Image Generator

## Operator Context

This skill operates as an operator for CLI-based image generation, configuring Claude's behavior for deterministic Python script execution against Google Gemini APIs. It implements an **Execute-Verify** pattern — validate environment, generate image, verify output — with **Domain Intelligence** embedded in model selection and prompt engineering.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md files
- **Over-Engineering Prevention**: Only generate what is directly requested
- **Exact Model Names**: Use only `gemini-2.5-flash-image` or `gemini-3-pro-image-preview` — no variations, no date suffixes
- **API Key Validation**: Always verify `GEMINI_API_KEY` exists before any generation attempt
- **Output Verification**: Confirm output file exists and is non-zero bytes after generation
- **Absolute Paths**: Always use absolute paths for output files

### Default Behaviors (ON unless disabled)
- **Show Complete Output**: Display full script output, never summarize
- **Rate Limit Handling**: Wait between requests to avoid 429 errors
- **Retry on Failure**: Retry transient failures with exponential backoff (3 attempts)
- **Status Reporting**: Output structured status for Claude to parse

### Optional Behaviors (OFF unless enabled)
- **Watermark Removal**: Clean watermarks from corners with `--remove-watermark`
- **Background Transparency**: Make solid backgrounds transparent with `--transparent-bg`
- **Batch Mode**: Generate multiple images from a prompt file with `--batch`

## What This Skill CAN Do
- Generate images from text prompts via CLI using Gemini APIs
- Select between fast (`gemini-2.5-flash-image`) and quality (`gemini-3-pro-image-preview`) models
- Save images to specified file paths with automatic directory creation
- Remove watermarks from generated images via post-processing
- Make solid-color backgrounds transparent for game sprites and assets
- Generate multiple images in batch mode from a prompt file
- Retry on transient failures with exponential backoff

## What This Skill CANNOT Do
- Build web applications with image generation (use `nano-banana-builder` instead)
- Use non-Gemini models (DALL-E, Midjourney, Stable Diffusion)
- Fine-tune or train models
- Generate video or audio content
- Bypass content policy restrictions
- Edit or modify existing images (generation only)

---

## Instructions

### Phase 1: ENVIRONMENT

**Goal**: Verify all prerequisites before attempting generation.

**Step 1: Validate API key**

```bash
echo "GEMINI_API_KEY is ${GEMINI_API_KEY:+set}"
```

Expect: `GEMINI_API_KEY is set`. If not set, instruct user to configure it.

**Step 2: Verify dependencies**

```bash
python3 -c "from google import genai; from PIL import Image; print('OK')"
```

If missing, install:
```bash
pip install google-genai Pillow
```

**Step 3: Determine output path**

Use an absolute path for the output file. Verify the parent directory exists or will be created.

**Gate**: API key is set, dependencies installed, output path is valid. Proceed only when gate passes.

### Phase 2: CONFIGURE

**Goal**: Select the correct model and options for the request.

**Step 1: Select model**

| Scenario | Model | Why |
|----------|-------|-----|
| Iterating on prompt, drafts | `gemini-2.5-flash-image` | Fast feedback (2-5s) |
| Final quality asset | `gemini-3-pro-image-preview` | Best quality, 2K resolution |
| Game sprites, batch work | `gemini-2.5-flash-image` | Cost effective, consistent |
| Text in image, typography | `gemini-3-pro-image-preview` | Better text rendering |
| Product photography | `gemini-3-pro-image-preview` | Detail matters |

**CRITICAL: Use ONLY these exact model strings. Do not invent, guess, or add date suffixes.**

| Correct (use exactly) | WRONG (never use) |
|------------------------|-------------------|
| `gemini-2.5-flash-image` | `gemini-2.5-flash-preview-05-20` (date suffix) |
| `gemini-3-pro-image-preview` | `gemini-2.5-pro-image` (doesn't exist) |
| | `gemini-3-flash-image` (doesn't exist) |
| | `gemini-pro-vision` (that's image input) |

**Step 2: Compose prompt**

Follow this structure: `[Subject] [Style] [Background] [Constraints]`

For transparent background post-processing, include:
- "solid dark gray background" or "solid uniform gray background (#3a3a3a)"
- "no background elements or scenery"

Always include negative constraints: "no text", "no labels", "character only"

**Step 3: Determine post-processing flags**

- Need watermark removal? Add `--remove-watermark`
- Need transparent background? Add `--transparent-bg`
- Custom background color? Add `--bg-color "#FFFFFF" --bg-tolerance 20`

**Gate**: Model selected, prompt composed, flags determined. Proceed only when gate passes.

### Phase 3: GENERATE

**Goal**: Execute the generation script and capture output.

**Step 1: Run generation**

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

**Step 2: Read script output**

Check for `SUCCESS` or `ERROR` in output. If rate limited (429), the script handles retry automatically.

**Gate**: Script exited with code 0 and printed SUCCESS. Proceed only when gate passes.

### Phase 4: VERIFY

**Goal**: Confirm the output file exists and is valid.

**Step 1: Verify file exists**

```bash
ls -la /absolute/path/to/output.png
```

File must exist and have non-zero size.

**Step 2: Check dimensions (optional)**

```bash
python3 -c "from PIL import Image; img = Image.open('/absolute/path/to/output.png'); print(f'Size: {img.size}, Mode: {img.mode}')"
```

**Step 3: Visual inspection (MANDATORY)**

Read the generated image file using the Read tool to visually inspect it:

```
Read the image at /absolute/path/to/output.png
```

Check for:
- Content matches the prompt intent (correct subject, layout, composition)
- No unwanted watermarks, logos, or artifacts
- Text renders correctly (if text was requested)
- Appropriate aspect ratio and framing
- No excessive empty space or dark padding that needs cropping

If the image fails visual inspection, regenerate with an adjusted prompt before reporting to the user. Do not commit or deliver images without visual verification.

**Step 4: Report result**

Provide the user with:
- Output file path
- Image dimensions
- Model used
- Visual verification status (what you checked and confirmed)
- Any post-processing applied (cropping, resizing)

**Gate**: Output file exists with non-zero size AND visual inspection passed. Generation is complete.

---

## Script Reference

### generate_image.py

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
1. Add more detail to the prompt — vague prompts sometimes fail
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

## Anti-Patterns

### Anti-Pattern 1: Inventing Model Names
**What it looks like**: `model="gemini-2.5-flash-image-preview-12-25"` or `model="gemini-3-flash-image"`
**Why wrong**: These models do not exist. Date suffixes are for text models only. The API returns cryptic errors.
**Do instead**: Use exactly `gemini-2.5-flash-image` or `gemini-3-pro-image-preview`. No variations.

### Anti-Pattern 2: Skipping Environment Validation
**What it looks like**: Running `generate_image.py` without checking API key or dependencies first
**Why wrong**: Produces confusing error messages. Wastes time debugging environment issues as generation bugs.
**Do instead**: Complete Phase 1 (ENVIRONMENT) before any generation attempt. Always.

### Anti-Pattern 3: Generating Without Visual Verification
**What it looks like**: Running the script, checking file size, and committing the image without reading it to visually inspect
**Why wrong**: The file may exist with correct dimensions but contain watermarks, wrong composition, excessive padding, or content that doesn't match the prompt. A 952KB PNG with a cat watermark and wrong aspect ratio passed file-exists checks but looked bad in the README.
**Do instead**: Complete Phase 4 (VERIFY) including Step 3 (visual inspection). Read the image file with the Read tool. Check composition, content, and artifacts before delivering or committing.

### Anti-Pattern 4: Writing Custom Generation Code Instead of Using the Script
**What it looks like**: Writing inline Python to call the Gemini API directly instead of using `generate_image.py`
**Why wrong**: Misses retry logic, rate limiting, post-processing, model validation, and error handling already built into the script.
**Do instead**: Always use the provided `generate_image.py` script. It handles all edge cases.

### Anti-Pattern 5: Storing Base64 in Memory Instead of Saving to File
**What it looks like**: Keeping image data in a variable without writing to disk
**Why wrong**: Data is lost on exit, cannot be used by other tools, wastes memory for large images.
**Do instead**: Save to file immediately. The script does this automatically.

---

## References

This skill uses these shared patterns:
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/prompts.md`: Categorized example prompts by use case (game art, characters, product photography, pixel art, icons)

### Prompt Engineering Quick Reference

**Effective prompt structure**: `[Subject] [Style] [Background] [Constraints]`

**For transparent background post-processing**:
- Use "solid dark gray background" or "solid uniform gray background (#3a3a3a)"
- Include "no background elements or scenery" and "no ground shadows"
- Combine with `--transparent-bg` flag

**For clean edges**: "clean edges", "sharp outlines", "heavy ink outlines"

**Negative constraints**: Always include "no text", "no labels", "no watermarks", "character only"

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "I know the right model name" | Model names are exact strings, not patterns | Check the two valid names |
| "Output file was probably created" | Probably is not verified | Run `ls -la` on the output path |
| "API key is probably set" | Silent failures waste debugging time | Check explicitly in Phase 1 |
| "Custom code is faster than the script" | Script has retry, rate limiting, validation | Use `generate_image.py` |
