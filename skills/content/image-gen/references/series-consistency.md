# Series Consistency

Always-load reference. Apply to every generation request, single or multi-image.

## Prompt-File-First Rule

Write all prompt files before the first API call. Reason: the anchor chain requires image 1's output as input to image 2. If prompts are written during generation, image 2's prompt may be revised after seeing image 1 — breaking the written record and making reruns impossible.

Order of operations for any series:
1. Write `prompts/{series-name}-01.md`
2. Write `prompts/{series-name}-02.md` through `prompts/{series-name}-NN.md`
3. Review all prompt files
4. Call generation scripts in order

## Anchor-Chain Algorithm

Character drift — when image 2's character looks different from image 1 — occurs when each image is generated independently. The anchor chain prevents drift by passing the previous output as a style/identity reference.

### Single image (no chain needed)

```bash
python3 skills/content/image-gen/scripts/nano-banana-generate.py generate \
  --prompt "$(cat prompts/warrior-01.md | tail -n +5)" \
  --output output/warrior-01.png \
  --model pro --aspect-ratio 1:1
```

### Series: image 1 (no reference)

```bash
python3 skills/content/image-gen/scripts/nano-banana-generate.py generate \
  --prompt "$(cat prompts/hero-series-01.md | tail -n +5)" \
  --output output/hero-series-01.png \
  --model pro --aspect-ratio 1:1 \
  --save-original output/originals/hero-series-01.png
```

### Series: image 2+ (with anchor reference)

```bash
python3 skills/content/image-gen/scripts/nano-banana-generate.py with-reference \
  --prompt "$(cat prompts/hero-series-02.md | tail -n +5)" \
  --reference output/hero-series-01.png \
  --output output/hero-series-02.png \
  --model pro --aspect-ratio 1:1 \
  --save-original output/originals/hero-series-02.png
```

### Series: image N (chain continues)

Each image N uses image N-1 as `--reference`. The chain is:

```
image-01.png (no ref) → image-02.png (ref=01) → image-03.png (ref=02) → ...
```

## File Naming Convention

| Context | Pattern | Example |
|---|---|---|
| Single image | `prompts/YYYY-MM-DD-{slug}.md` | `prompts/2026-05-31-warrior-sprite.md` |
| Series prompt N | `prompts/{series-name}-{N:02d}.md` | `prompts/hero-series-01.md` |
| Series output N | `output/{series-name}-{N:02d}.png` | `output/hero-series-01.png` |
| Series original N | `output/originals/{series-name}-{N:02d}.png` | `output/originals/hero-series-01.png` |

## Why Originals Matter

Save originals for any batch or expensive generation with `--save-original` (single) or `--originals-dir` (batch). Re-processing a saved original is free. Re-generating from the API costs quota and may produce a different result, breaking the anchor chain.

## Prompt File Format

```markdown
---
model: gemini-3-pro-image-preview
aspect-ratio: 1:1
flags: [--save-original output/originals/hero-series-01.png]
---

Full body warrior, Slay the Spire card game style, solid dark gray background
color only, golden glowing outline around character, clean digital hand-painted
style, heavy ink outlines, ONE character only, no text, no labels.
```

The `tail -n +5` in the generation commands strips the frontmatter (4 lines + blank) and passes only the prompt body to the script.
