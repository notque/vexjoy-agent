# Game sprite pipeline

The executable contract is `scripts/sprite_pipeline.py --help`. This reference records orchestration and failure-derived ordering that is not obvious from an individual stage.

## Modes

| Mode | Result | Stage order |
|---|---|---|
| portrait | one character image | prompt → generate → background removal → dimension check → deploy |
| portrait-loop | idle-loop frames | prompt → generate → extract/process frames → assemble → verify |
| spritesheet | action grid | prompt → generate → slice cells → extract/process → anchor → assemble → verify |
| per-row | independently generated action/direction rows | create manifest → isolated row jobs → parent validates rows → parent assembles/finalizes |
| video input | frames from a clip | extract → deterministic selection → process → assemble → verify |

Do not invent flags from this document; obtain them from `--help`.

## Reference router

| Need | Reference |
|---|---|
| backend and auth behavior | `backend-chain.md` |
| prompt slots and action phrasing | `prompt-rules.md` |
| named visual style | `style-presets.md` |
| wrestler archetype/tier slots | `wrestler-archetypes.md` |
| grid capacity and direction rows | `grid-shapes.md` |
| chroma/gray/rembg processing | `bg-removal-local.md` |
| connected-component extraction | `frame-detection.md` |
| mass-centroid vs ground-line alignment | `anchor-alignment.md` |
| deliverable layout and formats | `output-formats.md` |
| known symptoms and repairs | `error-catalog.md` |
| row-worker ownership/status | `subagent-delegation.md` |
| action-local VFX | `vfx-containment.md` |

## Ordering invariants

1. Preserve provider output as the raw artifact and record prompt/backend metadata.
2. For grids, slice on declared pitch before connected-component extraction; global extraction can merge neighboring cells.
3. Despill before resizing; upscaling first turns chroma fringe into mixed pixels.
4. Normalize each frame without erasing relative pose scale, then apply the selected anchor policy.
5. Assemble only verified frames. A successful compositor cannot make a bad row valid.
6. Run final verification on the deliverable, not just intermediates.

## Per-row ownership

The parent owns the manifest, shared prompt slots, assembly, and final verification. Each worker owns one isolated raw row plus its receipt and may not compose the final sheet. Status moves monotonically through the states in `subagent-delegation.md`; failure remains visible and is never rewritten as completion because another row succeeded.

## Verification semantics

Success exits `0`; a failed gate exits `2`; intentionally bypassed verification exits `3`. Treat `3` as unverified, not successful.

Check expected frame geometry, alpha/edge contamination, cell parity and strict pitch, foreground clipping, anchor jitter, adjacent-frame distinctness, parseability, and manifest consistency. Retain QA overlays and failing artifacts as diagnostic evidence.

## Known bad repairs

- Do not regenerate art to fix deterministic slicing, anchoring, alpha, or assembly defects.
- Do not hand-edit a final image to pass a gate; fix the stage or recorded prompt and rerun.
- Do not infer a different grid silently. If recovery is explicitly allowed, record inferred pitch.
- File existence and plausible dimensions do not prove valid animation.
- Row workers may not modify shared manifests or deploy directories.

## Completion receipt

Return mode, backend, metadata path, raw path, final paths, verifier result, and retained QA artifacts. For `--target road-to-aew`, also follow `road-to-aew-integration.md` and verify manifest generation and runtime lookup.
