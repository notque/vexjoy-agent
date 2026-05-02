# VFX Containment Rules

Effects in generated sprites must be **attached to the character silhouette** and **contained within frame boundaries**. Detached, ambient, or environmental effects cause background-removal failures and cross-frame contamination.

## Universal Rules

| Category | Allowed | Forbidden |
|---|---|---|
| Attached effects | Overlaps character silhouette, opaque pixel-style colors | Detached sparkles, floating icons |
| Shadows | None | Cast shadows, drop shadows, contact shadows, floor shadows |
| Glow/aura | None | Halos, auras, broad transparent glows, rim lighting |
| Motion cues | Body position conveys motion | Speed lines, motion trails, blur, smears, afterimages |
| UI elements | None | Text, labels, speech bubbles, health bars |
| Environment | None | Scenery, floor, dust clouds, weather particles |

## Per-State Rules

### Movement States

| State | Rule |
|---|---|
| `dash-right`, `dash-left` | Locomotion through body and limb movement only. No speed lines or dust trails. |
| `run`, `running`, `running-right`, `running-left`, `rush` | Locomotion through body and limb movement only. No speed lines or dust trails. |
| `jump`, `jumping` | Body position shows motion. No dust clouds, impact effects, or floor shadows. |
| `fall` | Body position shows descent. No wind lines or motion streaks. |
| `slide` | Body posture shows slide. No dust or friction effects. |
| `climb` | Limb positions show climbing. No environmental holds visible. |

### Combat States

| State | Rule |
|---|---|
| `attack`, `attack-punch`, `attack-kick` | Impact conveyed through pose extension. No impact stars, shockwaves, or hit flashes. |
| `hit-stun`, `hurt`, `failed` | Attached tears, smoke, or impact stars only. No detached symbols or red X marks. |
| `death` | Body collapse sequence. No floating souls, X-eyes, or detached symbols. |

### Energy States

| State | Rule |
|---|---|
| `special`, `cast`, `charge` | Attached energy effects only. No detached particles or broad transparent glows. |
| `review` | No effects. Pure pose-based inspection loop. |

### Neutral States

| State | Rule |
|---|---|
| `idle`, `waiting` | Breathing/blink loop only. No ambient particles or idle effects. |
| `taunt`, `waving`, `entrance`, `crouch` | Gesture-based. No celebratory particles or confetti. |

## Implementation

VFX containment rules are injected into row-strip prompts by `sprite_prompt.compose_row_strip_prompt()`:

1. `VFX_CONTAINMENT_RULES` — universal block appended to every row prompt
2. `VFX_STATE_RULES[state]` — per-state override appended when the state has a specific rule

Both constants live in `sprite_prompt.py`. The prompt builder appends them after `UNIVERSAL_RULES` and before `UNIVERSAL_NEGATIVE`.

## Rationale

Detached effects cause three downstream failures:
1. **Background removal**: Floating sparkles outside the silhouette get masked as background
2. **Frame distinction**: Ambient effects are inconsistent across frames, inflating verify_frames_distinct false positives
3. **Identity consistency**: Auras and glows change character proportions, breaking identity lock verification
