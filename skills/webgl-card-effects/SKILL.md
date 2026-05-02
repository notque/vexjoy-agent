---
name: webgl-card-effects
description: "Standalone WebGL fragment shaders for card visual effects: holographic foil, shimmer, rarity glow."
agent: typescript-frontend-engineer
user-invocable: false
command: /card-effects
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
routing:
  triggers:
    - card effects
    - holographic
    - foil effect
    - card shimmer
    - card glow
    - shader card
    - WebGL card
    - rarity effects
    - Balatro effect
    - card visual effects
  pairs_with:
    - typescript-frontend-engineer
    - ui-design-engineer
  complexity: Medium
  category: frontend
---

# WebGL Card Effects Skill

## Overview

GPU-accelerated visual effects for React card components using standalone WebGL2 fragment shaders. No Three.js, no R3F, no external library. Targets deckbuilder games and card UIs where rarity tiers need visual distinction beyond CSS `box-shadow`.

**Scope**: Holographic foil, metallic shimmer, rarity-driven energy pulses, and interactive tilt-shine on React card components. Canonical target: `FramedCard.tsx` in React 19 / Vite / Tailwind with rarity system (starter -> common -> uncommon -> rare -> legendary).

**Not in scope**: 3D transforms, texture loading, post-processing, Three.js scene management. Use `threejs-builder` for those.

**Key constraint**: Browsers cap WebGL contexts at ~8-16 per page. This skill uses a single shared WebGL2 context with blit-to-2D-canvas per card. See `references/shader-integration-react.md` for the singleton pattern.

---

## Instructions

### Phase 1: ASSESS

**Goal**: Understand needed effects and confirm card component structure before writing code.

**Step 1: Read the card component**

Read before writing:
- `src/components/cards/FramedCard.tsx` — structure, hover state, rarity prop flow
- `src/components/cards/cardStyles.ts` — `CARD_SIZE_CONFIG` for dimensions, rarity values

Confirm:
- How rarity reaches the component (prop name, type, string values)
- Whether `isHovered` state exists
- Which sizes justify shader cost (xl/lg only; xs/sm too small)
- Whether `showShine` / `card-shine` CSS exists and needs coordination

**Step 2: Select effect tier per rarity**

| Rarity | WebGL? | Effect |
|--------|--------|--------|
| starter / common | No | CSS shimmer only |
| uncommon | Yes (subtle) | Metallic band shimmer, very low opacity |
| rare | Yes (medium) | Moving shimmer + blue hue shift + edge pulse |
| legendary | Yes (full) | Rainbow holographic foil, mouse-reactive tilt |

**Step 3: Confirm React version**

Check `package.json`. This skill assumes React 19 (ref as prop, no forwardRef). React 18 requires `useRef` + standard ref passing.

**Gate**: Rarity values confirmed, CARD_SIZE_CONFIG read, effect tiers decided.

---

### Phase 2: BUILD

**Goal**: Write GLSL shaders and WebGL initialization harness.

Load `references/card-shader-patterns.md` now.

**Step 1: Create shader strings module**

Create `src/components/cards/effects/cardShaders.ts` with:
- Shared vertex shader (passthrough UV coordinates)
- Three fragment shaders: `SHIMMER_FRAG`, `RARE_FRAG`, `LEGENDARY_FRAG`
- `rarityToUniform(rarity: string): number` mapping

Every shader must expose this uniform interface:

```glsl
uniform float u_time;        // seconds elapsed, JS wraps at 1000.0
uniform float u_rarity;      // 0.0=starter/common, 0.25=uncommon, 0.5=rare, 1.0=legendary
uniform float u_hover;       // 0.0 to 1.0, lerped by JavaScript each frame
uniform vec2  u_mouse;       // normalized card-space [0,1] mouse position
uniform vec2  u_resolution;  // canvas pixel dimensions (width, height)
uniform float u_upgraded;    // 0.0 or 1.0 — upgraded cards get slightly more intense
```

**Step 2: Create WebGL harness hook**

Create `src/components/cards/effects/useCardShader.ts`.

Load `references/shader-integration-react.md` for full hook source. The hook must:
- Use shared WebGL2 context singleton (not per-card context)
- Accept `{ rarity, isHovered, isUpgraded, enabled }`
- Return `RefObject<HTMLCanvasElement>` for the canvas element
- Pause animation when off-screen (IntersectionObserver)
- Run at 30fps max via delta-time throttle
- Clean up RAF loop and observer on unmount

**Step 3: Shader construction per tier**

Load `references/balatro-shader-breakdown.md` for legendary holographic GLSL source.

- Rare: shimmer band + hue shift layer, omit rainbow foil
- Uncommon: metallic band pass only (single moving highlight), opacity 0.3 max

**Gate**: `npx tsc --noEmit` passes. Browser console shows `gl.getShaderInfoLog()` returns empty string for all shaders.

---

### Phase 3: INTEGRATE

**Goal**: Mount canvas overlay on `FramedCard.tsx`, wire rarity/hover into shader uniforms.

**Step 1: Derive render decision**

```tsx
const shouldRenderShader =
  ['uncommon', 'rare', 'legendary'].includes(rarity) &&
  size !== 'xs' &&
  size !== 'sm';
```

**Step 2: Call the hook**

```tsx
const shaderCanvasRef = useCardShader({
  rarity,
  isHovered,
  isUpgraded,
  enabled: shouldRenderShader,
});
```

**Step 3: Add canvas overlay to JSX**

After the frame `<img>` element (after z-10):

```tsx
{shouldRenderShader && (
  <canvas
    ref={shaderCanvasRef}
    className="absolute inset-0 w-full h-full pointer-events-none rounded-lg"
    style={{ zIndex: 15, mixBlendMode: 'screen' }}
  />
)}
```

`mix-blend-mode: screen` makes black background transparent while bright holographic colors add onto the card.

**Step 4: Coordinate with existing CSS shine**

Suppress `card-shine` for rarities with WebGL shader:

```tsx
const shineClass =
  showShine && shouldShine && !shouldRenderShader
    ? `card-shine ${...}`
    : '';
```

**Step 5: Verify z-layer stack**

- `z-0` — artwork container
- `z-10` — frame PNG
- `z-15` — shader canvas (new)
- `z-20` — text elements (energy orb, name, description, type strip)
- Tooltip renders outside via `AnimatePresence` portal

Tailwind lacks `z-15` by default. Use `style={{ zIndex: 15 }}` inline (shown above).

**Gate**: Cards render at all sizes. Shader visible on uncommon/rare/legendary. No z-fighting. TypeScript clean.

---

### Phase 4: POLISH

**Goal**: Performance verification, visual tuning, mobile fallback.

**Step 1: Performance audit**

Chrome DevTools -> Performance tab. Record 5 seconds hovering a legendary card.

Targets:
- GPU usage: < 5% for single legendary card
- Frame time: shader must not push below 60fps
- No memory growth across mount/unmount cycles

**Step 2: Mobile fallback**

```typescript
function supportsWebGL2(): boolean {
  try {
    const canvas = document.createElement('canvas');
    return !!canvas.getContext('webgl2');
  } catch {
    return false;
  }
}
```

When `supportsWebGL2()` returns false, hook returns null ref, `shouldRenderShader` evaluates false. Existing `card-shine` CSS handles fallback.

**Step 3: Visual calibration**

- **Legendary**: Rainbow visible but not garish. Opacity 0.65-0.75. Animation at 0.5x real-time.
- **Rare**: Blue hue shift + shimmer. Premium feel, not cursor glow.
- **Uncommon**: Barely perceptible silver shimmer. If noticeable on static card, opacity too high.
- **Mouse tilt**: Feels like physically tilting card under light, not flashlight following cursor. Limit to +/-15 degrees.

**Step 4: Test across sizes**

| Size | Width | Shader? | Note |
|------|-------|---------|------|
| xs | 80px | No | Too small |
| sm | 110px | No | Too small |
| md | 140px | Optional | Test legibility first |
| lg | 170px | Yes | Minimum for full effect |
| xl | 200px | Yes | Primary target |

**Gate**: Performance targets met. Mobile fallback verified. Visual quality approved at lg/xl across all shader tiers.

---

## Error Handling

### "WebGL: INVALID_OPERATION: useProgram: program not valid"
Shader compilation failed. Call `gl.getShaderInfoLog(shader)` after `gl.compileShader(shader)`. Common: GLSL syntax error, missing `#version 300 es`, or unused uniform (compilers strip them).

### Canvas present but effect invisible
Check `mixBlendMode`. On dark backgrounds, `screen` blend makes dark shader output invisible. Debug: switch to `normal` blend. Verify canvas `zIndex` > frame PNG (15 > 10).

### "Too many active WebGL contexts"
Singleton not being used. Verify module-level singleton initialized once and reused. See `references/shader-integration-react.md`.

### Canvas stretched on high-DPI
Canvas `width`/`height` must match physical pixels, not CSS dimensions. Use ResizeObserver: `canvas.width = entry.contentRect.width * devicePixelRatio`.

### TypeScript: "Property 'ref' does not exist on 'HTMLCanvasElement'"
React 19 passes ref as prop. Use `<canvas ref={shaderCanvasRef} />` directly. Ensure ref type: `useRef<HTMLCanvasElement>(null)`.

---

## Reference Loading Table

| Task | Reference File |
|------|---------------|
| Fragment shader GLSL source | `references/card-shader-patterns.md` |
| React 19 WebGL hook + context pool | `references/shader-integration-react.md` |
| Balatro holographic foil breakdown | `references/balatro-shader-breakdown.md` |

Load only the reference needed for the current phase. All three together ~1,400 lines.
