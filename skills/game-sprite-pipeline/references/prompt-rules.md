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

## Portrait-loop-mode addendum

Portrait-loop generates a 2x2 = 4-frame subtle idle loop (breathing + blink) in ONE Codex call. The output is a 1024x1024 image with 4 cells of 512x512 each; downstream extraction treats it as a 4-frame spritesheet at 200ms/frame (800ms total cycle).

The prompt must stress that the four cells are NEAR-IDENTICAL — only minor breath/blink variation, never new poses. If the model interprets "loop" as "animation cycle" it will draw four different poses and the result looks like a flipbook, not a portrait.

Append after the Universal Rules (replaces PORTRAIT_RULES, do not include both):

```
PORTRAIT_LOOP_RULES:
- 2x2 grid of FOUR cells; each cell contains the SAME character at the
  SAME framing, SAME pose, SAME background, SAME camera angle
- the four cells differ ONLY in subtle breath + blink variation:
  - frame 0 (top-left):  neutral, eyes open, chest at rest
  - frame 1 (top-right): subtle inhale, eyes still open, chest slightly
    expanded (2-3 pixel difference, NOT a deep breath)
  - frame 2 (bottom-left): blink — eyes CLOSED, body identical to frame 0
  - frame 3 (bottom-right): subtle exhale, eyes open, chest slightly
    compressed (2-3 pixel difference, NOT a deflated chest)
- DO NOT change the pose, the camera angle, the lighting, or the costume
  between cells; this is an idle loop, not an action sequence
- the four characters must be PIXEL-IDENTICAL except for eye state and
  the subtle chest-breath delta — viewers should barely notice the change
```

Tuning notes:
- 1024x1024 source, 512x512 cells. Smaller cells produce muddy faces; larger requires `--max-canvas` overrides.
- 200ms/frame at 4 frames = 800ms loop. Longer (300ms) feels sleepy; shorter (150ms) reads as twitchy.
- Always pair with `ground-line` anchor (default) so the four near-identical bodies stay perfectly registered.
- Reuse the same DESCRIPTION text as a static portrait — no need to add "looking forward" or "neutral pose"; the loop rules carry the pose constraint.

## Portrait-loop intensity modes (`loop_intensity` parameter)

The default `idle-breath` rules (above) produce a near-static loop —
breathing + blink only. User feedback during 2026-04-25 session: "almost
no change between frames — boring" for character-loop assets where the
motion should be the point (samurai sword flourish, mage spell circle
casting, cyberpunk hacker typing).

`compose_portrait_loop_prompt(meta, loop_intensity=...)` selects between
three rule blocks based on the spec's `loop_intensity` field:

| Mode | Per-frame variation | Mean frame-diff baseline | When to use |
|---|---|---|---|
| `idle-breath` (default) | breath + blink only; "viewers should barely notice" | 2.46-2.50 | static portrait that should feel alive but not animated |
| `gestural-movement` | 4 distinct visible gestures (head turns, hand poses, weight shifts) at the SAME pose framing | 11.69-13.x | character-loop assets where personality should read across the cycle |
| `action-loop` | full continuous action cycle (cast spell, sword flourish, flame breath, ripple) | 14.x-39.50 | effect-bearing or motion-heavy character loops where motion IS the asset |

The intensity is NOT a frame-count change — every mode is still 2x2 = 4
frames at 200ms each (800ms loop). What changes is the per-cell rule block:
`idle-breath` says "PIXEL-IDENTICAL except for eye state and chest delta",
while `action-loop` says "treat the four cells as four phases of a
continuous motion".

**How specs declare intensity.** The asset spec dict carries
`"loop_intensity": "action-loop"` (or `"gestural-movement"`).
`compose_portrait_loop_prompt` reads `meta.loop_intensity` (defaulting to
`idle-breath` for backward compat). Use the gestural and action modes for
character-loop assets where motion should read across the cycle; keep
`idle-breath` for meditative or contemplative portraits.

**Diff baseline measurement.** A simple offline check computes the mean
per-pixel RGBA delta across the 4-cell loop. The baselines above are the
empirical floor / ceiling per intensity, useful as a sanity check: a
`gestural-movement` asset that measures 2.x is suspiciously close to idle
and the prompt likely failed to cross the intensity boundary.

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
| `running-to-ropes` | 16 frames (4x4) | Stand → lean-forward → push-off → strides 1-12 → arrive-at-ropes |
| `top-rope-dive` | 8 frames (4x2) | Climb 1-3 → balance → leap → mid-air → descent → land/impact |
| `clothesline` | 16 frames (4x4) | Stand → run-up x4 → windup-arm-out → lean-into → impact → recover x6 |
| `vertical-suplex` | 16 frames (4x4) | Setup → grip → lift x3 → flip-airborne → impact → pin-cover → hold |
| `megaphone-rant` | 16 frames (4x4) | Idle → raise-megaphone → shout → lean-forward → arm-wave → sneer → recover |
| `spinning-heel-kick` | 16 frames (4x4) | Stance → turn 1-4 → leg-extend → foot-impact → spin-out → recover-stance |

Action templates are non-exhaustive; users can supply free-form `--action` text.

## Action-mode prompt template (painted styles)

Painted-style action spritesheets (slay-the-spire-painted, hand-painted
illustration) are HARDER than pixel-art animation because the model must
keep painted brushwork consistent across many cells while changing only
the pose. Without explicit cross-cell consistency stress, the model
produces N different paintings of similar characters instead of N frames
of one character animating.

The action-mode prompt template (used for the 19-24 demo assets):

```
ART_STYLE: {painted style fragment from style-presets}

DESCRIPTION: {character description, gear, build}

ACTION_RULES (cross-cell consistency, LOAD-BEARING):
- the SAME character appears in EVERY cell — same face, same costume,
  same hair, same gear, same proportions, same color palette
- the SAME painted-style treatment in every cell — same rim lighting
  direction, same brushwork density, same outline thickness, same
  shadow contrast
- the ONLY thing that changes between cells is the POSE for {ACTION}
- treat the cells as 16 (or 8, or N) ANIMATION FRAMES of a single
  continuous motion, not 16 separate portraits

{GRID_RULES — cell layout, magenta bg, NEGATIVE block}
```

The repetition of identity ("SAME character", "SAME costume", "SAME rim
lighting") is the load-bearing instruction. Drop it and the model
defaults to "draw 16 wrestlers" rather than "draw 16 frames of one
wrestler". The phrase "treat the cells as N animation frames of a single
continuous motion" frames the task as animation rather than illustration.

Tested actions in `slay-the-spire-painted` style (demo assets 19-24):

- `19-veteran-running-to-ropes` — 4x4=16 frames, 256px cells: sprint cycle
- `20-luchadora-top-rope-dive` — 4x2=8 frames, 256px cells: climb + dive
- `21-giant-clothesline` — 4x4=16 frames, 256px cells: windup + impact
- `22-tech-suplex` — 4x4=16 frames, 256px cells: lift + flip + impact
- `23-manager-megaphone-rant` — 4x4=16 frames, 256px cells: gesticulation
- `24-spinning-heel-kick` — 4x4=16 frames, 256px cells: turn + extend

Painted-style action sheets cost ~2-3x more Codex generation time than
pixel-art equivalents because the model needs more attention budget to
maintain cross-cell consistency. Budget accordingly.

## Backend-specific tweaks

| Backend | Tweak | Why |
|---------|-------|-----|
| Codex CLI | Repeat the magenta-bg instruction at the start AND end of the prompt | Codex sometimes drops the bg instruction when prompts run long |
| Nano Banana | Use shorter prompts (≤400 chars) | Nano Banana favors compact prompts; longer ones produce flatter output |
| Both | Keep all-caps emphasis out of prompts; standard prose-case keeps the pose instructions steady | Standard prose-case throughout |

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
## Prompt Structure Patterns to Detect and Fix

### Prompt Structure Patterns to Detect and Fix: Free-form prose without slot structure

**Signal:** "Generate a wrestler character that looks like a flamboyant showman with kabuki makeup in a dramatic pose with golden lighting".

**Why it matters:** Output is wildly inconsistent across runs because the model fills missing structure (background, framing, aspect, character count) freely. Reproducibility is impossible — the same prompt produces a different aspect, different pose, different framing each call.

**Preferred action**: Always go through `sprite_prompt.py` to compose a slot-structured prompt. The slot structure forces every required dimension (style, character, tier, rules, negatives) to be explicit. The same `--style --archetype --description` always produces the same prompt; only the model's stochastic sampling varies.

## Reference loading hint

Load this file when:
- Building a prompt manually (rare)
- Debugging prompt output that does not match expectations
- Adding a new action template or tweaking universal rules

For routine pipeline runs, `sprite_prompt.py` consumes this file's content programmatically; the model does not need to read it directly.
