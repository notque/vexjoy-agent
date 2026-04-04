# PixiJS v8 Post-Processing Reference

> **Scope**: pixi-filters v6+ filter system for PixiJS v8, filter chain composition, bloom, vignette, color grading, chromatic aberration, performance budgets
> **Version range**: pixi.js ^8.5.0, pixi-filters (v6+ required for v8)
> **Note**: Individual `@pixi/filter-*` packages (bloom, noise, etc.) are no longer maintained for v8. Import from `pixi-filters` directly.

---

## Installation

```bash
npm install pixi-filters
```

Verify you are using the v8-compatible release of pixi-filters:

```bash
npm ls pixi-filters
# Should show: pixi-filters@6.x.x or higher
```

v5 and below are for PixiJS v7 — they will fail at runtime with v8.

---

## Import Patterns

In pixi-filters v6+ for v8, filters are imported as named exports:

```typescript
import {
  AdvancedBloomFilter,
  VignetteFilter,
  CRTFilter,
  GodrayFilter,
  OldFilmFilter,
} from 'pixi-filters';

import {
  // Built-in PixiJS v8 filters (no separate package)
  BlurFilter,
  ColorMatrixFilter,
  DisplacementFilter,
  NoiseFilter,
  AlphaFilter,
} from 'pixi.js';
```

---

## Filter Chain Composition

Filters are applied as an array on any display object or container. They execute in array order — each filter receives the output of the previous one as input.

```typescript
import { Container } from 'pixi.js';
import { AdvancedBloomFilter, VignetteFilter } from 'pixi-filters';

const sceneContainer = new Container();

const bloom = new AdvancedBloomFilter({
  threshold: 0.5,
  bloomScale: 0.8,
  brightness: 1.0,
  blur: 8,
  quality: 4,
});

const vignette = new VignetteFilter({
  alpha: 0.6,
  size: 0.5,
});

// Order: bloom first, then vignette over the bloomed image
sceneContainer.filters = [bloom, vignette];
```

Chain order rules:
1. Bloom runs before vignette — bloom on the raw image, vignette darkens edges after
2. Chromatic aberration runs last — it distorts the final composed image
3. Color grading (ColorMatrixFilter) runs after bloom — grading the post-bloom output
4. DisplacementFilter for screen shake runs early — before color effects

---

## AdvancedBloomFilter

The primary visual quality upgrade. Adds glow to bright areas of the combat scene.

```typescript
import { AdvancedBloomFilter } from 'pixi-filters';

// Combat scene bloom — moderate, not overwhelming
const combatBloom = new AdvancedBloomFilter({
  threshold: 0.5,    // pixels brighter than this glow (0-1)
  bloomScale: 0.8,   // glow intensity
  brightness: 1.0,   // overall brightness multiplier (keep at 1 unless intentional)
  blur: 8,           // glow radius in pixels
  quality: 4,        // blur pass count — higher = softer glow, more GPU cost
  resolution: window.devicePixelRatio,
  pixelSize: { x: 1, y: 1 },
});

// Finisher special bloom — more intense
const finisherBloom = new AdvancedBloomFilter({
  threshold: 0.3,    // more pixels glow
  bloomScale: 1.5,
  brightness: 1.1,
  blur: 16,
  quality: 6,
  resolution: window.devicePixelRatio,
});
```

Threshold guide:
- 0.5–0.7: Subtle — only very bright whites glow (good default)
- 0.3–0.5: Moderate — character highlights and effect particles glow
- 0.1–0.3: Heavy — most of the scene glows (finisher only)

Quality trade-off:
- `quality: 2` — Fast, slightly blocky bloom. Good for mobile.
- `quality: 4` — Default. Smooth bloom for most cases.
- `quality: 8` — Very smooth but 4x the cost. Use only for finisher freeze-frame.

---

## VignetteFilter

Darkens the edges of the canvas, drawing the eye to the center of the combat scene.

```typescript
import { VignetteFilter } from 'pixi-filters';

const vignette = new VignetteFilter({
  alpha: 0.6,      // darkness strength (0-1)
  size: 0.5,       // vignette start radius (0-1 from center)
  resolution: window.devicePixelRatio,
});
```

This replaces the CSS vignette overlay on `CombatArena.tsx` (`::after` pseudo-element with a radial gradient). The CSS approach is fine but can't react to game events. The PixiJS filter version can animate `alpha` during dramatic moments:

```typescript
// Animate vignette during finisher sequence
function triggerFinisherVignette(vignette: VignetteFilter): void {
  let elapsed = 0;
  const ticker = app.ticker.add((t) => {
    elapsed += t.deltaMS;
    // Pulse: expand to full screen darkness over 300ms
    vignette.alpha = Math.min(0.95, elapsed / 300);
    if (elapsed > 1500) {
      vignette.alpha = 0.6; // return to base
      app.ticker.remove(ticker);
    }
  });
}
```

---

## ColorMatrixFilter (Color Grading)

The `ColorMatrixFilter` built into PixiJS v8 provides color grading via a 4x5 matrix. Use preset methods rather than raw matrix values.

```typescript
import { ColorMatrixFilter } from 'pixi.js';

const colorGrade = new ColorMatrixFilter();

// Wrestling arena warm tone
colorGrade.saturate(0.2, false);   // slight saturation boost
colorGrade.warmth(0.1, false);     // warm yellow tint — arena lighting

// Submission hold — cool blue tint
colorGrade.reset();
colorGrade.tint(0x4080ff, false);  // blue overlay
colorGrade.saturate(-0.1, false);  // slightly desaturate

// Finisher — high contrast punch
colorGrade.reset();
colorGrade.brightness(1.1, false);
colorGrade.contrast(0.15, false);
colorGrade.saturate(0.3, false);
```

Available ColorMatrixFilter methods (all boolean `multiply` param for chain composition):
- `saturate(amount, multiply)` — -1 to 1
- `brightness(amount, multiply)` — 0 to 2
- `contrast(amount, multiply)` — -1 to 1
- `hue(rotation, multiply)` — degrees
- `tint(color, multiply)` — hex color
- `greyscale(scale, multiply)` — 0 to 1
- `sepia(multiply)` — classic sepia tone
- `technicolor(multiply)` — vivid high-contrast
- `night(intensity, multiply)` — dark blue-green night vision

---

## Chromatic Aberration

Splits color channels at the edges — creates a cheap cinematic lens effect. Best used sparingly on high-impact moments.

PixiJS v8 does not include a built-in chromatic aberration filter in pixi-filters. Use a simple custom filter:

```typescript
// src/combat/filters/ChromaticAberrationFilter.ts
import { Filter, GlProgram } from 'pixi.js';

const FRAG_SRC = `
  #version 300 es
  precision mediump float;

  in vec2 vTextureCoord;
  out vec4 fragColor;

  uniform sampler2D uTexture;
  uniform float uAmount;    // aberration offset in UV units (0.001 to 0.01)

  void main(void) {
    float r = texture(uTexture, vTextureCoord + vec2(uAmount, 0.0)).r;
    float g = texture(uTexture, vTextureCoord).g;
    float b = texture(uTexture, vTextureCoord - vec2(uAmount, 0.0)).b;
    float a = texture(uTexture, vTextureCoord).a;
    fragColor = vec4(r, g, b, a);
  }
`;

export class ChromaticAberrationFilter extends Filter {
  constructor(amount = 0.003) {
    const glProgram = GlProgram.from({
      fragment: FRAG_SRC,
      // Uses PixiJS default vertex shader
    });
    super({
      glProgram,
      resources: {
        caUniforms: {
          uAmount: { value: amount, type: 'f32' },
        },
      },
    });
    this.resolution = window.devicePixelRatio;
  }

  set amount(value: number) {
    this.resources.caUniforms.uniforms.uAmount = value;
  }
}
```

Usage — animate amount on hit:
```typescript
const ca = new ChromaticAberrationFilter(0.001); // subtle default

// On heavy hit: spike and decay
function triggerHitAberration(ca: ChromaticAberrationFilter): void {
  ca.amount = 0.008; // spike
  let elapsed = 0;
  const ticker = app.ticker.add((t) => {
    elapsed += t.deltaMS;
    ca.amount = Math.max(0.001, 0.008 - (elapsed / 200) * 0.007); // decay over 200ms
    if (elapsed >= 200) app.ticker.remove(ticker);
  });
}
```

---

## Full Combat Scene Filter Stack

```typescript
// src/combat/CombatScene.tsx — complete filter setup
import { useEffect, useRef } from 'react';
import { useApp } from '@pixi/react';
import { ColorMatrixFilter } from 'pixi.js';
import { AdvancedBloomFilter, VignetteFilter } from 'pixi-filters';
import { ChromaticAberrationFilter } from './filters/ChromaticAberrationFilter';
import type { Container } from 'pixi.js';

const isMobile = /iPhone|iPad|Android/i.test(navigator.userAgent);

export function useCombatFilters(containerRef: React.RefObject<Container | null>) {
  const app = useApp();

  useEffect(() => {
    if (!containerRef.current) return;

    const resolution = app.renderer.resolution;

    if (isMobile) {
      // Mobile: minimal filter stack — vignette only
      const vignette = new VignetteFilter({ alpha: 0.5, size: 0.5 });
      vignette.resolution = resolution;
      containerRef.current.filters = [vignette];
      return () => {
        vignette.destroy();
        if (containerRef.current) containerRef.current.filters = [];
      };
    }

    // Desktop: full stack
    const bloom = new AdvancedBloomFilter({
      threshold: 0.5,
      bloomScale: 0.8,
      brightness: 1.0,
      blur: 8,
      quality: 4,
    });
    bloom.resolution = resolution;

    const vignette = new VignetteFilter({ alpha: 0.6, size: 0.5 });
    vignette.resolution = resolution;

    const colorGrade = new ColorMatrixFilter();
    colorGrade.saturate(0.2, false);
    colorGrade.warmth(0.1, false);

    const ca = new ChromaticAberrationFilter(0.001);

    // Chain order: bloom → color grade → vignette → chromatic aberration
    containerRef.current.filters = [bloom, colorGrade, vignette, ca];

    return () => {
      [bloom, vignette, colorGrade, ca].forEach(f => f.destroy());
      if (containerRef.current) containerRef.current.filters = [];
    };
  }, [app.renderer.resolution]);
}
```

---

## Performance Budget

| Filter | GPU cost | Mobile? | Notes |
|--------|----------|---------|-------|
| `VignetteFilter` | Very low | Yes | Single pass, minimal math |
| `ColorMatrixFilter` | Very low | Yes | Single pass, matrix multiply |
| `AdvancedBloomFilter` quality:2 | Low | Marginal | 3 passes |
| `AdvancedBloomFilter` quality:4 | Medium | No | 5 passes |
| `AdvancedBloomFilter` quality:8 | High | No | 9 passes — finisher only |
| `ChromaticAberrationFilter` | Very low | Yes | Single pass |
| `NormalMapFilter` (from lighting ref) | Medium | No | Per-character only |

Desktop budget: 4 filter passes maximum on the root container.
Mobile budget: 2 filter passes maximum. Recommended stack: `[VignetteFilter, ColorMatrixFilter]`.

Each filter pass redraws the entire canvas texture. A 1920x1080 canvas with 5 filter passes at retina (devicePixelRatio: 2) = 5 × 3840 × 2160 = 41.5M pixels per frame at 60fps. That is the limit where mid-range mobile GPUs stall.

---

## How STS2 Does This in Godot

Slay the Spire 2 achieves its visual quality in Godot via:
- **WorldEnvironment** node with `SSEffect` and `Glow` enabled — equivalent to PixiJS `AdvancedBloomFilter`
- **Ambient light** and **CanvasModulate** for color grading — equivalent to `ColorMatrixFilter`
- Per-sprite **Normal Map** texture slots — equivalent to the custom `NormalMapFilter` in the lighting reference
- **Camera2D** `vignette` shader on the camera output — equivalent to `VignetteFilter`

The PixiJS stack in these references approximates all four of those systems.

---

## Anti-Patterns

### ❌ Applying filters to the HTML canvas element via CSS
```css
/* WRONG — CSS filters are CPU-only, bypass WebGL pipeline entirely */
canvas { filter: brightness(1.1) contrast(1.2); }
```
Apply all filters via the PixiJS filter system on display objects. CSS filters are calculated by the browser's compositor, not the GPU render pipeline, and cannot interact with PixiJS display objects.

### ❌ Using @pixi/filter-bloom (v7 package) with PixiJS v8
```typescript
// WRONG — v7 package, will throw at runtime with PixiJS v8
import { BloomFilter } from '@pixi/filter-bloom';
```
```typescript
// CORRECT — v8 package
import { AdvancedBloomFilter } from 'pixi-filters';
```

### ❌ Not setting filter.resolution on retina displays
Without matching resolution, filters render at 1x then upscale, appearing blurry on HiDPI screens. Always set `filter.resolution = app.renderer.resolution` after app init.

### ❌ Applying bloom to the UI overlay
Bloom applied to a container that includes text will blur the text. The filter processes everything in the container including children. Apply bloom only to the combat scene container, never to the HUD layer.

### ❌ Running AdvancedBloomFilter quality: 8 continuously
High quality bloom with 9 passes is acceptable for a 1-second finisher freeze-frame. Running it continuously at 60fps on a 1080p canvas will drop mobile to 15fps and will stress desktop GPUs. Reserve high-quality settings for triggered, time-limited events.
