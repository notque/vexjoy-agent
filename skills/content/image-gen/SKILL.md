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

Use the repository scripts instead of constructing API calls.

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

## Select Script

| Use case | Script | Subcommand |
|---|---|---|
| Single image, Gemini | `scripts/generate_image.py` | `--prompt` |
| Batch from text file, Gemini | `scripts/generate_image.py` | `--batch` |
| Single with post-processing | `scripts/nano-banana-generate.py` | `generate` |
| Style match from reference | `scripts/nano-banana-generate.py` | `with-reference` |
| Batch from JSON manifest | `scripts/nano-banana-generate.py` | `batch` |
| Series (anchor chain) | `scripts/nano-banana-generate.py` | `generate` then `with-reference` |
| Post-processing only | `scripts/nano-banana-process.py` | `crop` / `remove-bg` / `pipeline` |

Generate at the target ratio. Generating 1:1 and cropping to 16:9 loses 56% of pixels.

## Generate

Use absolute paths for output files. Show full script output.

### Anchor-Chain Algorithm (Series)

Character drift occurs when images are generated independently. Prevent it by passing the previous output as `--reference`:

```
image-01.png (no ref) -> image-02.png (ref=01) -> image-03.png (ref=02) -> ...
```

Write every series prompt before spending quota. Generate image 1 without a reference; each later image references its immediate predecessor.

Save originals with `--save-original` for any batch or expensive generation. Re-processing a saved original is free; re-generating costs quota and may break the chain.

## Verify and Report

Read the generated image to verify:
- Subject matches prompt
- No unwanted watermarks or artifacts
- Aspect ratio and framing correct
- No excessive padding or dark borders

If inspection fails: regenerate with adjusted prompt. Report the issue before retrying.

Report: output file path (absolute), dimensions, model, post-processing applied, verification result. Report only what was requested.
