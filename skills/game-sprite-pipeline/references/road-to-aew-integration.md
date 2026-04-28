# road-to-aew Integration

Project-aware deploy and manifest regen for the road-to-aew Slay-the-Spire-style deckbuilder. Loaded only when `--target road-to-aew` is set.

## Project state (as of 2026-04)

- 87 enemy wrestler sprites at `public/assets/characters/enemies/<snake_case>.png`.
- 8 player sprites at `public/assets/characters/player/{male,female}/<snake_case>.png`.
- All single full-body portrait PNGs, RGBA transparent bg.
- Resolution range: ~470-815px wide × 935-994px tall (matches the portrait-mode dimension gate).
- Manifest at `src/game/sprites/enemySpriteManifest.ts`, regenerated via `npm run generate:sprites`.
- Style target: Slay-the-Spire-inspired hand-painted (see `slay-the-spire-painted` preset in `style-presets.md`).

## Naming convention

`snake_case` derived from the character display name:

```
"Bangkok Belle Nisa" → bangkok_belle_nisa
"General Gideon"     → general_gideon
"The Giant Pyotr"    → giant_pyotr  (definite article dropped)
"D'Marcus James"     → dmarcus_james (apostrophe stripped)
```

`road_to_aew_integration.py snake-case <display-name>` runs the conversion. The rules:

1. Drop leading articles: `The`, `A`, `An`.
2. Lowercase everything.
3. Replace whitespace with `_`.
4. Strip non-alphanumeric except `_` (apostrophes, periods, commas removed).
5. Collapse runs of `_` into single `_`.
6. Strip leading/trailing `_`.

## Deploy paths

| Character class | Path |
|------------------|------|
| Enemy | `~/road-to-aew/public/assets/characters/enemies/<snake_case>.png` |
| Player male | `~/road-to-aew/public/assets/characters/player/male/<snake_case>.png` |
| Player female | `~/road-to-aew/public/assets/characters/player/female/<snake_case>.png` |

Selection logic:

| Flag | Path resolved |
|------|---------------|
| `--target road-to-aew` (default) | enemies dir |
| `--target road-to-aew --player male` | player/male dir |
| `--target road-to-aew --player female` | player/female dir |
| `--target road-to-aew --target-dir <path>` | use `<path>` instead of `~/road-to-aew` |

## Manifest regeneration

After deploying a new sprite, the manifest at `src/game/sprites/enemySpriteManifest.ts` must be refreshed. Two modes:

### Auto-regen (`--regen-manifest`)

```bash
python3 portrait_pipeline.py \
    --prompt "..." --target road-to-aew --regen-manifest
```

The skill runs:

```bash
cd ~/road-to-aew && npm run generate:sprites
```

Stdout/stderr is forwarded. Exit code propagates — non-zero from manifest regen surfaces as `IntegrationError`.

### Manual regen (default)

Without `--regen-manifest`, the skill prints a reminder:

```
[deploy] Sprite written: ~/road-to-aew/public/assets/characters/enemies/bangkok_belle_nisa.png
[deploy] Run `cd ~/road-to-aew && npm run generate:sprites` to refresh the manifest.
```

The user runs the command when they want to ship the manifest update.

Why default to manual: regen takes 5-15 seconds and triggers TypeScript compilation, which produces noise. Batch generation of 10 wrestlers should regen once at the end, not 10 times. The user picks the moment.

## Tier and archetype mapping

road-to-aew has procedural archetype + tier enums in `src/game/types/wrestler.ts`. The skill's `--archetype` and `--tier` flags map directly:

| Skill flag | road-to-aew enum value |
|------------|-------------------------|
| `--archetype powerhouse` | `WrestlerArchetype.POWERHOUSE` |
| `--archetype technical` | `WrestlerArchetype.TECHNICAL` |
| `--archetype high-flyer` | `WrestlerArchetype.HIGH_FLYER` (snake_case in the enum) |
| `--archetype brawler` | `WrestlerArchetype.BRAWLER` |
| `--archetype striker` | `WrestlerArchetype.STRIKER` |
| `--archetype submission` | `WrestlerArchetype.SUBMISSION` |
| `--archetype showman` | `WrestlerArchetype.SHOWMAN` |
| `--archetype giant` | `WrestlerArchetype.GIANT` |
| `--archetype player` | `WrestlerArchetype.PLAYER` |
| `--tier act1` | `Tier.INDIES` |
| `--tier act2` | `Tier.ROH` |
| `--tier act3` | `Tier.AEW` |

The metadata sidecar JSON includes both flag-form and enum-form values so manifest-side code can look up either.

## Wrestling style enum

road-to-aew also has `WrestlingStyle` (striker, grappler, high_flyer, brawler). This is independent of archetype and is used for combat-system mechanics. The skill does not generate this — it is hand-set in the manifest by the user. Listed here for awareness.

## Image transform on render

Enemy sprites are rendered facing the player via:

```jsx
<img src={`/assets/characters/enemies/${sprite}.png`}
     style={{ transform: 'scaleX(-1)' }} />
```

This means the generated sprite should face screen-right (player faces enemy from the left). The `slay-the-spire-painted` preset's "3/4 isometric perspective from slightly above" is direction-neutral; the transform handles facing.

`giant` archetype additionally applies `scale(1.2)` for towering presence — the skill does not need to apply this; the React renderer handles it.

## Existing sprite library inspection

To avoid duplicate IDs, run before adding a new wrestler:

```bash
python3 road_to_aew_integration.py list-existing | grep -i "bangkok"
```

This lists all existing sprite IDs and matches against the candidate name. Empty output means the ID is free.

## Rive infrastructure

road-to-aew has Rive `.riv` skeletal-animation infrastructure scaffolded at `src/game/rive/`. It is not currently deployed — every wrestler is a static portrait. Future Rive activation is out of scope for this skill (per ADR-197 deferred-questions section).

If/when Rive is activated, this reference will be updated to include a `--rive-export` flag that decomposes the portrait into Rive-ready bone groups.

## Example end-to-end run

```bash
# Generate Bangkok Belle Nisa (Act 2 ROH heel showman)
python3 portrait_pipeline.py \
    --display-name "Bangkok Belle Nisa" \
    --description "kabuki-inspired makeup, Thai national colors woven into the showman gear, mid-30s confident expression" \
    --style slay-the-spire-painted \
    --archetype showman \
    --gimmick heel \
    --tier act2 \
    --target road-to-aew \
    --regen-manifest \
    --seed 42

# Output:
# [phase A] Codex CLI generation: 28.4s
# [phase B] Magenta chroma key: 1.2s
# [phase C] Trim and center: 0.08s
# [phase D] Dimension validation: PASS (612x980, aspect 1:1.6)
# [phase E] Deployed: ~/road-to-aew/public/assets/characters/enemies/bangkok_belle_nisa.png
# [phase E] Manifest regenerated: src/game/sprites/enemySpriteManifest.ts updated (88 entries)
```

<!-- no-pair-required: section header; pair lives in subsection -->
## Signals and Fixes

### Signal: Hard-coding the road-to-aew path

**What it looks like:** `output_path = Path("/home/feedgen/road-to-aew/...")` hard-coded into the skill scripts.

**Why wrong:** Other users / environments have road-to-aew checked out elsewhere. The skill becomes unportable.

**Do instead**: Resolve `--target-dir` at runtime; default to `~/road-to-aew` (`Path.home() / "road-to-aew"`); allow override via flag. The deploy step refuses to guess if the resolved path does not exist — explicit error with the resolved value, not silent fallback.

### Signal: Regenerating every sprite during a batch

**What it looks like:** Loop over 50 wrestlers; each iteration runs `npm run generate:sprites`.

**Why wrong:** TypeScript compilation runs 50 times, taking 5-15s each = 5-12 minutes of pure manifest-rebuild overhead. The manifest content is the same as the final state regardless of how many times it ran mid-batch.

**Do instead**: Run the batch with `--regen-manifest=false` (skill default); regen once at the end with a single `cd ~/road-to-aew && npm run generate:sprites`. The skill prints the reminder so the user does not forget. For automation, wrap the batch + final regen in a single shell script.

## Reference loading hint

Load when:
- `--target road-to-aew` is in the active command
- The user asks about deploying to road-to-aew
- A `IntegrationError` is being debugged
- ID-collision check is needed before generating
