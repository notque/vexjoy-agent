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
    - phaser-gamedev
    - threejs-builder
    - python-general-engineer
---

# Game Sprite Pipeline

Local-first AI sprite generation. One skill, three modes behind `--mode`:

- `portrait` — single full-body character PNG (road-to-aew wrestlers, card-game characters).
- `portrait-loop` — 2×2 = 4-frame subtle idle (breathing + blink) at 200ms/frame in ONE Codex call. Animated portraits without re-prompting new poses.
- `spritesheet` — animated multi-frame grid with connected-components detection, ground-line anchor alignment, and Phaser atlas output.

Backend: Codex CLI imagegen, sole backend. No fallback. No paid APIs (no Gemini, no Nano Banana, no `remove.bg`, no separate `OPENAI_API_KEY`). When Codex is unavailable, the skill fails loud with an actionable error message rather than silently calling a paid alternative. Reference implementation of the "Local-First, Deterministic Systems Over External APIs" principle in `docs/PHILOSOPHY.md`.

## When to use

| User says | Mode | Entry script |
|-----------|------|--------------|
| "generate a wrestler portrait" | `portrait` | `portrait_pipeline.py` |
| "add a new enemy to road-to-aew" | `portrait` | `portrait_pipeline.py --target road-to-aew` |
| "animated idle portrait" / "subtle breathing loop" | `portrait-loop` | `portrait_pipeline.py --mode portrait-loop` |
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
| picking or troubleshooting a backend | `references/backend-chain.md` | Codex CLI invocation pattern + failure modes |
| spritesheet Phase D | `references/frame-detection.md` | connected-components algorithm |
| spritesheet Phase F | `references/anchor-alignment.md` | shared-scale + bottom-anchor math |
| any bg removal phase | `references/bg-removal-local.md` | magenta chroma + rembg |
| Phase H assembly / output shape | `references/output-formats.md` | PNG / GIF / WebP / atlas JSON |
| any phase errors | `references/error-catalog.md` | failure mode → fix mapping |
| user reports clipping / blank cells / cut effects | `references/error-catalog.md` (top section) | "Codex Regeneration as a Post-Processing Fix" anti-pattern; debug slicer, never raw |
| asset has effects (fire, projectile trails, auras, extended limbs) | `references/error-catalog.md` + use `slice_with_content_awareness` | content extending past cell boundaries needs centroid-ownership extraction |
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

## Portrait-loop-mode pipeline (5 phases)

| Phase | Script | What |
|-------|--------|------|
| A1 — Prompt build | `sprite_prompt.py build-portrait-loop` | Slot-structured prompt: same character, same pose, same framing, only breath + blink variation across 4 cells. |
| A2 — Backend dispatch | `sprite_generate.py generate-portrait` | Codex CLI call; produces a 1024×1024 PNG with 2×2 cells of 512×512. |
| D — Per-cell extract | inline in `portrait_pipeline.run_portrait_loop` | Naive 2×2 cell crop (cells are well-defined here). |
| E — Per-cell bg removal | `sprite_process.chroma_pass1` + `chroma_pass2_edge_flood` + `alpha_fade_magenta_fringe` + `color_despill_magenta` + `dilate_alpha_zero` | Same despill chain as portrait/spritesheet modes. |
| F — Ground-line anchor | `sprite_process.detect_ground_line` + `apply_ground_line_anchor` | Drift-free: the four near-identical bodies stay perfectly registered across the loop. |
| H — Assembly | inline | PNG sheet, animated GIF (200ms/frame, 800ms loop), animated WebP, per-frame PNGs. |

End-to-end: `python3 scripts/portrait_pipeline.py --mode portrait-loop --display-name "..." --description "..." --style <preset>`.

The loop must be SUBTLE: viewers should barely notice the animation (just feels alive). New poses defeat the purpose — that's spritesheet mode. See `references/prompt-rules.md` for the loop prompt template.

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

## Backend (Codex CLI only)

Per generation call:

1. `codex` in `PATH` and `codex --version` exits 0 → use Codex CLI imagegen via `codex exec` (the agent's internal `image_gen` tool, prompted to save at an absolute path).
2. Else fail loudly:
   ```
   ERROR: Codex CLI is not available.
   Install Codex CLI and run `codex login`, then retry.
   This skill uses Codex as its sole backend. There is no fallback to
   paid APIs (no Gemini, no Nano Banana, no OpenAI direct).
   ```

Never call `api.openai.com`, `remove.bg`, Gemini, Nano Banana, or any other paid endpoint. A silent paid fallback violates the Local-First principle — breakage must be visible. See `references/backend-chain.md` for the actual invocation shape and failure modes.

## --max-frames: pack the canvas

One Codex imagegen call produces ONE image. To get N frames, pack as many cells as possible into that one image rather than firing N calls.

`--max-frames` (on `sprite_canvas.py make-template` and `sprite_pipeline.py`) auto-computes the largest square grid that fits `--max-canvas` (default 1024x1024) at the given `--cell-size`:

```bash
# 4x4 = 16 frames at 256px on a 1024 canvas (default)
python3 sprite_pipeline.py --description "knight walk cycle" \
    --style snes-16bit-jrpg --cell-size 256 --max-frames --action walking

# 8x8 = 64 frames at 128px on a 1024 canvas
python3 sprite_pipeline.py --description "tiny adventurer, attack cycle" \
    --style nes-8bit --cell-size 128 --max-frames --action attack-punch

# 16x16 = 256 frames at 64px on a 1024 canvas (extreme density)
python3 sprite_pipeline.py --description "GB-era hero, 4-direction walk" \
    --style gameboy-4color --cell-size 64 --max-frames --action walking
```

`--max-frames` overrides `--grid`; the chosen grid is logged to stderr. See `references/grid-shapes.md` for the cell-size → max-grid → total-frames table at canvas sizes 1024, 1536, and 2048.

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

- **Paid APIs are forbidden.** Codex CLI is the sole backend. No Gemini, no Nano Banana, no `remove.bg`, no separate `OPENAI_API_KEY`. Violating this violates the Local-First principle.
- **Magenta background (`#FF00FF`)** is the chroma-key default because it never appears in realistic character skin or wrestling gear. Backend prompts include explicit "solid magenta background" instruction; post-processing validates the dominant corner color.
- **Fixed seed per run** for reproducibility. Re-running with the same `--seed` should produce identical output given identical backend output (best-effort: Codex CLI does not currently expose a public seed flag, so the seed travels in the prompt body as a comment).

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

**Error: "Codex CLI is not available"**
- Cause: `codex` CLI is not installed or `codex --version` failed.
- Solution: Install Codex CLI (`npm install -g @openai/codex` or per-OS) and run `codex login`. Never add `OPENAI_API_KEY`/`GEMINI_API_KEY` for this skill — paid fallbacks are intentionally prohibited.

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

### Anti-pattern: Codex regeneration as a post-processing fix

**What it looks like:** A verifier flags a blank cell, clipped fire, missing silhouette, or any other final-asset defect. The reflex is to re-run `codex exec` to redraw the raw with a different prompt or seed. STOP.

**Why wrong:** Codex generation is treated as ground truth. The raw PNG in `/tmp/sprite-demo/raw/<slug>.png` is what Codex painted, and it is almost always correct. If the final-sheet shows blank cells, clipped effects, or missing silhouettes, the bug is in one of the post-processing steps:
- `slice_grid_cells` derived the wrong pitch (raw_size / grid math) and cut the cell at the wrong place
- `slice_with_content_awareness` claimed a component to the wrong cell (centroid mapping bug)
- The despill chain (`chroma_pass2_edge_flood`, `kill_pink_fringe`, `neutralize_interior_magenta_spill`) ate the silhouette
- The mass-centroid anchor pinned the wrong body part to the ground line
- The LANCZOS resize between magenta padding and content created pink fringe

The user's framing: "the codex generation has never failed, it is working perfectly, the rest has failed."

**Do instead:** Open the raw and the final side-by-side. Confirm the raw has the content (it almost always does). Trace which post-processing step lost it. Specifically for boundary clipping (asset 27 dragon flame, asset 30 plasma trail): set `has_effects: True` and/or `content_aware_extraction: True` in the spec to use `slice_with_content_awareness`, which expands cell windows to recover content extending past conceptual cell boundaries.

See `references/error-catalog.md` for the full diagnostic procedure.

### Anti-pattern: Calling a paid API when Codex fails

**What it looks like:** Adding a try/except that falls back from Codex CLI → Nano Banana / Gemini / OpenAI direct.

**Why wrong:** Silent paid fallbacks make cost invisible; the user loses the ability to opt out. The Local-First principle requires visible failure when free backends are absent, not silent monetization. We removed the Nano Banana branch from this skill exactly to enforce this.

**Do instead**: Fail loudly when Codex is missing or unauthenticated. Tell the user exactly what is missing and how to fix it. If they want a second backend, they should add it explicitly via a separate skill or a deliberate env-var-gated path — not a silent runtime fallback.

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
- `references/backend-chain.md` — Codex CLI invocation pattern, auth checks, failure modes.
- `references/frame-detection.md` — connected-components algorithm, minimum-separation gap, component filter.
- `references/anchor-alignment.md` — shared-scale percentile, bottom-anchor math, horizontal centering.
- `references/bg-removal-local.md` — two-pass chroma, rembg opt-in, anti-patterns.
- `references/output-formats.md` — PNG / GIF / WebP / atlas JSON / strips matrix per mode.
- `references/error-catalog.md` — error message → cause → fix, per phase.
- `references/road-to-aew-integration.md` — snake_case naming, deploy paths, manifest regen.

## Demo idempotency

Demo orchestrators (e.g. `/tmp/sprite-demo/generate.py`) should be idempotent: running them again on a partial output skips assets whose `assets/<slug>/final.png` (or `final-sheet.png`) AND `meta.json` already exist. This saves ~30-60s per asset of Codex CLI time when iterating. The pattern:

```python
def _is_done(asset_dir: Path) -> bool:
    if not (asset_dir / "meta.json").exists():
        return False
    if (asset_dir / "final.png").exists() or (asset_dir / "final-sheet.png").exists():
        return True
    return False

def run_one(spec, force=False):
    if not force and _is_done(asset_dir):
        return existing_meta  # log "skipping" + return
    ...
```

Provide `--force` to override (re-run all) and `--force-slug <prefix>` to re-run a specific asset. Document the behavior in the orchestrator's docstring so future maintainers don't accidentally regenerate everything.

## Related skills

- `phaser-gamedev` — downstream consumer of spritesheet output (atlas JSON).
- `threejs-builder` — may consume portrait output for 3D card framing.
- `game-asset-generator` — sibling umbrella for 3D models / textures / matrix-driven pixel art. Its `references/pixel-art-sprites.md` redirects AI-driven sprite work here.
- `game-pipeline` — parent lifecycle orchestrator; slot this skill under its ASSETS phase when building a new game.
