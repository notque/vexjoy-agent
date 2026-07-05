
# WebGL Card Effects Skill

## Overview

This skill adds GPU-accelerated visual effects to React card components using standalone WebGL2 fragment shaders — no Three.js, no R3F, no external library required. It targets deckbuilder games and card UIs where rarity tiers should feel visually distinct, not just differentiated by a CSS `box-shadow` value.

**Scope**: Holographic foil overlays, metallic shimmer bands, rarity-driven energy pulses, and interactive tilt-shine effects mounted directly on React card components. The canonical target is `FramedCard.tsx` in a React 19 / Vite / Tailwind project with a rarity system (starter → common → uncommon → rare → legendary).

**Not in scope**: 3D transformations, texture loading, post-processing pipelines, or any Three.js scene management. For those, use `threejs-builder`.

**Key constraint**: Browsers cap WebGL contexts at roughly 8–16 total per page. This skill uses a single shared WebGL2 context with blit-to-2D-canvas output per card, avoiding the per-card context problem entirely. See `references/shader-integration-react.md` for the full singleton pattern.


### Phase 2: BUILD

**Goal**: Write working GLSL shaders and the WebGL initialization harness.

Load `references/card-shader-patterns.md` now.

**Step 1: Create the shader strings module**

Create `src/components/cards/effects/cardShaders.ts`. This file holds:
- The shared vertex shader (passthrough UV coordinates)
- Three fragment shader strings: `SHIMMER_FRAG`, `RARE_FRAG`, `LEGENDARY_FRAG`
- A `rarityToUniform(rarity: string): number` mapping function

Every shader must expose this exact uniform interface:

```glsl
uniform float u_time;        // seconds elapsed, JS wraps at 1000.0
uniform float u_rarity;      // 0.0=starter/common, 0.25=uncommon, 0.5=rare, 1.0=legendary
uniform float u_hover;       // 0.0 to 1.0, lerped by JavaScript each frame
uniform vec2  u_mouse;       // normalized card-space [0,1] mouse position
uniform vec2  u_resolution;  // canvas pixel dimensions (width, height)
uniform float u_upgraded;    // 0.0 or 1.0 — upgraded cards get slightly more intense effect
```

**Step 2: Create the WebGL harness hook**

Create `src/components/cards/effects/useCardShader.ts`.

Load `references/shader-integration-react.md` for the full hook source. The hook must:
- Use the shared WebGL2 context singleton (not create a new context per card)
- Accept `{ rarity, isHovered, isUpgraded, enabled }` as input
- Return a `RefObject<HTMLCanvasElement>` that the component attaches to the canvas element
- Pause the animation loop when the card is off-screen (IntersectionObserver)
- Run at 30fps maximum via delta-time throttle
- Clean up the RAF loop and observer on unmount

**Step 3: Shader construction for each tier**

Load `references/balatro-shader-breakdown.md` for the legendary holographic shader GLSL source.

For rare: use the shimmer band + hue shift layer from the breakdown, omit the rainbow foil layer.

For uncommon: use only the metallic band pass (single moving highlight), opacity 0.3 maximum.

**Gate**: Run `npx tsc --noEmit`. Zero TypeScript errors. Open browser console and verify `gl.getShaderInfoLog()` returns empty string for all shaders.


### Phase 4: POLISH

**Goal**: Performance verification, visual tuning, mobile fallback confirmation.

**Step 1: Performance audit**

Open Chrome DevTools → Performance tab. Record 5 seconds while hovering over a legendary card.

Targets:
- GPU usage: < 5% for a single legendary card
- Frame time: shader must not push game loop below 60fps
- No memory growth across multiple mount/unmount cycles (check Heap in Memory tab)

**Step 2: Mobile fallback verification**

```typescript
// In useCardShader.ts — call this once at module load
function supportsWebGL2(): boolean {
  try {
    const canvas = document.createElement('canvas');
    return !!canvas.getContext('webgl2');
  } catch {
    return false;
  }
}
```

On devices where `supportsWebGL2()` returns false, the hook returns a null ref and `shouldRenderShader` must evaluate to false. The existing `card-shine` CSS handles the fallback. Verify this works by temporarily forcing the function to return false.

**Step 3: Visual calibration**

- **Legendary**: Rainbow visible but not garish. Effective opacity 0.65–0.75 over the card. Animation speed: `u_time` advances at 0.5× real-time (not 1:1 — too fast feels cheap).
- **Rare**: Blue hue shift + shimmer. Feels premium, not like a cursor glow effect.
- **Uncommon**: Barely perceptible silver shimmer. If you notice it immediately on a static card, the opacity is too high.
- **Mouse tilt**: The holographic angle shift should feel like physically tilting a card under light, not like a flashlight following the cursor. Limit the angular response to ±15 degrees of apparent rotation.

**Step 4: Test across all rendered sizes**

| Size | Width | Shader? | Note |
|------|-------|---------|------|
| xs | 80px | No | Too small — no overhead |
| sm | 110px | No | Too small — no overhead |
| md | 140px | Optional | Test legibility first |
| lg | 170px | Yes | Minimum size for full effect |
| xl | 200px | Yes | Primary target — should look best |

**Gate**: All DevTools performance targets met. Mobile fallback verified. Visual quality approved at lg and xl sizes across all three shader tiers.


## Reference Loading Table

| Task | Reference File |
|------|---------------|
| Fragment shader GLSL source | `references/card-shader-patterns.md` |
| React 19 WebGL hook + context pool | `references/shader-integration-react.md` |
| Balatro holographic foil breakdown | `references/balatro-shader-breakdown.md` |

Load only the reference needed for the current phase. All three together is ~1,400 lines — only load all three if implementing everything in one pass.
