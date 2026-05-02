---
name: game-sprite-pipeline
version: 1.0.0
description: "AI sprite generation: portraits, idle loops, animated sheets via Codex/Nano Banana. Use for generated character art."
agent: python-general-engineer
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
    - AI sprite
    - AI character art
    - generate character
    - generate sprite
    - generate wrestler
    - generate character portrait
    - spritesheet pipeline
    - animated spritesheet
    - animated sprite
    - portrait loop
    - idle loop
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

Local-first AI sprite generation. Three modes behind `--mode`:

- `portrait` — single full-body character PNG.
- `portrait-loop` — 2x2 = 4-frame subtle idle (breathing + blink) at 200ms/frame in ONE Codex call.
- `spritesheet` — animated multi-frame grid with connected-components detection, ground-line anchor alignment, and Phaser atlas output.

Backend chain (per ADR-198): Codex CLI default. Falls back to Nano Banana via `nano-banana-builder` when Codex unavailable AND `GEMINI_API_KEY`/`GOOGLE_API_KEY` is set. Fails loud with `BackendUnavailableError` listing both fix paths when neither is available. Both paths use user-owned keys only.

## When to use

| User says | Mode | Entry script |
|-----------|------|--------------|
| "generate a wrestler portrait" | `portrait` | `portrait_pipeline.py` |
| "add a new enemy to road-to-aew" | `portrait` | `portrait_pipeline.py --target road-to-aew` |
| "animated idle portrait" / "subtle breathing loop" | `portrait-loop` | `portrait_pipeline.py --mode portrait-loop` |
| "make a walk cycle spritesheet" | `spritesheet` | `sprite_pipeline.py` |
| "4-direction character sheet" | `spritesheet` | `sprite_pipeline.py --grid 4x4` |
| "Phaser-ready texture atlas" | `spritesheet` | `sprite_pipeline.py` (emits atlas JSON) |

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
| asset has effects (fire, projectile trails, auras, extended limbs) | `references/error-catalog.md` + use `slice_with_content_awareness` | Content extending past cell boundaries needs centroid-ownership extraction. ADR-207 RC-1: on dense grids (`cols * rows >= 16` AND both dims >= 4) `--content-aware-extraction` silently downgrades to strict-pitch with a warning unless `--effects-asset` is also passed. Use `--effects-asset` only for genuine sparse-but-cross-boundary content. |
| `--target road-to-aew` deploy | `references/road-to-aew-integration.md` | snake_case, paths, manifest regen |

Load greedily when a signal matches.

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
| A1 — Prompt build | `sprite_prompt.py build-portrait-loop` | Same character, same pose, same framing, only breath + blink variation across 4 cells. |
| A2 — Backend dispatch | `sprite_generate.py generate-portrait` | Codex CLI call; produces 1024x1024 PNG with 2x2 cells of 512x512. |
| D — Per-cell extract | inline in `portrait_pipeline.run_portrait_loop` | Naive 2x2 cell crop (cells are well-defined here). |
| E — Per-cell bg removal | `sprite_process.chroma_pass1` + `chroma_pass2_edge_flood` + `alpha_fade_magenta_fringe` + `color_despill_magenta` + `dilate_alpha_zero` | Same despill chain as portrait/spritesheet modes. |
| F — Ground-line anchor | `sprite_process.detect_ground_line` + `apply_ground_line_anchor` | Drift-free: four near-identical bodies stay registered across the loop. |
| H — Assembly | inline | PNG sheet, animated GIF (200ms/frame, 800ms loop), animated WebP, per-frame PNGs. |

End-to-end: `python3 scripts/portrait_pipeline.py --mode portrait-loop --display-name "..." --description "..." --style <preset>`.

The loop must be SUBTLE: viewers should barely notice the animation (just feels alive). New poses belong in spritesheet mode. See `references/prompt-rules.md` for the loop prompt template.

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

## Backend (Codex default with Nano Banana fallback, per ADR-198)

Per generation call, evaluated in order:

1. `codex` in `PATH` and `codex --version` exits 0 → use Codex CLI imagegen. Codex CLI 0.125+ no longer exposes `--output-image`/`--aspect-ratio`/`--reference`/`--seed` as direct flags; image generation goes through the agent's internal `image_gen` tool via prompt text. Canonical invocation: `codex exec --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check [-i <ref>... --] "<wrapped prompt>"`. Reference list MUST be terminated with `--` before the positional prompt. Subprocess timeout: 360s.
2. Else if `GEMINI_API_KEY` or `GOOGLE_API_KEY` is set → Nano Banana via `nano-banana-builder`'s scripts (`scripts/nano-banana-generate.py with-reference` for reference-guided, `batch` for multi-variant). The skill never imports the Gemini SDK directly.
3. Else fail loudly with `BackendUnavailableError` listing BOTH fix paths:
   ```
   BackendUnavailableError: No image-generation backend available.

   Fix path 1 (Codex CLI, recommended):
     Install Codex CLI and run `codex auth` to authenticate against your existing subscription.

   Fix path 2 (Nano Banana fallback):
     Set GEMINI_API_KEY (or GOOGLE_API_KEY) in your environment to enable the Nano Banana fallback.
   ```

See `references/backend-chain.md` for the locked-in invocation contract and failure modes.

## --max-frames: pack the canvas

One Codex imagegen call produces ONE image. Pack as many cells as possible into that one image rather than firing N calls.

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

Default when `--variants N` > 1.

1. Fewest edge-touch frames wins (sprite touching canvas edge = clipping).
2. Tiebreak: smallest shared-scale variance (visually consistent height).
3. Tiebreak: lowest seed number (reproducible).

`--curate` opens a manual review gate. Off by default; interactive gates block automation.

## Shared constraints

- **User-owned keys only.** Codex CLI and Nano Banana via `GEMINI_API_KEY`/`GOOGLE_API_KEY` are the two authorized backends. The skill never calls `api.openai.com` directly, `remove.bg`, or any unauthorized service. See ADR-198.
- **Magenta background (`#FF00FF`)** is the chroma-key default — never appears in realistic character skin or gear. Backend prompts include explicit "solid magenta background" instruction; post-processing validates dominant corner color.
- **Fixed seed per run** for reproducibility (best-effort: seed travels in the prompt body as a comment since Codex CLI lacks a public seed flag).

## Verification

Before shipping any change to this skill:

```bash
cd /home/feedgen/vexjoy-agent
python3 scripts/generate-skill-index.py
python3 scripts/validate-references.py --check-do-framing
ruff check . --config pyproject.toml
ruff format --check . --config pyproject.toml
```

Smoke tests:

```bash
# Portrait (no backend required in dry-run)
python3 skills/game-sprite-pipeline/scripts/portrait_pipeline.py \
    --prompt "veteran wrestler, indie circuit, 35yo, scarred face, leather jacket" \
    --style slay-the-spire-painted --target road-to-aew --dry-run

# Spritesheet (--allow-frame-duplication because synthetic fixture has 4
# near-identical figures that trip verify_frames_distinct at the 70% threshold)
python3 skills/game-sprite-pipeline/scripts/sprite_pipeline.py \
    --prompt "wrestler walk cycle, 4 frames" \
    --grid 4x1 --cell-size 256 --dry-run --allow-frame-duplication
```

Both dry-run modes skip the backend, generate a synthetic fixture, and exercise every post-processing phase. Pass: exit 0, expected outputs present, dimension gates satisfied.

## Verifier gates (default-on, ADR-199)

Both pipelines run a verifier suite as the LAST step. Default-on; opt out with `--no-verify`.

| Flag | Default | Effect |
|------|---------|--------|
| `--verify` | ON | Run gate suite after assembly. Print JSON to stdout; exit 2 on failure. |
| `--no-verify` | — | Skip all gates. Logs `WARNING: --no-verify opted out; output not validated`. **Spritesheet mode (ADR-207 Rule 4)**: exit code 3 (`VERIFIER_SKIPPED_EXIT_CODE`) instead of 0 so orchestrators cannot mask failures. **Portrait + portrait-loop**: retain exit 0 (small verifier surface). |
| `--allow-frame-duplication` | OFF | Relax `verify_frames_distinct` from 70% to 100% duplicate-pct (ADR-208 RC-3). Use for sheets with legitimate frame repetition (idle loops filling 64 cells, held taunt poses). Without this flag the gate catches layout-drift where centroid mis-routing lands most cells on few poses. |
| `--effects-asset` | OFF | Opt INTO content-aware routing on dense grids (>= 4x4, >= 16 cells). Use ONLY for sparse-but-cross-boundary content (fire breath, plasma trails). Keep dense character grids on strict-pitch (ADR-207 RC-1). |

Per-mode gate selection:

| Mode | Entry | Gates |
|------|-------|-------|
| spritesheet | `sprite_pipeline.py run_pipeline` | `verify_no_magenta`, `verify_grid_alignment`, `verify_anchor_consistency`, `verify_frames_have_content`, `verify_frames_distinct`, `verify_pixel_preservation` (when `{name}_sheet_raw.png` present), `verify_raw_vs_final_cell_parity` (ADR-207 Rule 3) |
| portrait | `portrait_pipeline.py run_pipeline` (mode=portrait) | `verify_no_magenta` |
| portrait-loop | `portrait_pipeline.py run_portrait_loop` | `verify_no_magenta`, `verify_frames_have_content`, `verify_frames_distinct`, `verify_anchor_consistency` |

Output JSON shape:

```json
{
  "passed": false,
  "verifier_verdict": "FAIL",
  "gates_run": ["verify_no_magenta", "verify_grid_alignment", ...],
  "failures": [{"check": "verify_no_magenta", "file": "...", "details": {...}}],
  "backends_available": {"codex": true, "nano_banana": true},
  "elapsed_seconds": 0.21
}
```

`verifier_verdict` (ADR-207 Rule 2) is the contracted consumer-facing field. `write_manifest_record` asserts `verifier_verdict == "PASS"` implies empty `verifier_failures` list (and vice versa).

Exit codes: 0 = passed (or `--no-verify` for portrait modes). 2 = gate failed. 3 = `--no-verify` in spritesheet mode (ADR-207 Rule 4).

## Logging (ADR-202)

Both pipelines emit diagnostics via stdlib `logging` on stderr. Verifier JSON and structured output on stdout. Logger name: `sprite-pipeline.<module>`. Default: INFO.

| Flag | Effect |
|------|--------|
| (none) | INFO: phase boundaries, backend selection, asset paths, per-phase status. |
| `--quiet` / `-q` | WARNING only. Mutually exclusive with `--verbose`. |
| `--verbose` / `-v` | DEBUG: parameter dumps, intermediate counters. Mutually exclusive with `--quiet`. |

Stream contract: stdout = structured output; stderr = diagnostics. Redirect independently.

## Error handling

**"BackendUnavailableError: No image-generation backend available"**
Install Codex CLI (`npm install -g @openai/codex` + `codex auth`), OR set `GEMINI_API_KEY`/`GOOGLE_API_KEY` for Nano Banana fallback. Never set `OPENAI_API_KEY` — direct OpenAI calls are not authorized.

**"Aspect ratio X outside allowed range [1:1.5, 1:2.5]"**
Re-generate with a neutral standing prompt. For atypical poses, use `--force-dimensions` (not routine).

**"Frame count mismatch: detected 6 components, grid expected 8"**
Connected-components merged neighboring frames or small fragments were filtered. Increase cell-size, re-generate, or use `--chroma-threshold` to tighten the bg mask. See `references/frame-detection.md`.

**"Codex CLI grid-template input not supported"**
Skill auto-falls-back to per-frame generation + Pillow compositing. Slower but deterministic.

**"rembg not installed"**
`pip install rembg onnxruntime` (~200MB ONNX model), or re-run with default magenta chroma key.

**"road-to-aew directory not found at ~/road-to-aew"**
Pass `--target-dir <explicit-path>` or clone the repo to `~/road-to-aew`. The deploy step refuses to guess.

<!-- no-pair-required: section header; pairs live in subsections -->
## Failure Patterns

### Failure mode: Codex regeneration as a post-processing fix

**What it looks like:** Verifier flags a blank cell, clipped fire, or missing silhouette. The reflex is to re-run `codex exec`. STOP.

**Why wrong:** The raw PNG is almost always correct. If the final sheet shows defects, the bug is in post-processing: wrong pitch in `slice_grid_cells`, wrong centroid mapping in `slice_with_content_awareness`, despill chain eating the silhouette, mass-centroid anchor pinning wrong body part, or LANCZOS resize creating pink fringe.

**Do instead:** Open raw and final side-by-side. Confirm raw has the content. Trace which post-processing step lost it. For boundary clipping: set `has_effects: True` and/or `content_aware_extraction: True` to use `slice_with_content_awareness`.

**Caveat (ADR-207 RC-1, dense-grid downgrade):** On dense grids (`cols * rows >= 16` AND both dims >= 4), the slicer silently downgrades `--content-aware-extraction` to strict-pitch because content-aware routing on fractional-pitch raws drops cells via centroid drift. To opt in on a dense grid, also pass `--effects-asset`. Character grids with arms touching cell edges should stay on strict slicer.

See `references/error-catalog.md` for the full diagnostic procedure.

### Failure mode: Calling an unauthorized third-party paid API

**What it looks like:** Adding a fallback from Codex CLI → `api.openai.com` direct / `remove.bg` / any service the user did not authorize.

**Do instead:** Stop at the two authorized backends. When neither is available, raise `BackendUnavailableError` with both fix paths. Adding a third backend requires a new env-var-gated path AND an ADR amendment.

### Failure mode: Naive grid-math frame cropping

**What it looks like:** `frame = sheet.crop((col*CELL, row*CELL, (col+1)*CELL, (row+1)*CELL))`.

**Why wrong:** Generated frames drift within cells. Naive cropping captures neighbor-cell pixels and truncates the sprite.

**Do instead:** Connected-components clustering. See `references/frame-detection.md`.

### Failure mode: Trusting the backend's alpha channel

**What it looks like:** Prompting "transparent background" and consuming the output PNG directly.

**Why wrong:** Both backends produce backgrounds with magenta/white/gray fringing, full-opacity backgrounds, or inconsistent alpha.

**Do instead:** Always post-process: prompt for magenta `#FF00FF`, then run local bg removal. Two-pass flood fill handles feathering. See `references/bg-removal-local.md`.

### Failure mode: Interactive curation as the default

**What it looks like:** Every pipeline run opens a contact-sheet viewer and waits for user confirmation.

**Why wrong:** Blocks automation, adds cognitive load, prevents reproducibility.

**Do instead:** Deterministic auto-curation is the default. Expose `--curate` for cases where the automated pick is wrong.

## Reference files

- `references/style-presets.md` — 9 era/hardware presets, prompt fragments, `--style custom` slot.
- `references/wrestler-archetypes.md` — 9 color archetypes, 10 gimmick types, tier modifiers.
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

Demo orchestrators should be idempotent: re-running on partial output skips assets whose `final.png` (or `final-sheet.png`) AND `meta.json` already exist. Saves ~30-60s per asset of Codex CLI time.

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

`--force` overrides (re-run all); `--force-slug <prefix>` re-runs a specific asset.

## Related skills

- `phaser-gamedev` — downstream consumer of spritesheet output (atlas JSON).
- `threejs-builder` — may consume portrait output for 3D card framing.
- `game-asset-generator` — sibling for 3D models / textures / matrix-driven pixel art. Its `references/pixel-art-sprites.md` redirects AI-driven sprite work here.
- `game-pipeline` — parent lifecycle orchestrator; slot this skill under its ASSETS phase.
