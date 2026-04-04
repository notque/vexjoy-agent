# Balatro Holographic Shader Breakdown

Deep technical breakdown of the Balatro-style holographic foil card effect, adapted for wrestling deckbuilder card dimensions (400×560) and rarity-based color palettes. All GLSL targets `#version 300 es` (WebGL2).

The core Balatro technique: animated UV distortion layered with multi-octave noise, fed into a rainbow hue rotation function, with a Fresnel-like edge brightening that responds to mouse position. The result looks like a physical holographic foil card catching light.

---

## Technique Overview

Five layers compose the holographic effect:

1. **UV distortion field** — Slow-moving noise shifts the base UV coordinates, creating the "swimming" quality of real holo foil
2. **Rainbow hue rotation** — Distorted UV position maps to hue, creating the color-sweep bands
3. **Shimmer band** — A fast diagonal highlight band (the "catch" of light)
4. **Fresnel-like edge response** — Edges brighten as mouse moves to simulate viewing angle
5. **Mouse tilt influence** — Mouse position offsets the hue slightly, simulating physical card tilt

Each layer is blended together with the card's final color output using `mix-blend-mode: screen` at the HTML level — the shader outputs over a transparent background, so dark regions disappear and bright holographic regions add to the card.

---

## Complete Legendary Holographic Shader

This is the full copy-pasteable shader for the `legendary` tier. Import the noise functions from `card-shader-patterns.md` or inline them.

```glsl
#version 300 es
precision highp float;

in vec2 v_uv;
out vec4 fragColor;

// --- Uniforms ---
uniform float u_time;        // seconds, wraps at 1000.0
uniform float u_rarity;      // 1.0 for legendary
uniform float u_hover;       // 0.0–1.0 lerped
uniform vec2  u_mouse;       // card-space [0,1], (0.5,0.5) at rest
uniform vec2  u_resolution;  // canvas pixel size
uniform float u_upgraded;    // 0.0 or 1.0

// --- Noise functions (paste from card-shader-patterns.md or include via import) ---

// Hash for value noise
float hash(vec2 p) {
  p = fract(p * vec2(127.1, 311.7));
  p += dot(p, p + 19.19);
  return fract(p.x * p.y);
}

// 2D value noise
float valueNoise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(
    mix(hash(i),            hash(i + vec2(1.0, 0.0)), u.x),
    mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x),
    u.y
  );
}

// Simplex permutation helper
vec3 permute(vec3 x) {
  return mod(((x * 34.0) + 1.0) * x, 289.0);
}

// 2D simplex noise [-1,1]
float snoise(vec2 v) {
  const vec4 C = vec4(0.211324865405187, 0.366025403784439,
                     -0.577350269189626, 0.024390243902439);
  vec2 i  = floor(v + dot(v, C.yy));
  vec2 x0 = v - i + dot(i, C.xx);
  vec2 i1 = (x0.x > x0.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
  vec4 x12 = x0.xyxy + C.xxzz;
  x12.xy -= i1;
  i = mod(i, 289.0);
  vec3 p = permute(permute(i.y + vec3(0.0, i1.y, 1.0))
                 + i.x + vec3(0.0, i1.x, 1.0));
  vec3 m = max(0.5 - vec3(dot(x0,x0), dot(x12.xy,x12.xy), dot(x12.zw,x12.zw)), 0.0);
  m = m * m * m * m;
  vec3 x = 2.0 * fract(p * C.www) - 1.0;
  vec3 h = abs(x) - 0.5;
  vec3 a0 = x - floor(x + 0.5);
  m *= 1.79284291400159 - 0.85373472095314 * (a0*a0 + h*h);
  vec3 g;
  g.x  = a0.x  * x0.x   + h.x  * x0.y;
  g.yz = a0.yz * x12.xz + h.yz * x12.yw;
  return 130.0 * dot(m, g);
}

// fBm: 5 octaves for organic foil quality
float fbm5(vec2 p) {
  float v = 0.0, a = 0.5, f = 1.0;
  for (int i = 0; i < 5; i++) {
    v += a * snoise(p * f);
    f *= 2.0; a *= 0.5;
  }
  return v;
}

// --- HSV to RGB ---
vec3 hsv2rgb(float h, float s, float v) {
  vec3 rgb = clamp(abs(fract(h + vec3(0.0, 2.0/3.0, 1.0/3.0)) * 6.0 - 3.0) - 1.0, 0.0, 1.0);
  return v * mix(vec3(1.0), rgb, s);
}

// --- Main ---
void main() {
  vec2 uv = v_uv;

  // Aspect-correct UV for 400x560 card
  // Geometric operations (circles, isotropic noise) need this
  vec2 aspectUV = vec2(uv.x, uv.y * (400.0 / 560.0));

  // -------------------------------------------------------
  // Layer 1: UV Distortion Field
  // Slow-moving noise that shifts UV coords, creating the
  // "swimming" quality of real holographic foil
  // -------------------------------------------------------
  float distortSpeed = 0.12;  // Very slow — physical foil doesn't swim fast
  vec2 distortSeed = aspectUV * 2.5 + vec2(u_time * distortSpeed, u_time * distortSpeed * 0.7);
  float distortX = fbm5(distortSeed) * 0.18;
  float distortY = fbm5(distortSeed + vec2(3.7, 1.3)) * 0.18;
  vec2 distortedUV = uv + vec2(distortX, distortY);

  // -------------------------------------------------------
  // Layer 2: Mouse tilt influence
  // Mouse offset shifts the hue — simulates physical card tilt
  // At rest: mouse = (0.5, 0.5), no shift
  // Max tilt: ±0.15 hue units at card edge
  // -------------------------------------------------------
  vec2 mouseOffset = (u_mouse - 0.5) * 0.15;  // Center mouse at 0 offset
  // More influence when hovering (u_hover lerped in)
  vec2 tiltInfluence = mouseOffset * u_hover;

  // -------------------------------------------------------
  // Layer 3: Rainbow hue from distorted UV + tilt
  // Diagonal axis across card maps to full rainbow cycle
  // -------------------------------------------------------
  float diagAxis = (distortedUV.x + tiltInfluence.x) * 0.55
                 + (distortedUV.y + tiltInfluence.y) * 0.45;

  // Slow hue drift over time + mouse-driven shift
  float hueShift = u_time * 0.08;
  float hue = fract(diagAxis * 1.2 + hueShift);

  // Saturation: high but not 1.0 — fully saturated looks flat
  float sat = 0.75 + u_hover * 0.15;

  // Value: bright overall, enhanced on hover
  float val = 0.6 + u_hover * 0.25;

  vec3 rainbowColor = hsv2rgb(hue, sat, val);

  // -------------------------------------------------------
  // Layer 4: Fast shimmer band
  // Sharp diagonal highlight that sweeps quickly on hover
  // At rest: slow drift; on hover: 3x faster
  // -------------------------------------------------------
  float bandDiag = uv.x * 0.7 + uv.y * 0.3;
  float bandSpeed = 0.3 + u_hover * 0.9;
  float bandPhase = fract(bandDiag - u_time * bandSpeed);
  float band = smoothstep(0.0, 0.04, bandPhase) * smoothstep(0.14, 0.07, bandPhase);

  // Band is white-ish (adds brightness to the rainbow underneath)
  vec3 bandColor = vec3(0.9, 0.95, 1.0);
  float bandOpacity = band * (0.5 + u_hover * 0.4);

  // -------------------------------------------------------
  // Layer 5: Fresnel-like edge brightening
  // Edges respond to viewing angle (approximated by mouse position)
  // Without real geometry normals, we approximate with edge distance + mouse offset
  // -------------------------------------------------------
  vec2 edge = min(uv, 1.0 - uv);
  float edgeDist = min(edge.x, edge.y);
  float edgeGlow = 1.0 - smoothstep(0.0, 0.12, edgeDist);

  // Mouse position influences which edges brighten
  // When mouse is in top-left corner, top/left edges glow more
  float mouseAngle = atan(u_mouse.y - 0.5, u_mouse.x - 0.5);
  float edgeAngle = atan(uv.y - 0.5, uv.x - 0.5);
  float angleDiff = abs(cos(edgeAngle - mouseAngle));
  float fresnelResponse = edgeGlow * (0.3 + angleDiff * 0.5 * u_hover);

  vec3 edgeColor = mix(rainbowColor, vec3(1.0, 0.95, 0.9), 0.3);  // Warm edge highlight
  // Gold tint for legendary — matches the game's #FFB800 accent
  vec3 legendaryEdge = mix(edgeColor, vec3(1.0, 0.72, 0.0), 0.35 * u_rarity);

  // -------------------------------------------------------
  // Upgraded modifier: slight green shift on hue, stronger edge pulse
  // -------------------------------------------------------
  float upgradedHueShift = u_upgraded * 0.08;
  vec3 finalRainbow = hsv2rgb(fract(hue + upgradedHueShift), sat, val);

  // -------------------------------------------------------
  // Composite all layers
  // -------------------------------------------------------
  // Start with rainbow
  vec3 color = finalRainbow;

  // Add shimmer band on top (additive blend within shader)
  color = mix(color, color + bandColor, bandOpacity * 0.7);

  // Add edge brightening
  color = mix(color, legendaryEdge, fresnelResponse);

  // -------------------------------------------------------
  // Opacity calculation
  // Base opacity at rest: 0.45 (visible but not obscuring card art)
  // Peak opacity on hover: 0.70
  // The black background disappears via mix-blend-mode:screen in HTML
  // -------------------------------------------------------
  float baseOpacity = 0.45;
  float hoverBoost = 0.25;
  float opacity = baseOpacity + u_hover * hoverBoost;

  // Vignette: reduce effect near card center (keeps card art readable)
  // Card text is in the lower 45% — protect that region
  vec2 centered = uv - 0.5;
  float radialFade = 1.0 - smoothstep(0.15, 0.45, length(centered * vec2(1.0, 0.7)));

  // Text zone protection: lower portion of card
  float textProtect = smoothstep(0.45, 0.55, uv.y);  // fade out above y=0.5
  float finalVignette = radialFade * (0.4 + textProtect * 0.6);

  fragColor = vec4(color, opacity * finalVignette);
}
```

---

## Layer-by-Layer Explanation

### UV Distortion Field

Real holographic foil has micro-embossed patterns that cause adjacent areas to reflect different hues. The distortion field approximates this with slow fBm (fractional Brownian motion) noise that shifts UV coordinates. The key is **slow movement** — `distortSpeed = 0.12` means the pattern shifts visibly over about 8 seconds.

If you increase this to 0.5 or above, the card looks like it's underwater. Below 0.05, the animation is imperceptible at rest.

### Mouse Tilt Influence

The `u_mouse` uniform holds normalized card-space coordinates. At rest (cursor not on card), it should be set to `(0.5, 0.5)` — the center — so there's zero tilt offset. As the mouse moves toward a corner, the hue shifts by up to ±0.15 units.

```
mouse at (0.0, 0.0) → tiltInfluence = (-0.075, -0.075) → hue shifted toward warmer
mouse at (1.0, 1.0) → tiltInfluence = (0.075, 0.075) → hue shifted toward cooler
```

The `* u_hover` multiplier means the tilt has no effect when `u_hover = 0.0` (card at rest, not being hovered). This prevents the effect from jumping when the cursor first enters the card.

### Rainbow Hue Rotation

The diagonal axis `diagAxis = uv.x * 0.55 + uv.y * 0.45` maps position on the card to a position on a diagonal line. Multiplied by `1.2` and fed into `hsv2rgb`, this creates about 1.2 full rainbow cycles across the diagonal.

Adjusting the `1.2` multiplier:
- `0.5` — one half-cycle: card goes from red at one corner to cyan at the other
- `1.2` — slightly more than one cycle: most natural, looks like real foil
- `3.0` — three cycles: very dense, looks like cheap novelty foil

### Shimmer Band

The `band` computation creates a thin bright stripe that sweeps diagonally. `bandPhase = fract(bandDiag - u_time * bandSpeed)` makes the phase value advance continuously, so the stripe sweeps from corner to corner repeatedly.

`smoothstep(0.0, 0.04, bandPhase) * smoothstep(0.14, 0.07, bandPhase)` creates a peak at phase ≈ 0.07–0.10 with soft falloff. The `0.04` and `0.14` values control band width.

At `u_hover = 0.0`: band speed is `0.3` (one sweep every ~3 seconds). At `u_hover = 1.0`: speed is `1.2` (four sweeps per second). This is what "catches the light" when you hover.

---

## Color Palette Customization

The wrestling theme uses gold `#FFB800` as the primary accent. The legendary shader incorporates this in the edge glow:

```glsl
// #FFB800 in linear RGB ≈ (1.0, 0.72, 0.0)
vec3 legendaryEdge = mix(edgeColor, vec3(1.0, 0.72, 0.0), 0.35 * u_rarity);
```

To customize per rarity tier, these are the target palettes:

| Rarity | Primary Hue | Gold Accent | Saturation |
|--------|-------------|-------------|------------|
| uncommon | Silver/white (neutral) | None | 0.2 |
| rare | Blue 220°–240° | None | 0.7 |
| legendary | Full rainbow | Gold #FFB800 at edges | 0.75 |

For the rare tier (not in this shader, in `RARE_FRAG`), replace the rainbow hue rotation with a fixed blue hue:

```glsl
// Rare: blue hue range instead of full rainbow
float hue = 0.60 + fbm5(distortedUV * 2.0 + u_time * 0.1) * 0.06;
// 0.60 = 216°, range ±0.06 = 194°–238° (blue-violet band)
```

---

## Performance Characteristics

- Single render pass (no ping-pong or multiple draw calls)
- No texture lookups — fully procedural
- fBm at 5 octaves: ~5 `snoise()` calls per pixel. At 200×280 canvas (lg card at 1x DPR): ~280,000 noise evaluations per frame at 30fps = 8.4M noise evaluations/second. This is comfortably within WebGL2 fragment shader limits on integrated graphics.
- On mobile (low-end), reduce to 3 octaves: change `fbm5()` to loop `i < 3`. Quality is slightly lower but still recognizable as holographic foil.

Estimated GPU cost: < 0.5ms per frame for a single legendary card at 200×280 pixels on mid-range integrated graphics (Intel Iris / Apple M-series).

---

## Adapting for Non-Legendary Rarities

Strip layers in order from most to least expensive:

**Rare** (remove rainbow, keep shimmer + distortion):
```glsl
// Replace Layer 2+3 with fixed blue hue
float hue = 0.62 + distortX * 0.04;  // Blue, slight variation
// Keep Layer 4 (shimmer) and Layer 5 (edge)
// Reduce opacity: base 0.30, hover 0.55
```

**Uncommon** (shimmer only, no distortion, no edge):
```glsl
// Skip fBm entirely — use simple diagonal band
// Use neutral silver color vec3(0.8, 0.85, 1.0)
// Opacity: base 0.12, hover 0.25
// Remove edge glow and mouse tilt entirely
```

---

## Anti-Patterns

**Animating hue at full time speed**: `hue = fract(uv.x + u_time)` cycles through the full rainbow every second. Real holo foil shifts hue based on viewing angle, not time — it doesn't pulse like a disco ball. Use mouse position as the primary hue driver; time should only add a slow ambient drift.

**Skipping the distortion field for performance**: Without UV distortion, the rainbow bands are perfectly straight lines. Real holo foil has organic, slightly random banding. Even 2 octaves of noise (not 5) is enough to break the linearity.

**Using `opacity = 1.0`**: The shader is composited via `mix-blend-mode: screen`. At full opacity, the dark regions of the shader block the card art. Keep base opacity ≤ 0.5 at rest, ≤ 0.75 on hover.

**Hard-coding `u_rarity = 1.0` constants**: The shader should work across rarity values. Use `u_rarity` to scale the intensity of specific features (e.g., the gold edge accent is `0.35 * u_rarity` — at `u_rarity = 0.5` for rare, the gold is 50% as strong).

**Running at 60fps**: The shimmer animation at 30fps is indistinguishable from 60fps to human perception. The 30fps throttle in `useCardShader` halves GPU load. Only change this if the animation looks choppy at 30fps (it should not).

**Large canvas dimensions for small cards**: At `md` size (140px wide), a 140×178 canvas is 24,920 pixels. At `lg` (170px), it's 36,550 pixels. At 2x DPR, these double. The fragment shader runs per pixel — keep canvases sized to their CSS-rendered dimensions, not artificially large.
