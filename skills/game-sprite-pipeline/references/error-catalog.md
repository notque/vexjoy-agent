# Error Catalog

Per-phase failure mode → cause → fix mapping. Loaded when a pipeline emits a recognizable error or when debugging a stuck run.

## Anti-pattern: Codex Regeneration as a Post-Processing Fix

Codex generation is treated as ground truth. If a final-sheet, animation, or contact-sheet shows clipping/blank-cells/cuts, the bug is in post-processing, never in Codex output. Never regenerate the raw as a fix; debug the slicer, anchor, despill, or matte step instead. The user's framing: "the codex generation has never failed, it is working perfectly, the rest has failed."

**What it looks like:** A verifier flags a "blank cell" or "missing content" or "clipped fire". The diagnostic urge is to re-run `codex exec` to redraw the raw with a different prompt. STOP.

**Why wrong:** The raw PNG in `<your-output-dir>/raw/<slug>.png` is what Codex painted. It is the ground truth. If post-processing shows blank cells, the bug is one of:
- `slice_grid_cells` derived the wrong pitch (raw_size / grid math) and cut the cell at the wrong place
- `slice_with_content_awareness` claimed a component to the wrong cell (centroid mapping bug)
- The despill chain (`chroma_pass2_edge_flood`, `kill_pink_fringe`, `neutralize_interior_magenta_spill`) ate the silhouette
- The mass-centroid anchor pinned the wrong body part to the ground line
- The LANCZOS resize between magenta padding and content created pink fringe that downstream gates flagged

**Do instead:** Open the raw and the final side-by-side. Verify the raw is correct (it almost always is). Then trace which post-processing step lost the content:

```bash
# 1. Inspect raw
xdg-open <your-output-dir>/raw/<slug>.png

# 2. Inspect final
xdg-open <your-output-dir>/assets/<slug>/final-sheet.png

# 3. Run the slicer in isolation
python3 -c "
import sys
sys.path.insert(0, '<your-toolkit-root>/skills/game-sprite-pipeline/scripts')
from PIL import Image
from sprite_process import slice_grid_cells, slice_with_content_awareness
sheet = Image.open('<your-output-dir>/raw/<slug>.png')
cells = slice_grid_cells(sheet, COLS, ROWS, CELL_SIZE)  # or slice_with_content_awareness
for i, c in enumerate(cells):
    c.save(f'/tmp/_dbg_cell_{i}.png')
"
```

**Specifically for boundary clipping** (asset 27 dragon flame, asset 30 plasma trail): Codex paints content that extends past the conceptual cell boundary in the raw (e.g. fire jets extend 30-50 px past the 313.5 px cell pitch). The strict-pitch slicer cuts that content; use `slice_with_content_awareness` with `content_aware_extraction: True` in the spec, OR set `has_effects: True`.

## Backend errors

### `BackendUnavailableError: No image-generation backend available`

**Phase:** any generation phase (A, C in spritesheet; A in portrait).

**Cause:** Neither `codex` CLI nor `GEMINI_API_KEY` detected.

**Fix:**
```bash
# Install Codex CLI:
npm install -g @openai/codex   # or your distro's equivalent
codex auth                      # complete OAuth flow

# OR set Gemini key:
export GEMINI_API_KEY=<your-key>
```

Never set `OPENAI_API_KEY` for this skill. The skill does not consume it; setting it does not unlock anything.

### `subprocess.CalledProcessError: codex exec exit code 2`

**Phase:** any generation phase using Codex.

**Cause:** Codex CLI version mismatch (e.g., older syntax, retired image model alias) or auth token expired.

**Fix:**
1. `codex --version` to check version.
2. `codex auth` to refresh tokens.
3. If model alias is wrong, the skill will detect this and emit a `--codex-model` suggestion. Pass `--codex-model image-2` (or whatever current alias) to override.

### `nano-banana-generate.py: ERROR: Set GEMINI_API_KEY`

**Phase:** any generation phase using Nano Banana.

**Cause:** `GEMINI_API_KEY` not set in the environment seen by the subprocess.

**Fix:** Export in the calling shell, NOT in a `.env` file the subprocess can't read:

```bash
export GEMINI_API_KEY=<your-key>
python3 sprite_pipeline.py ...
```

### `nano-banana-generate.py: ERROR: No image in response`

**Phase:** generation phase.

**Cause:** Gemini's safety filters rejected the prompt; no image returned.

**Fix:** Edit the prompt. Look for content that might trigger filters (violence, certain character archetypes, named individuals). Try with `--style-string` rephrased.

## Spritesheet Phase D errors (frame detection)

### `FrameCountMismatchError: detected N components, grid expected M`

**Cause:** Connected-components found a different number of clusters than `cols × rows`. Two patterns:

- N < M: components merged across cells (chroma threshold too tight, fringe pixels bridge cells).
- N > M: components fragmented within cells (chroma threshold too loose, character broken into pieces).

**Fix:**

| Direction | Adjustment |
|-----------|------------|
| N < M | `--chroma-threshold 50` (relaxes mask, drops more fringe). Or regenerate canvas with `--cell-size 384` (more separation). |
| N > M | `--chroma-threshold 15` (tightens mask, keeps more character). Or `--min-pixels 500` (filters fragments). |

Inspect the metadata JSON to see component bboxes. If the rejected count is high (>2), the threshold is biting into the character.

### `ComponentSortError: ambiguous frame ordering`

**Cause:** Multiple components have nearly equal `top` y-coordinates; the natural sort cannot determine which is "first".

**Fix:** Pass `--cell-aware` to use centroid-to-cell mapping instead of top-left sort. The skill does this by default for grids ≥ 2x2; the error indicates a 1xN sheet where centroids map to a single row.

## Spritesheet Phase F errors (anchor alignment)

### `NormalizationError: frame N is (W, H), expected (cell_w, cell_h)`

**Cause:** A frame failed to rescale to the target cell size. Usually because Phase D returned a zero-area component (all-transparent after Phase E).

**Fix:** Check `frame_metadata.json` for the offending frame's bbox. If bbox area is 0 or near-zero, the chroma key removed the entire frame (over-aggressive bg removal). Adjust `--chroma-threshold` and re-run.

### `WARNING: frame N anchor at y=K (canvas height H) — sprite floats high`

**Cause:** Frame's lowest non-transparent pixel is in the upper half of the cell. Either the character is genuinely aerial (jump pose) or Phase D extracted only the top of the character.

**Fix:** Inspect the frame visually. If the character is supposed to be aerial, the warning is benign. If only the top of the character is present, Phase D failed — adjust extraction parameters.

## Portrait Phase D errors (dimension validation)

### `DimensionError: width 320 outside [350, 850]`

**Cause:** Trim phase produced a character narrower than the floor.

**Fix:** Re-generate with explicit width hints in the prompt: "wide stance" or "broad shoulders". If the character should genuinely be narrow (e.g., `submission` lean grappler), pass `--force-dimensions` for emergencies.

### `DimensionError: aspect 1:3.1 outside [1:1.5, 1:2.5]`

**Cause:** Character is too tall relative to width (extreme full-extension pose) or too wide (crouched).

**Fix:** Re-generate with `--description` updated to specify "neutral standing pose". Atypical poses are not portrait-mode subjects; use spritesheet mode for action poses.

### `WARNING: --force-dimensions used; output bypasses gate`

**Cause:** Emergency override flag is active.

**Fix:** None — this is the expected log when the user opts out. Listed here so it does not look like a bug.

## Portrait Phase E errors (deploy)

### `IntegrationError: road-to-aew directory not found at ~/road-to-aew`

**Cause:** `--target road-to-aew` resolves to a path that does not exist.

**Fix:** Either clone the repo to `~/road-to-aew`, or pass `--target-dir <explicit-path>` to point at your installation.

### `subprocess.CalledProcessError: npm run generate:sprites exit 1`

**Cause:** road-to-aew's manifest regen script failed. Could be missing `node_modules`, syntax error in a sprite-name → ID mapping, or the new sprite has the same ID as an existing one.

**Fix:**
1. `cd ~/road-to-aew && npm install` to ensure deps.
2. Check stderr from the manifest script — it prints which sprite is conflicting.
3. Manually rename if there is an ID collision (e.g., two characters both resolve to `general_gideon`).

## Background-removal errors

### `RuntimeError: rembg not installed`

**Phase:** any phase using `--bg-mode rembg`.

**Cause:** `--bg-mode rembg` requested but the optional dep is missing.

**Fix:**
```bash
pip install rembg onnxruntime
# or for GPU:
pip install rembg onnxruntime-gpu
```

Or re-run with `--bg-mode chroma` (default; no extra deps).

### `WARNING: corner not transparent: alpha=N`

**Phase:** post bg-removal validation.

**Cause:** Chroma key did not catch the dominant-corner color. Usually because the backend ignored the magenta-bg instruction and produced a different color.

**Fix:**
1. Inspect the source image. If bg is white/gray/blue (not magenta), pass `--bg-mode rembg` for general bg removal.
2. If bg is magenta but with strong fringing, increase `--chroma-threshold`.

## Canvas errors

### `ValueError: cell-size 200 not allowed`

**Cause:** Cell size not in `{64, 128, 192, 256, 384, 512}`. Powers of 16 only.

**Fix:** Use one of the allowed sizes. Closest to 200 is 192.

### `ValueError: total canvas 2560x1024 exceeds 2048x2048 limit`

**Cause:** `cell_size × cols` or `cell_size × rows` exceeds 2048. Backends silently downsample anything larger.

**Fix:** Reduce `cell-size` (192 instead of 256), or reduce grid (`4x4` instead of `8x4`).

### `ValueError: grid '4_4' malformed`

**Cause:** Wrong separator. Skill expects `CxR` (e.g., `4x4`).

**Fix:** Use `x` (lowercase) as separator: `--grid 4x4`.

## Auto-curation errors

### `WARNING: all variants have edge-touch issues`

**Cause:** All generated variants have at least one frame where the character's bbox touches a canvas edge. Indicates the prompt's "70-85% canvas coverage" instruction was ignored, or the cell size is too small for the character.

**Fix:**
1. Re-generate with `--variants 5` for more options.
2. Increase `--cell-size`.
3. Tighten the `PORTRAIT_RULES` block in `prompt-rules.md` to enforce smaller character coverage.

### `CurationError: zero variants generated`

**Cause:** Earlier phase failed; no variants reached Phase G.

**Fix:** Check upstream errors. Phase A or C failed silently; look at `<output-dir>/error.log` for backend stderr.

## Verifier gate failures (v8 added)

These are the deterministic build-time gates wired into `verify_asset_outputs`.
Each gate reports `passed: bool` plus diagnosis details. The `pipeline.run_one`
hard-fails the asset and records the failure on `meta["verification_failures"]`
so the demo HTML shows a red FAIL badge instead of broken art.

The full set is six gates: `verify_no_magenta`, `verify_grid_alignment`,
`verify_anchor_consistency`, `verify_frames_have_content`, `verify_frames_distinct`
(advisory for spritesheets), `verify_pixel_preservation`. All six run on every
final-sheet, frames-strip, animation.gif, and final.webp where applicable;
file-format tolerance bands are applied per-format inside `verify_asset_outputs`
(GIF/WebP get 10x relaxation on wide-pink because lossy palettes resurrect
halo pixels).

### `no_magenta` failure

**Cause:** Residual magenta survives in the final asset. Two pixel classes:
- `strict_count`: near-pure (R>200, B>200, G<100) — catches `(255,0,255)` bleeding
  through despill.
- `wide_count`: diluted pink halo (R>130, B>120, G<80, R-G>50, B-G>40) — catches
  fringe survival.

The strict band excludes purple (`B/R <= 1.05` clause) so legitimate purple-
costume art (manager suit, wizard robes) does not register.

**Fix:** Tighten `chroma_pass2_edge_flood` threshold (drop pass2_threshold from
90 to 60 for painted styles), or check whether the asset has legitimate purple
art crossing the wide threshold. For `has_effects: True` assets the wide
threshold relaxes 30x so plasma/fire/aura content is not misread as fringe.

### `grid_alignment` failure

**Cause:** Per-cell alignment check finds character silhouettes touching cell
boundaries (within `edge_margin_px=2`). Threshold is **5% of cells violating**,
NOT 50%. A 50% tolerance is permissive enough to admit the failure it exists
to catch — see the `Rubber-stamp verifier thresholds` anti-pattern below. For
a 4x4 sheet this is 1 violation; for an 8x8 it is 3.

**Fix:** When the gate fires, the slicer placed a cell boundary inside another
character's body. Either reduce grid density (8x8 → 4x4 — see the Codex grid-
density limit in `frame-detection.md`), or switch to `slice_with_content_awareness`
via `has_effects: True`.

### `anchor_consistency` failure

**Cause:** mass-centroid Y stddev across cells exceeds 8px (4px for portrait-loops),
OR a single frame's centroid is more than 16px from the median (a "hop" outlier).
Reproduces the asset 05 powerhouse failure where bbox-bottom anchor pinned the
fist to the floor and the trunk floated up.

**Fix:** Use mass-centroid anchor (`apply_mass_centroid_anchor` rather than the
legacy `apply_ground_line_anchor`). The mass centroid integrates over all opaque
pixels so limb extensions only nudge it a few percent rather than the dozens of
pixels bbox-bottom shifts. See `references/anchor-alignment.md`.

### `frames_have_content` failure

**Cause:** One or more cells have <2% alpha pixels (effectively blank). The
generator left a cell empty (asset 08 cell 12, asset 28 cell 0). The post-
processor cannot infer content from nothing.

**Fix:** Regenerate the asset via Codex. The blank-cell rate is non-deterministic
across runs; up to 2 retries usually clears it. If consistent, the prompt may be
overconstrained — try lowering action_mode constraints or splitting the cycle
across two grids (e.g. 2x2 of 4-frame mini-cycles instead of 4x4).

### `frames_distinct` warning (non-blocking by default)

**Cause:** Pairwise dHash distances < 4 across many cells, indicating high
inter-cell similarity. Set to non-blocking (threshold=100%) for spritesheets
because legitimate animation cycles routinely measure 70-95% dup_pct: walk
cycles repeat poses across strides, idle loops are by construction near-
identical, 3-count animations have 4 reference poses repeated 4 times each.

**Fix:** Investigate when both `frames_distinct` AND `frames_have_content` fire
together — that's the "cells merged into one" pattern. Otherwise treat as
informational diagnosis output.

### `pixel_preservation` failure

**Cause:** Area-normalized ratio of final-cell visible pixels to expected
silhouette pixels is below 0.40, for more than 25% of cells. The despill chain
has bridged cells (asset 19 painted veteran in v7) or over-aggressively wiped
silhouette pixels.

**Fix:** Tighten chroma_pass2_edge_flood threshold. v8 uses pass2=60 for painted-
style assets (default 90 for pixel-art styles). For effect-bearing assets (fire,
energy), set `has_effects=True` in the spec to skip neutralize_interior_magenta_spill.

## Operational errors

### Demo HTML staleness — `index.html` does not reflect new/modified assets

**Symptom:** User reports "I do not see the improvements" after a generation
or reprocess run. `curl -sI http://144.126.223.3:8080/` returns the same
`Content-Length` after work that should grow the file. Newly-generated asset
directories exist on disk but the live demo page shows the old asset list.

**Cause:** `build_html.py` is a **separate manual step** from `generate.py`
and `reprocess_all.py`. Adding or modifying assets does NOT auto-rebuild
`<your-output-dir>/index.html`. The Python `http.server` keeps serving the
stale index until `build_html.py` runs.

**Fix:** Every asset-modifying workflow MUST run `build_html.py` before
declaring the work done:

```bash
cd <your-output-dir>
python3 generate.py [...]            # or reprocess_all.py
python3 build_html.py                # rebuild index from per-asset meta.json
```

**Verification:** Compare the cards-in-HTML count vs asset-dirs-on-disk, or
check the curl size delta:

```bash
ls <your-output-dir>/assets/ | wc -l                # asset directory count
grep -c 'class="card"' <your-output-dir>/index.html # cards rendered in HTML
curl -sI http://<your-demo-host>:8080/ | grep Content-Length
```

If counts disagree, run `build_html.py` and re-check.

## `has_effects: True` spec flag (consolidated)

A single flag in the asset spec that propagates through the pipeline:

1. **Slicer:** triggers `slice_with_content_awareness` instead of
   `slice_grid_cells` (frame-detection.md). Recovers content extending past
   conceptual cell boundaries (dragon flame, plasma trails, extended limbs).
2. **Despill:** sets `skip_interior_neutralize=True` so
   `neutralize_interior_magenta_spill` does NOT fire. Effect art (red/orange
   fire, magenta plasma arcs, purple aura) is legitimate-pink-cast pixels
   that the interior neutralizer would erase.
3. **Verifier:** in `verify_asset_outputs`, `magenta_wide_threshold` relaxes
   30x and `magenta_strict_threshold` relaxes from 0 to 200. Plasma orbs
   paint near-pure magenta arcs intentionally; the verifier tolerates that
   while still catching whole-silhouette-magenta failures.

Set `has_effects: True` in the asset spec when the character has fire,
projectile trails, plasma, energy auras, magic effects, or any saturated
warm-cast art that overlaps the fringe-detection band. `content_aware_extraction:
True` is a more-targeted variant: enables only the slicer change without the
despill and verifier relaxation. `has_effects=True` is the right default for
effect-heavy assets.

**Known limitation (deliberate, per session 2026-04-25):** the wide-pink
verifier criterion still produces false positives on a small subset of
legitimate purple/red painted art even with the 30x relaxation. The user
explicitly chose to leave this for future work rather than add an
effects-aware bypass — wide thresholds are easier to retune than to
re-introduce after deletion.

## Reference loading hint

Load when an error message matches one in this catalog. The catalog is exhaustive for known failures; novel errors should be added here when fixed (the file is the institutional memory).

<!-- no-pair-required: section header; pair lives in subsection -->
## Anti-pattern

### Anti-pattern: Rubber-stamp verifier thresholds

**What it looks like:** Adding a verifier gate but tuning its tolerance
loose enough that it almost never fires. Concrete examples from this skill's
own history: `verify_grid_alignment` shipped with `violation_tolerance=50%`
of cells (commit `ea01a21`); a 4x4 sheet would need 8 of 16 cells to fail
before the gate flagged anything. Tightened to `5%` in `182bf03` after
the 50% threshold admitted a 4x4 powerhouse asset whose every cell was
clipped at the arms.

**Why wrong:** A verifier whose threshold is ≥10% of total cases is
permissive enough to admit the failure class it exists to catch. The
`docs/PHILOSOPHY.md` "Verifier pattern" requires evidence-bearing verdicts:
"passed" must carry meaning. A 50% threshold means "passed" can hide a sheet
where half the cells are broken — the gate becomes a rubber stamp.

**Do instead:** Justify each threshold against real failure data, not
synthetic test cases. Rule of thumb: tolerance should be `max(1, ceil(0.05 *
total_cells))` for grid-shape gates, `8px` (mass-centroid Y stddev) for
anchor gates, `0` blank cells for content gates. When tightening an existing
threshold, regression-test against the known-bad asset that motivated the
original (loose) value — the tighter gate must catch it. When relaxing, you
need a stronger reason than "the gate is firing on legitimate art": find
the disjoint criterion that distinguishes legitimate cases from real failures
and encode that, instead of widening the band.

### Anti-pattern: Suppressing dimension errors with `--force-dimensions` routinely

**What it looks like:** Every portrait generation passes `--force-dimensions` because dimension validation "is annoying".

**Why wrong:** The dimension gate exists because road-to-aew's existing 87 enemy + 8 player sprites cluster around 1:1.8 aspect, 470-815px wide. Outliers visually break the game's UI grid. Routinely bypassing the gate produces a heterogeneous sprite library that no one notices is broken until a layout pass fails.

**Do instead**: Re-generate when the gate fails. The gate's error message tells you which dimension is off and by how much; treat it as feedback, not friction. Use `--force-dimensions` only when you have a concrete reason to override (e.g., one-off boss character that genuinely needs different proportions).
