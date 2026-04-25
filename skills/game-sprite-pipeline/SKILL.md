---
name: game-sprite-pipeline
version: 1.0.0
description: "AI sprite generation: portrait + animated spritesheet modes, local backends, road-to-aew integration"
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
  - Grep
  - Edit
routing:
  triggers:
    - generate sprite
    - generate wrestler
    - generate character portrait
    - spritesheet pipeline
    - animated sprite
    - road-to-aew sprite
    - sprite for road-to-aew
    - wrestler portrait
    - character sheet
  complexity: Complex
  category: game
  pairs_with:
    - nano-banana-builder
    - phaser-gamedev
    - threejs-builder
    - python-general-engineer
---

# Game Sprite Pipeline

Local-first AI sprite generation. One skill, two modes behind `--mode`:

- `portrait` — single full-body character PNG (road-to-aew wrestlers, card-game characters).
- `spritesheet` — animated multi-frame grid with connected-components detection, anchor alignment, and Phaser atlas output.

Backend chain: Codex CLI imagegen primary, Gemini Nano Banana fallback, fail-loud on absence. No paid APIs (no `remove.bg`, no separate `OPENAI_API_KEY`). Reference implementation of the "Local-First, Deterministic Systems Over External APIs" principle in `docs/PHILOSOPHY.md`.

## When to use

| User says | Mode | Entry script |
|-----------|------|--------------|
| "generate a wrestler portrait" | `portrait` | `portrait_pipeline.py` |
| "add a new enemy to road-to-aew" | `portrait` | `portrait_pipeline.py --target road-to-aew` |
| "make a walk cycle spritesheet" | `spritesheet` | `sprite_pipeline.py` |
| "4-direction character sheet" | `spritesheet` | `sprite_pipeline.py --grid 4x4` |
| "Phaser-ready texture atlas" | `spritesheet` | `sprite_pipeline.py` (emits atlas JSON) |

Portrait is the road-to-aew immediate need; spritesheet is the forward-looking capability. Both share one backbone (prompt scaffolding, backend dispatch, bg removal, validation).

## Reference Loading Table

| Signal | Load | Why |
|--------|------|-----|
| picking a style preset | `references/style-presets.md` | 9 era/hardware presets + custom slot |
| `--target road-to-aew` or `--archetype` | `references/wrestler-archetypes.md` | 9 color archetypes + 10 gimmick types + tier |
| sizing `--grid CxR` / `--cell-size` | `references/grid-shapes.md` | allowed dims, direction conventions |
| building a prompt | `references/prompt-rules.md` | ART_STYLE, CHAR_STYLE, GRID_RULES slot contents |
| picking or troubleshooting a backend | `references/backend-chain.md` | Codex CLI vs Nano Banana decision tree |
| spritesheet Phase D | `references/frame-detection.md` | connected-components algorithm |
| spritesheet Phase F | `references/anchor-alignment.md` | shared-scale + bottom-anchor math |
| any bg removal phase | `references/bg-removal-local.md` | magenta chroma + rembg |
| Phase H assembly / output shape | `references/output-formats.md` | PNG / GIF / WebP / atlas JSON |
| any phase errors | `references/error-catalog.md` | failure mode → fix mapping |
| `--target road-to-aew` deploy | `references/road-to-aew-integration.md` | snake_case, paths, manifest regen |

Load greedily when a signal matches — references are only read on demand, so the cost is paid once per execution, not once per routing decision.

## Portrait-mode pipeline (5 phases)

| Phase | Script | What |
|-------|--------|------|
| A — Character generation | `sprite_prompt.py build-portrait` + `sprite_generate.py generate-portrait` | Build prompt from style+archetype+description; dispatch backend. |
| B — Background removal | `sprite_process.py remove-bg` | Magenta chroma key (two-pass); rembg fallback if installed. |
| C — Trim and center | `sprite_process.py normalize --mode portrait` | Auto-trim transparent borders; re-canvas with ~5-10% padding; bottom-anchor. |
| D — Dimension validation | `sprite_process.py validate-portrait` | Width ∈ [350, 850], height ∈ [900, 1100], aspect ∈ [1:1.5, 1:2.5]. |
| E — Project-aware deploy | `road_to_aew_integration.py deploy` | Snake_case name, path resolution; `npm run generate:sprites` if `--regen-manifest`. |

End-to-end: `python3 scripts/portrait_pipeline.py --prompt "<desc>" --style <preset> [--target road-to-aew]`.

## Spritesheet-mode pipeline (8 phases)

| Phase | Script | What |
|-------|--------|------|
| A — Reference character | `sprite_prompt.py build-character` + `sprite_generate.py generate-character` | 1024x1024 magenta-bg reference PNG. |
| B — Canvas prep | `sprite_canvas.py make-template` | Pillow grid (CxR cells, magenta bg, thin borders). No LLM. |
| C — Spritesheet generation | `sprite_prompt.py build-spritesheet` + `sprite_generate.py generate-spritesheet` | Character + canvas as references; action prompt. |
| D — Frame detection | `sprite_process.py extract-frames` | Connected-components clustering (not naive grid math). See `references/frame-detection.md`. |
| E — Per-frame bg removal | `sprite_process.py remove-bg` | Same chroma engine as portrait mode, looped per frame. |
| F — Normalization & anchor | `sprite_process.py normalize --mode spritesheet` | Shared-scale rescale + bottom-anchor alignment. |
| G — Auto-curation | `sprite_process.py auto-curate` | Deterministic rank: fewest edge-touches → smallest scale variance → lowest seed. |
| H — Final assembly | `sprite_process.py assemble` | PNG sheet, GIF, WebP, per-frame PNGs, Phaser atlas JSON, per-direction strips (4xR / 8xR only). |

End-to-end: `python3 scripts/sprite_pipeline.py --prompt "<desc>" --grid <CxR> --cell-size 256`.

## Backend chain

Decision tree, evaluated per generation call:

1. `codex` in `PATH` and auth check succeeds → Codex CLI imagegen via `codex exec "<prompt>"`. User's existing paid subscription. No separate API key.
2. Else `GEMINI_API_KEY` in env → dispatch to `nano-banana-builder`'s scripts (`nano-banana-generate.py generate` or `with-reference`).
3. Else fail loudly:
   ```
   ERROR: No image-generation backend available.
   Install Codex CLI and authenticate, or set GEMINI_API_KEY.
   This skill does not call paid APIs directly.
   ```

Never call `api.openai.com`, `remove.bg`, or any other paid endpoint. A silent paid fallback violates the Local-First principle — breakage must be visible. See `references/backend-chain.md` for detection commands and failure modes.

## Dimension and cell policy

**Portrait mode** — variable output, validated after trim:
- width 350-850, height 900-1100, aspect 1:1.5 to 1:2.5 (h:w).
- `--force-dimensions` skips the gate (emergency only; logged loudly).

**Spritesheet mode** — fixed cells:
- cell-size in {64, 128, 192, 256, 384, 512}; default 256.
- grid `CxR` via `--grid`; total canvas <= 2048x2048.
- `--grid 4xR` or `--grid 8xR` triggers per-direction strip output.

See `references/grid-shapes.md` for direction-to-row conventions.

## Auto-curation (deterministic)

Default. Applied when `--variants N` > 1.

1. Fewest edge-touch frames wins (sprite touching canvas edge = clipping).
2. Tiebreak: smallest shared-scale variance (visually consistent height across frames).
3. Tiebreak: lowest seed number (reproducible tie resolution).

`--curate` writes a contact sheet and opens a manual review gate. Off by default; interactive gates block automation.

## Shared constraints

- **Paid APIs are forbidden.** The skill uses only Codex CLI and Gemini Nano Banana (both user-existing). No `remove.bg`, no separate `OPENAI_API_KEY`. Violating this violates the Local-First principle.
- **Magenta background (`#FF00FF`)** is the chroma-key default because it never appears in realistic character skin or wrestling gear. Backend prompts include explicit "solid magenta background" instruction; post-processing validates the dominant corner color.
- **Fixed seed per run** for reproducibility. Re-running with the same `--seed` should produce identical output given identical backend output.

## Verification

Before shipping any change to this skill, run:

```bash
cd /home/feedgen/claude-code-toolkit
python3 scripts/generate-skill-index.py
python3 scripts/validate-references.py --check-do-framing
ruff check . --config pyproject.toml
ruff format --check . --config pyproject.toml
```

Plus the two smoke tests:

```bash
# Portrait (no backend required in dry-run)
python3 skills/game-sprite-pipeline/scripts/portrait_pipeline.py \
    --prompt "veteran wrestler, indie circuit, 35yo, scarred face, leather jacket" \
    --style slay-the-spire-painted --target road-to-aew --dry-run

# Spritesheet (no backend required in dry-run)
python3 skills/game-sprite-pipeline/scripts/sprite_pipeline.py \
    --prompt "wrestler walk cycle, 4 frames" \
    --grid 4x1 --cell-size 256 --dry-run
```

Both dry-run modes skip the backend call, generate a synthetic fixture, and exercise every post-processing phase. Pass criteria: exit 0, expected output files present, dimension gates satisfied.

## Error handling

**Error: "No image-generation backend available"**
- Cause: Neither `codex` CLI nor `GEMINI_API_KEY` is detectable.
- Solution: Install Codex CLI and authenticate with `codex auth`; or `export GEMINI_API_KEY=...`. Never add `OPENAI_API_KEY` — the skill does not use it directly.

**Error: "Aspect ratio X outside allowed range [1:1.5, 1:2.5]"**
- Cause: Character rendered too wide (crouched pose) or too tall (full-extension jump pose).
- Solution: Re-generate with a neutral standing prompt. If the character must have an atypical pose, add `--force-dimensions` (logs loudly, should not become routine).

**Error: "Frame count mismatch: detected 6 components, grid expected 8"**
- Cause: Connected-components merged neighboring frames, or small fragments were filtered.
- Solution: Increase cell-size (gives more separation gap), re-generate, or use `--chroma-threshold` to tighten the bg mask. See `references/frame-detection.md`.

**Error: "Codex CLI grid-template input not supported"**
- Cause: Codex imagegen may not consume a magenta grid canvas as a structural input.
- Solution: Skill auto-falls-back to per-frame generation + Pillow compositing. Slower but deterministic.

**Error: "rembg not installed"**
- Cause: `--bg-mode rembg` requested without the opt-in dependency.
- Solution: `pip install rembg onnxruntime` (~200MB ONNX model). Or re-run with default magenta chroma key.

**Error: "road-to-aew directory not found at ~/road-to-aew"**
- Cause: `--target road-to-aew` resolves to a path that does not exist.
- Solution: Pass `--target-dir <explicit-path>` or clone the repo to `~/road-to-aew`. The deploy step refuses to guess.

<!-- no-pair-required: section header; pairs live in subsections -->
## Anti-patterns

### Anti-pattern: Calling a paid API when a free one fails

**What it looks like:** Adding a try/except that falls back from Codex CLI → Nano Banana → OpenAI API with a separate key.

**Why wrong:** Silent paid fallbacks make cost invisible; the user loses the ability to opt out. The Local-First principle requires visible failure when free backends are absent, not silent monetization.

**Do instead**: Keep the two-step chain (Codex → Nano Banana) and fail loudly at step 3. If a user wants a third backend, they add it explicitly in configuration with a deliberate environment variable, not as a silent fallback.

### Anti-pattern: Naive grid-math frame cropping

**What it looks like:** `frame = sheet.crop((col*CELL, row*CELL, (col+1)*CELL, (row+1)*CELL))` for every cell.

**Why wrong:** Generated frames drift within their cells (the model does not respect grid boundaries precisely). Naive cropping captures neighbor-cell pixels and truncates the current sprite.

**Do instead**: Use connected-components clustering (flood-fill from non-magenta pixels, bound each cluster by its actual pixel extent). See `references/frame-detection.md`.

### Anti-pattern: Trusting the backend's alpha channel

**What it looks like:** Prompting "transparent background" and consuming the output PNG directly.

**Why wrong:** Both Codex CLI and Nano Banana produce backgrounds that are nominally transparent but often have magenta/white/gray fringing, full-opacity backgrounds, or inconsistent alpha. Downstream consumers get dirty assets.

**Do instead**: Always post-process: prompt for a known chroma color (magenta `#FF00FF`), then run local bg removal. Two-pass flood fill handles feathering. `references/bg-removal-local.md` has the algorithm.

### Anti-pattern: Interactive curation as the default

**What it looks like:** Every pipeline run opens a contact-sheet viewer and waits for user confirmation.

**Why wrong:** Blocks automation (batch generation of 50 wrestlers), adds cognitive load, and prevents reproducibility. The user is not always at the keyboard.

**Do instead**: Deterministic auto-curation is the default (rank by edge-touches → scale variance → seed). Expose `--curate` for cases where the automated pick is visibly wrong. Reproducibility matters more than picking the single prettiest variant.

## Reference files

- `references/style-presets.md` — full catalog of 9 era/hardware presets, prompt fragments, `--style custom` slot.
- `references/wrestler-archetypes.md` — 9 color archetypes, 10 gimmick types, tier modifiers (Act 1/2/3).
- `references/grid-shapes.md` — cell-size table, grid validation, direction-to-row mapping.
- `references/prompt-rules.md` — ART_STYLE, CHAR_STYLE, GRID_RULES slot content; negative prompts.
- `references/backend-chain.md` — Codex CLI vs Nano Banana detection, auth checks, failure modes.
- `references/frame-detection.md` — connected-components algorithm, minimum-separation gap, component filter.
- `references/anchor-alignment.md` — shared-scale percentile, bottom-anchor math, horizontal centering.
- `references/bg-removal-local.md` — two-pass chroma, rembg opt-in, anti-patterns.
- `references/output-formats.md` — PNG / GIF / WebP / atlas JSON / strips matrix per mode.
- `references/error-catalog.md` — error message → cause → fix, per phase.
- `references/road-to-aew-integration.md` — snake_case naming, deploy paths, manifest regen.

## Related skills

- `nano-banana-builder` — fallback backend; this skill dispatches to its scripts.
- `phaser-gamedev` — downstream consumer of spritesheet output (atlas JSON).
- `threejs-builder` — may consume portrait output for 3D card framing.
- `game-asset-generator` — sibling umbrella for 3D models / textures / matrix-driven pixel art. Its `references/pixel-art-sprites.md` redirects AI-driven sprite work here.
- `game-pipeline` — parent lifecycle orchestrator; slot this skill under its ASSETS phase when building a new game.
