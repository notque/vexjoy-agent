# Style Presets

Era/hardware-defined visual styles. No trademarked franchise names. The preset name selects a prompt fragment that gets injected into the `ART_STYLE` slot; everything else (character, archetype, action) composes around it.

`--style <preset>` selects from the catalog. `--style custom --style-string "<fragment>"` injects a free-form fragment in the same slot.

## Preset catalog

| Preset | Prompt fragment | Best for |
|--------|-----------------|----------|
| `gameboy-4color` | "4-shade green Game Boy palette (#0f380f, #306230, #8bac0f, #9bbc0f), 8x8 tile-aligned, chunky silhouettes, no anti-aliasing, hard pixel edges" | Retro 1989-era handheld |
| `nes-8bit` | "8-bit NES palette (54-color hardware), 3-color-per-sprite limit, blocky pixel style, 16x16 or 32x32 character cells, no shading gradients, hard outlines" | NES-era platformers, RPGs |
| `snes-16bit-jrpg` | "16-bit SNES JRPG style, saturated colors, character-portrait framing, anti-aliased 32x32 to 64x64 sprites, dithered shading, dramatic lighting" | SNES JRPG character portraits |
| `genesis-16bit` | "16-bit Genesis/Mega Drive style, high-contrast palette, sharp outlines, fast-action sprite design, slightly desaturated tones, hard shadows" | 90s arcade-style action |
| `arcade-cps2` | "Capcom CPS-2 arcade style, large expressive sprites (96x128 typical), dramatic poses, heavy outline, painterly shading on flat colors, hand-animated feel" | Fighting-game character art |
| `gba-16bit-portable` | "Game Boy Advance 16-bit style, softer palette than SNES, portable-console framing, 32x32 sprites with subtle dithering, mid-90s pop aesthetic" | GBA-era RPGs and adventure games |
| `psx-low-poly` | "PlayStation 1 low-poly render, ~500-1500 polygons, texture warping (affine mapping), vertex lighting, no anti-aliasing, slight jitter, 256x256 textures" | PSX-era 3D pre-render look |
| `modern-hi-bit` | "Modern indie hi-bit style (clean outlines, limited 16-32 color palette, chunky pixels with anti-aliased edges, expressive poses, contemporary indie game aesthetic)" | Celeste/Shovel Knight-tier indie |
| `slay-the-spire-painted` | "Hand-painted illustration style: heavy black ink outlines, saturated rich colors (deep reds, golds, purples), golden glowing aura around character, 3/4 isometric perspective from slightly above, painterly brushwork visible, atmospheric rim lighting" | road-to-aew default; deckbuilder card portraits |

`slay-the-spire-painted` is the default for `--target road-to-aew` because it matches the existing 87 enemy + 8 player sprite library.

## Custom-style slot

```bash
python3 sprite_prompt.py build-portrait \
    --style custom \
    --style-string "comic-book inked, ben-day dot shading, four-color palette" \
    --description "lucha libre wrestler in flowing cape" \
    --output prompt.txt
```

The string is dropped into the `ART_STYLE` slot verbatim. The skill does not validate semantic correctness — that is the user's responsibility.

## Composition example

A built portrait prompt looks like:

```
ART_STYLE: <preset fragment>
CHAR_STYLE: <archetype fragment, if --archetype set>
TIER: <tier fragment, if --tier set>
DESCRIPTION: <user description>
RULES: full body visible head to feet, ONE character only, solid magenta background (#FF00FF), no text, no labels, no UI overlays
NEGATIVE: cropped body, multiple characters, text overlays, watermarks, white background, transparent background
```

Each slot is filled from the preset catalogs in this file and `wrestler-archetypes.md`. The orchestrator never asks the LLM to "be creative about the style" — the style is fixed at the slot level so the same preset produces visually consistent output across runs.

## Adding a preset

1. Add a row to the table above with a single concrete prompt fragment.
2. The fragment must be one to three sentences. Longer fragments cause the model to lose other slot information.
3. Era/hardware names only. No "looks like Mario", no "Final Fantasy style". These trigger trademark filters and produce inconsistent output across backends.
4. Test with both backends (Codex CLI and Nano Banana) — fragments that work on one may produce flat output on the other.
5. Add a one-line entry to the `--style` choices list in `sprite_prompt.py`.

<!-- no-pair-required: section header; pair lives in subsection -->
## Patterns to Detect and Fix

### Signal: Trademarked franchise names in style strings

**Detection**: `--style-string "Pokemon-style sprite"` or "in the style of Final Fantasy 6".

**Why it matters**: Backends silently filter or transform trademarked terms, producing inconsistent output across runs. Some backends refuse the prompt entirely, so reproducibility breaks when provider filtering changes.

**Preferred action**: Use era/hardware language (`gameboy-4color`, `snes-16bit-jrpg`). Describe the visual properties directly: palette, dithering, outline weight, and perspective. Era names avoid trademark friction and translate consistently.

## Reference loading hint

Load this file when the user picks a style or asks "what styles are available". Reserve it for style selection — the SKILL.md table is enough at routing time.
