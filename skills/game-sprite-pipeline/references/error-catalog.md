# Error Catalog

Per-phase failure mode → cause → fix mapping. Loaded when a pipeline emits a recognizable error or when debugging a stuck run.

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

## Reference loading hint

Load when an error message matches one in this catalog. The catalog is exhaustive for known failures; novel errors should be added here when fixed (the file is the institutional memory).

<!-- no-pair-required: section header; pair lives in subsection -->
## Anti-pattern

### Anti-pattern: Suppressing dimension errors with `--force-dimensions` routinely

**What it looks like:** Every portrait generation passes `--force-dimensions` because dimension validation "is annoying".

**Why wrong:** The dimension gate exists because road-to-aew's existing 87 enemy + 8 player sprites cluster around 1:1.8 aspect, 470-815px wide. Outliers visually break the game's UI grid. Routinely bypassing the gate produces a heterogeneous sprite library that no one notices is broken until a layout pass fails.

**Do instead**: Re-generate when the gate fails. The gate's error message tells you which dimension is off and by how much; treat it as feedback, not friction. Use `--force-dimensions` only when you have a concrete reason to override (e.g., one-off boss character that genuinely needs different proportions).
