# Prompt Rules

Slot-based prompt scaffolding. The orchestrator never passes free prose to the backend — every prompt is a structured composition of slots loaded from preset catalogs. This keeps output reproducible across runs and across backends.

## Slot structure

| Slot | Source | Required? | Purpose |
|------|--------|-----------|---------|
| `ART_STYLE` | `style-presets.md` preset | Yes | Visual treatment (palette, dithering, perspective) |
| `CHAR_STYLE` | `wrestler-archetypes.md` archetype + gimmick | Optional | Character build/color/presentation |
| `TIER` | `wrestler-archetypes.md` tier | Optional | Gear quality + venue signal |
| `DESCRIPTION` | User free text via `--description` | Yes | Specific character details |
| `RULES` | This file (Universal Rules block) | Yes | Background, framing, "ONE character" enforcement |
| `NEGATIVE` | This file (Universal Negatives block) | Yes | Cropping, multiple characters, watermarks |
| `GRID_RULES` | This file (Grid block) | Spritesheet only | Cell-by-cell placement instructions |

The order matters. Place `ART_STYLE` first so the model commits to visual treatment before the character definition lands; place `RULES` and `NEGATIVE` last so they shadow any conflicting language earlier in the prompt.

## Universal Rules block (portrait + spritesheet)

```
RULES:
- ONE character only, full body visible from head to feet, centered in frame
- solid magenta background color (#FF00FF), filling all space outside the character silhouette
- no text, no labels, no UI overlays, no speech bubbles, no watermarks
- character occupies approximately 70-85% of vertical canvas (not extending edge-to-edge)
- single composition, no panel borders, no comic-strip layout
```

## Universal Negatives block

```
NEGATIVE:
- cropped body, head cut off, legs cut off, arms cut off
- multiple characters, group shot, crowd scene
- text overlays, captions, signatures, artist watermarks
- white background, transparent background, gradient background, photographic background
- visible audience, ring announcer, microphone in frame
- nudity (wrestlers wear gear; this is a costuming style)
```

These negatives are applied verbatim in both portrait and spritesheet modes. Do not edit at runtime — change the slot content in this file if behavior needs to change globally.

## Portrait-mode addendum

Append after the Universal Rules:

```
PORTRAIT_RULES:
- character standing in neutral pose (not crouched, not jumping, not lying down)
- aspect ratio approximately 1:1.8 (height:width); character is taller than wide
- feet visible at bottom of frame with small margin (~5% of canvas height)
- head visible at top with small margin (~5% of canvas height)
```

Why these specifics: road-to-aew's existing 87 enemy + 8 player sprites cluster around 1:1.8 aspect. The dimension validator gates on this range. Prompting for the desired aspect up front reduces re-generation rate.

## Spritesheet-mode addendum

Append after the Universal Rules in Phase C:

```
GRID_RULES:
- the canvas is divided into a {COLS}x{ROWS} grid of cells
- place ONE frame of the character in each cell, performing {ACTION}
- frames must stay within their assigned cell; do not overflow grid lines
- the character should appear at consistent scale across all cells
- frame {N} shows {FRAME_DESCRIPTION_N}
```

`{ACTION}` is filled from the user's `--action` flag (e.g., "walking", "throwing a punch", "idle breathing"). `{FRAME_DESCRIPTION_N}` is filled per cell when `--frame-descriptions` is supplied as a list.

If no per-frame descriptions are given, the orchestrator emits generic intermediate frames:

```
walking: frame 0 = right foot forward; frame 1 = mid-step; frame 2 = left foot forward; frame 3 = mid-step (mirror of frame 1)
```

These are stored in `sprite_prompt.py` as named action templates. Adding a new action requires editing the template dict.

## Action templates

| Action | Frame count guidance | Frame breakdown |
|--------|----------------------|-----------------|
| `walking` | 4 or 8 frames per direction | Foot-forward → mid-step → opposite-foot → mid-step (mirror) |
| `idle` | 2 or 4 frames | Breath in → breath out (loop) |
| `attack-punch` | 4 frames | Wind-up → extend → impact → recover |
| `attack-kick` | 5 frames | Wind-up → leg-back → extend → impact → recover |
| `hit-stagger` | 3 frames | Recoil → off-balance → recover |
| `death` | 4 frames | Stagger → fall-start → fall-mid → ground |
| `entrance` | 6 frames | Standing → arms-up → flex-pose → recovery → standing (loop variant) |

Action templates are non-exhaustive; users can supply free-form `--action` text.

## Backend-specific tweaks

| Backend | Tweak | Why |
|---------|-------|-----|
| Codex CLI | Repeat the magenta-bg instruction at the start AND end of the prompt | Codex sometimes drops the bg instruction when prompts run long |
| Nano Banana | Use shorter prompts (≤400 chars) | Nano Banana favors compact prompts; longer ones produce flatter output |
| Both | Avoid all-caps emphasis; the model interprets caps as shouting and may produce overly dramatic poses | Standard prose-case throughout |

These tweaks are applied automatically by `sprite_generate.py` when it knows which backend will run — the user does not need to think about them.

## Example: composed portrait prompt

```
ART_STYLE: Hand-painted illustration style: heavy black ink outlines, saturated rich colors (deep reds, golds, purples), golden glowing aura around character, 3/4 isometric perspective from slightly above, painterly brushwork visible, atmospheric rim lighting

CHAR_STYLE: theatrical flamboyant build, showman frame, magenta and gold gear with rhinestones, dramatic pose. villainous presentation, sneering expression, dark accents on gear, intimidating posture.

TIER: upgraded gear, custom-fit shorts and boots, mid-tier sponsor logos visible. mid-tier venue context (lighting suggests theater or small arena, polished production).

DESCRIPTION: Bangkok Belle Nisa, kabuki-inspired makeup, Thai national colors woven into the showman gear, mid-30s confident expression

RULES:
- ONE character only, full body visible from head to feet, centered in frame
- solid magenta background color (#FF00FF), filling all space outside the character silhouette
- no text, no labels, no UI overlays, no speech bubbles, no watermarks
- character occupies approximately 70-85% of vertical canvas

PORTRAIT_RULES:
- character standing in neutral pose
- aspect ratio approximately 1:1.8 (height:width)
- feet visible at bottom with small margin
- head visible at top with small margin

NEGATIVE:
- cropped body, head cut off, legs cut off, arms cut off
- multiple characters, group shot
- text overlays, captions, watermarks
- white background, transparent background
```

`sprite_prompt.py build-portrait` produces this composition automatically; the user supplies only `--style`, `--archetype`, `--gimmick`, `--tier`, and `--description`.

<!-- no-pair-required: section header; pair lives in subsection -->
## Anti-pattern

### Anti-pattern: Free-form prose without slot structure

**What it looks like:** "Generate a wrestler character that looks like a flamboyant showman with kabuki makeup in a dramatic pose with golden lighting".

**Why wrong:** Output is wildly inconsistent across runs because the model fills missing structure (background, framing, aspect, character count) freely. Reproducibility is impossible — the same prompt produces a different aspect, different pose, different framing each call.

**Do instead**: Always go through `sprite_prompt.py` to compose a slot-structured prompt. The slot structure forces every required dimension (style, character, tier, rules, negatives) to be explicit. The same `--style --archetype --description` always produces the same prompt; only the model's stochastic sampling varies.

## Reference loading hint

Load this file when:
- Building a prompt manually (rare)
- Debugging prompt output that does not match expectations
- Adding a new action template or tweaking universal rules

For routine pipeline runs, `sprite_prompt.py` consumes this file's content programmatically; the model does not need to read it directly.
