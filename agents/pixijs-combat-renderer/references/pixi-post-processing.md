# PixiJS v8 Post-Processing Reference

> **Scope**: pixi-filters v6+ for PixiJS v8, filter chain composition, bloom, vignette, color grading, chromatic aberration, performance budgets
> **Version range**: pixi.js ^8.5.0, pixi-filters v6+ (required for v8)

---

## Installation

```bash
npm install pixi-filters
# Verify v6+: npm ls pixi-filters
```

Individual `@pixi/filter-*` packages are NOT maintained for v8. Import from `pixi-filters`.

---

## Import Patterns

```typescript
// pixi-filters v6+ (external)
import { AdvancedBloomFilter, VignetteFilter, CRTFilter, GodrayFilter } from 'pixi-filters';

// Built-in PixiJS v8 (no separate package)
import { BlurFilter, ColorMatrixFilter, DisplacementFilter, NoiseFilter, AlphaFilter } from 'pixi.js';
```

---

## Filter Chain Composition

Filters execute in array order. Each receives previous output as input.

```typescript
const bloom = new AdvancedBloomFilter({ threshold: 0.5, bloomScale: 0.8, brightness: 1.0, blur: 8, quality: 4 });
const vignette = new VignetteFilter({ alpha: 0.6, size: 0.5 });
sceneContainer.filters = [bloom, vignette];
```

Chain order: (1) Displacement/shake early, (2) Bloom, (3) Color grading, (4) Vignette, (5) Chromatic aberration last.

---

## AdvancedBloomFilter

```typescript
const combatBloom = new AdvancedBloomFilter({
  threshold: 0.5, bloomScale: 0.8, brightness: 1.0, blur: 8, quality: 4,
  resolution: window.devicePixelRatio,
});
```

Threshold guide: 0.5-0.7 subtle, 0.3-0.5 moderate, 0.1-0.3 heavy (finisher only).
Quality: 2 fast/mobile, 4 default, 8 finisher freeze-frame only.

---

## VignetteFilter

```typescript
const vignette = new VignetteFilter({ alpha: 0.6, size: 0.5, resolution: window.devicePixelRatio });

// Animate during finisher
function triggerFinisherVignette(vignette: VignetteFilter): void {
  let elapsed = 0;
  const ticker = app.ticker.add((t) => {
    elapsed += t.deltaMS;
    vignette.alpha = Math.min(0.95, elapsed / 300);
    if (elapsed > 1500) { vignette.alpha = 0.6; app.ticker.remove(ticker); }
  });
}
```

Replaces CSS `::after` vignette overlay on `CombatArena.tsx` — PixiJS version can animate reactively.

---

## ColorMatrixFilter (Color Grading)

```typescript
const colorGrade = new ColorMatrixFilter();

// Arena warm tone
colorGrade.saturate(0.2, false);
colorGrade.warmth(0.1, false);

// Submission blue tint
colorGrade.reset();
colorGrade.tint(0x4080ff, false);
colorGrade.saturate(-0.1, false);

// Finisher high contrast
colorGrade.reset();
colorGrade.brightness(1.1, false);
colorGrade.contrast(0.15, false);
colorGrade.saturate(0.3, false);
```

Methods: `saturate`, `brightness`, `contrast`, `hue`, `tint`, `greyscale`, `sepia`, `technicolor`, `night`.

---

## Chromatic Aberration (Custom Filter)

```typescript
import { Filter, GlProgram } from 'pixi.js';

const FRAG_SRC = `
  #version 300 es
  precision mediump float;
  in vec2 vTextureCoord;
  out vec4 fragColor;
  uniform sampler2D uTexture;
  uniform float uAmount;

  void main(void) {
    float r = texture(uTexture, vTextureCoord + vec2(uAmount, 0.0)).r;
    float g = texture(uTexture, vTextureCoord).g;
    float b = texture(uTexture, vTextureCoord - vec2(uAmount, 0.0)).b;
    fragColor = vec4(r, g, b, texture(uTexture, vTextureCoord).a);
  }
`;

export class ChromaticAberrationFilter extends Filter {
  constructor(amount = 0.003) {
    super({
      glProgram: GlProgram.from({ fragment: FRAG_SRC }),
      resources: { caUniforms: { uAmount: { value: amount, type: 'f32' } } },
    });
    this.resolution = window.devicePixelRatio;
  }
  set amount(value: number) { this.resources.caUniforms.uniforms.uAmount = value; }
}

// On hit: spike and decay over 200ms
function triggerHitAberration(ca: ChromaticAberrationFilter): void {
  ca.amount = 0.008;
  let elapsed = 0;
  const ticker = app.ticker.add((t) => {
    elapsed += t.deltaMS;
    ca.amount = Math.max(0.001, 0.008 - (elapsed / 200) * 0.007);
    if (elapsed >= 200) app.ticker.remove(ticker);
  });
}
```

---

## Full Combat Filter Stack

```typescript
const isMobile = /iPhone|iPad|Android/i.test(navigator.userAgent);

export function useCombatFilters(containerRef: React.RefObject<Container | null>) {
  const app = useApp();
  useEffect(() => {
    if (!containerRef.current) return;
    const resolution = app.renderer.resolution;

    if (isMobile) {
      const vignette = new VignetteFilter({ alpha: 0.5, size: 0.5 });
      vignette.resolution = resolution;
      containerRef.current.filters = [vignette];
      return () => { vignette.destroy(); if (containerRef.current) containerRef.current.filters = []; };
    }

    const bloom = new AdvancedBloomFilter({ threshold: 0.5, bloomScale: 0.8, brightness: 1.0, blur: 8, quality: 4 });
    bloom.resolution = resolution;
    const vignette = new VignetteFilter({ alpha: 0.6, size: 0.5 });
    vignette.resolution = resolution;
    const colorGrade = new ColorMatrixFilter();
    colorGrade.saturate(0.2, false); colorGrade.warmth(0.1, false);
    const ca = new ChromaticAberrationFilter(0.001);

    containerRef.current.filters = [bloom, colorGrade, vignette, ca];
    return () => { [bloom, vignette, colorGrade, ca].forEach(f => f.destroy()); if (containerRef.current) containerRef.current.filters = []; };
  }, [app.renderer.resolution]);
}
```

---

## Performance Budget

| Filter | GPU cost | Mobile? |
|--------|----------|---------|
| VignetteFilter | Very low | Yes |
| ColorMatrixFilter | Very low | Yes |
| AdvancedBloomFilter quality:2 | Low | Marginal |
| AdvancedBloomFilter quality:4 | Medium | No |
| AdvancedBloomFilter quality:8 | High | No (finisher only) |
| ChromaticAberrationFilter | Very low | Yes |
| NormalMapFilter | Medium | No |

Desktop: 4 filter passes max on root container.
Mobile: 2 passes max. Recommended: `[VignetteFilter, ColorMatrixFilter]`.

Each pass redraws entire canvas texture. 1920x1080 at retina (2x) with 5 passes = 41.5M pixels/frame at 60fps — mobile GPU stall threshold.

---

## Patterns to Fix

- **Apply filters via PixiJS, not CSS** — CSS `filter:` is CPU-only, bypasses WebGL pipeline.
- **Use pixi-filters v6+ for v8** — `@pixi/filter-bloom` is v7, throws at runtime.
- **Set filter.resolution on retina** — without it, renders at 1x, appears blurry.
- **Bloom on combat container only** — bloom on text container blurs text.
- **High-quality bloom for time-limited events only** — 9 passes at 60fps drops mobile to 15fps.
