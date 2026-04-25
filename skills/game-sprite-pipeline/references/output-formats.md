# Output Formats

Per-mode output matrix. Phase H (spritesheet) and Phase E (portrait) write the canonical asset files.

## Spritesheet mode (Phase H)

| File | Always produced? | Notes |
|------|-------------------|-------|
| `<name>_sheet.png` | Yes | Full grid, RGBA transparent bg |
| `<name>.gif` | Yes | Animated GIF, 8-12 fps default loop |
| `<name>.webp` | Yes | Animated WebP, smaller than GIF |
| `<name>_frames/<name>_frame_NN.png` | Yes | One PNG per frame, RGBA, cell_w × cell_h |
| `<name>.json` | Yes | Phaser 3 texture atlas |
| `<name>_<dir>.png` | Only when `--grid 4xR` or `8xR` | One per direction row |

### PNG sheet

```
<name>_sheet.png  (cell_w * cols, cell_h * rows, RGBA)
```

Layout matches the `--grid CxR` spec. RGBA so transparency survives. Used by:

- Phaser via `this.load.spritesheet(key, path, {frameWidth, frameHeight})` — needs uniform cell sizes (which Phase F guarantees).
- Web games via CSS `background-position` animation.
- Other game engines that consume sprite-grid PNGs.

### Animated GIF

```python
def write_gif(frames, output_path, fps=10):
    """Animated GIF with transparency."""
    duration_ms = int(1000 / fps)
    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=duration_ms,
        loop=0,
        disposal=2,  # restore to bg color → transparent
        transparency=0,
    )
```

GIF transparency is finicky — alpha is binary (on/off), no smooth edges. Pillow's `disposal=2` plus `transparency=0` produces the cleanest output, but anti-aliased edges will have visible halos because GIF cannot represent the gradient.

### Animated WebP

```python
def write_webp(frames, output_path, fps=10):
    """Animated WebP with full alpha."""
    duration_ms = int(1000 / fps)
    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=duration_ms,
        loop=0,
        format="WebP",
    )
```

WebP supports full alpha (8-bit). Recommended over GIF for any modern target. Smaller files, smoother edges.

### Per-frame PNGs

`<name>_frames/<name>_frame_00.png` ... `_frame_NN.png`. RGBA, cell_w × cell_h. Already on disk after Phase F — Phase H copies them into the named output directory for organization.

### Phaser texture atlas (JSON)

```json
{
  "frames": {
    "frame_00.png": {
      "frame": {"x": 0, "y": 0, "w": 256, "h": 256},
      "rotated": false,
      "trimmed": false,
      "spriteSourceSize": {"x": 0, "y": 0, "w": 256, "h": 256},
      "sourceSize": {"w": 256, "h": 256},
      "anchor": {"x": 0.5, "y": 0.97}
    },
    "frame_01.png": { ... }
  },
  "meta": {
    "app": "game-sprite-pipeline",
    "version": "1.0.0",
    "image": "<name>_sheet.png",
    "format": "RGBA8888",
    "size": {"w": 1024, "h": 1024},
    "scale": "1"
  }
}
```

The `anchor.y` is computed in Phase F (anchor-alignment.md). Phaser consumes this via:

```javascript
this.load.atlas('walkCycle', '<name>_sheet.png', '<name>.json');
const sprite = this.add.sprite(x, y, 'walkCycle', 'frame_00.png');
sprite.setOrigin(0.5, 0.97);  // matches anchor.y
```

Phaser's atlas format is well-documented; the skill emits the standard JSON-Hash format.

### Per-direction strips (4xR / 8xR only)

```
<name>_down.png   (cell_w * cols, cell_h)
<name>_left.png
<name>_right.png  (only if --no-flip-right; otherwise omitted)
<name>_up.png
```

For `--grid 4xR`, the convention is row 0=down, 1=left, 2=right, 3=up (see grid-shapes.md). `--no-flip-right` toggles whether row 2 is generated separately or runtime-mirrored.

For `--grid 8xR` (8-direction), strips are `<name>_<dir>.png` for each of {down, down-left, left, up-left, up, up-right, right, down-right}.

Each strip is one row of the full sheet, exported as a horizontal strip PNG. Used by:

- Top-down games that load per-direction strips for performance.
- Engines that prefer row-strip atlases over the full grid.

## Portrait mode (Phase E)

| File | Always produced? | Notes |
|------|-------------------|-------|
| `<name>.png` | Yes | RGBA transparent, dimension-validated |
| `<name>_metadata.json` | Yes | Generation log: prompt, seed, backend, dimensions |
| `<name>.riv` | No (deferred) | Rive infrastructure exists in road-to-aew but is not deployed |

### PNG output

Aspect ratio 1:1.5 to 1:2.5 (h:w). Width 350-850, height 900-1100. RGBA with transparent background. Centered horizontally, bottom-anchored vertically with ~5% margin.

The PNG's filename is `snake_case` derived from the character display name when `--target road-to-aew`:

```
"Bangkok Belle Nisa" → bangkok_belle_nisa.png
"General Gideon"     → general_gideon.png
```

### Metadata JSON

```json
{
  "name": "bangkok_belle_nisa",
  "display_name": "Bangkok Belle Nisa",
  "prompt": "ART_STYLE: Hand-painted illustration style: ...",
  "seed": 42,
  "backend": "codex",
  "model": "image-1",
  "dimensions": {"width": 612, "height": 980},
  "aspect_ratio": "1:1.6",
  "archetype": "showman",
  "gimmick": "heel",
  "tier": "act2",
  "style_preset": "slay-the-spire-painted",
  "generated_at": "2026-04-24T14:32:11Z",
  "phases": [
    {"phase": "A", "name": "generate", "duration_ms": 28400},
    {"phase": "B", "name": "remove-bg", "duration_ms": 1200, "mode": "chroma"},
    {"phase": "C", "name": "trim-center", "duration_ms": 80},
    {"phase": "D", "name": "validate", "duration_ms": 5, "passed": true},
    {"phase": "E", "name": "deploy", "duration_ms": 12, "target": "road-to-aew"}
  ]
}
```

The metadata sidecar enables:

- Re-running with the same seed for reproducibility.
- Auditing which backend / model produced each asset.
- Cost tracking across batch runs.
- Debugging (which phase took the longest, did dimension validation pass).

## Output directory layout

### Spritesheet mode

```
<output-dir>/
└── <name>/
    ├── <name>_sheet.png
    ├── <name>.gif
    ├── <name>.webp
    ├── <name>.json                     # Phaser atlas
    ├── <name>_metadata.json            # generation log
    ├── <name>_frames/
    │   ├── <name>_frame_00.png
    │   ├── <name>_frame_01.png
    │   └── ...
    ├── <name>_down.png                 # only if 4xR or 8xR
    ├── <name>_left.png
    ├── <name>_up.png
    └── <name>_right.png                # only if --no-flip-right
```

### Portrait mode (`--target road-to-aew`)

```
~/road-to-aew/public/assets/characters/enemies/
└── <snake_case>.png
~/road-to-aew/public/assets/characters/enemies/
└── <snake_case>_metadata.json          # generation log

(or characters/player/{male,female}/ for player sprites)
```

Manifest regeneration runs `npm run generate:sprites` in the road-to-aew directory if `--regen-manifest` is passed.

### Portrait mode (no target)

```
<output-dir>/
└── <name>.png
└── <name>_metadata.json
```

## Format selection guidance

| Use case | Format |
|----------|--------|
| Web preview / share | Animated GIF |
| Modern game engine (Phaser/Three.js) | PNG sheet + atlas JSON |
| Mobile / WebP-supporting browsers | Animated WebP (smaller than GIF) |
| Per-frame manipulation | Per-frame PNGs |
| Top-down game with per-direction movement | Per-direction strips |

The skill always emits all spritesheet outputs (cheap to produce in parallel after Phase G); consumers pick the format they want.

<!-- no-pair-required: section header; pair lives in subsection -->
## Anti-pattern

### Anti-pattern: Emitting only a GIF for a spritesheet

**What it looks like:** Pipeline output is `<name>.gif` and nothing else.

**Why wrong:** GIF has binary alpha (no smooth edges), 256-color palette (color banding on painterly art), and lossy frame timing. Game engines cannot consume GIF directly — they need PNG frames or atlas-JSON. The user gets stuck re-extracting frames manually.

**Do instead**: Emit the full output matrix every run. PNG sheet + atlas JSON for engines, GIF for previews, WebP for modern targets, per-frame PNGs for editing. Storage cost is small; user friction of missing format is large.

## Reference loading hint

Load when:
- Phase H (spritesheet assembly) or Phase E (portrait deploy) is active
- Phaser integration code is being written
- Per-direction strips are being debugged
