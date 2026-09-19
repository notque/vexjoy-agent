---
name: image-gen
description: "AI image generation: Gemini and Nano Banana backends; single/series/batch workflows with prompt-to-disk."
agent: python-general-engineer
user-invocable: false
routing:
  category: image-generation
  triggers:
    - generate image
    - create image
    - image generation
    - AI image
    - gemini image
    - make image
    - draw
    - illustrate
    - sprite generation
    - card art
    - batch generation
    - series of images
    - character art
    - pixel art
    - image post-processing
    - make a picture
    - create art
    - generate a picture
    - make art
    - generate artwork
    - create artwork
  not_for: "HTML visualization or charts (use html-artifact), or deterministic non-AI palette/matrix pixel art (use game-asset-generator)"
  pairs_with:
    - python-general-engineer
    - game-dev
---

# image-gen

Backend-agnostic image generation: single images, series with anchor-chain consistency, batch pipelines. Two backends: Gemini (API) and Nano Banana (local scripts with post-processing).

## Deep References

| Signal | Load | Content |
|---|---|---|
| Gemini backend selected | `references/backends/gemini.md` | Models, env vars, flag table, examples, error codes |
| Nano Banana needed (post-processing, series, JSON batch, style-match) | `references/backends/nano-banana.md` | Subcommands, flags, aspect ratios, prompt patterns by asset type |

## Phase 1: Detect Backend

```bash
python3 skills/content/image-gen/scripts/detect-backend.py
```

- `gemini` -- load `references/backends/gemini.md`
- `ask` -- no key found; ask the user to set `GEMINI_API_KEY`

**Gate**: backend confirmed.

## Phase 2: Write Prompt Files

Write all prompts to disk before any API call. Prompt files are the generation record and anchor-chain input for series.

File naming: single `prompts/YYYY-MM-DD-{slug}.md`, series `prompts/{series-name}-01.md` through `-NN.md`.

```markdown
---
model: gemini-3-pro-image-preview
aspect-ratio: 1:1
flags: []
---

Full prompt text. Be explicit about subject, style, background, constraints.
```

```bash
mkdir -p prompts
```

For series: write ALL prompt files before calling any generation script.

**Gate**: all prompt files written and reviewed.

## Phase 3: Select Script

| Use case | Script | Subcommand |
|---|---|---|
| Single image, Gemini | `scripts/generate_image.py` | `--prompt` |
| Batch from text file, Gemini | `scripts/generate_image.py` | `--batch` |
| Single with post-processing | `scripts/nano-banana-generate.py` | `generate` |
| Style match from reference | `scripts/nano-banana-generate.py` | `with-reference` |
| Batch from JSON manifest | `scripts/nano-banana-generate.py` | `batch` |
| Series (anchor chain) | `scripts/nano-banana-generate.py` | `generate` then `with-reference` |
| Post-processing only | `scripts/nano-banana-process.py` | `crop` / `remove-bg` / `pipeline` |

Model selection:

| Scenario | Model |
|---|---|
| Draft, testing, batch, cost-sensitive | `gemini-2.5-flash-image` (2-5s) |
| Final asset, character art, typography | `gemini-3-pro-image-preview` (~30s) |

Aspect ratio by use case:

| Asset type | Ratio |
|---|---|
| Sprites, characters, icons | `1:1` |
| Card art, landscape | `16:9` |
| Vertical maps, portrait bg | `9:16` |
| Portrait cards | `3:4` |
| Wide banners | `21:9` |

Generate at the target ratio. Generating 1:1 and cropping to 16:9 loses 56% of pixels.

**Gate**: script and subcommand identified.

## Phase 4: Generate

Use absolute paths for output files. Show full script output.

### Anchor-Chain Algorithm (Series)

Character drift occurs when images are generated independently. Prevent it by passing the previous output as `--reference`:

```
image-01.png (no ref) -> image-02.png (ref=01) -> image-03.png (ref=02) -> ...
```

1. Generate image 1 with no reference.
2. Use output of image 1 as `--reference` for image 2.
3. Continue: each image N references image N-1.

Save originals with `--save-original` for any batch or expensive generation. Re-processing a saved original is free; re-generating costs quota and may break the chain.

**Gate**: script exits 0.

## Phase 5: Verify and Report

Read the generated image to verify:
- Subject matches prompt
- No unwanted watermarks or artifacts
- Aspect ratio and framing correct
- No excessive padding or dark borders

If inspection fails: regenerate with adjusted prompt. Report the issue before retrying.

Report: output file path (absolute), dimensions, model, post-processing applied, verification result. Report only what was requested.

## Error Handling

| Error | Cause | Resolution |
|---|---|---|
| `GEMINI_API_KEY not set` | Missing env var | `export GEMINI_API_KEY=your_key` |
| `No image in response` | Safety filter or text-only response | Adjust prompt; remove policy-adjacent content |
| `Missing dependency: google-genai` | Package absent | `pip install google-genai pillow` |
| `Rate limit exceeded (429)` | Too many requests | Increase `--delay`; script retries automatically |
| `Content policy violation (400)` | Restricted content | Rephrase using neutral language |
| Model not found | Wrong model string | Use exact strings: `gemini-2.5-flash-image` or `gemini-3-pro-image-preview` |
