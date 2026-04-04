# Card Shader Patterns

WebGL2 fragment shader patterns for card game visual effects. All shaders target `#version 300 es` (WebGL2). No texture lookups — all effects are procedural, running on any WebGL2-capable device without asset loading.

**Card aspect ratio**: 400×560 (5:7). UV coordinates are aspect-corrected where noted.

---

## Shader Architecture

Every card shader uses the same vertex shader. The fragment shader varies by effect tier.

### Shared Vertex Shader

```glsl
#version 300 es
precision highp float;

in vec2 a_position;  // clip-space quad: [-1,1] x [-1,1]
out vec2 v_uv;       // normalized [0,1] UV for the fragment shader

void main() {
  // Convert clip-space position to [0,1] UV
  v_uv = a_position * 0.5 + 0.5;
  gl_Position = vec4(a_position, 0.0, 1.0);
}
```

The vertex shader draws a full-screen quad covering the canvas. Two triangles, four vertices, no index buffer needed for a quad (use `TRIANGLE_STRIP`):

```typescript
// Quad geometry — reuse across all card canvases
const QUAD_VERTS = new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]);
```

### Uniform Interface (all shaders)

```glsl
// Required uniforms — every shader must declare all of these
uniform float u_time;       // elapsed seconds, JS wraps at 1000.0 to avoid float precision loss
uniform float u_rarity;     // 0.0=common, 0.25=uncommon, 0.5=rare, 1.0=legendary
uniform float u_hover;      // 0.0 to 1.0, lerped toward target each frame
uniform vec2  u_mouse;      // card-space mouse [0,1], (0.5,0.5) when not hovering
uniform vec2  u_resolution; // canvas pixel size (width, height)
uniform float u_upgraded;   // 0.0 or 1.0
```

---

## Noise Functions

All procedural effects use these noise primitives. Include whichever you need at the top of each fragment shader.

### Value Noise (fast, slightly blocky — good for energy pulses)

```glsl
// Hash function — maps vec2 to pseudo-random float in [0,1]
float hash(vec2 p) {
  p = fract(p * vec2(127.1, 311.7));
  p += dot(p, p + 19.19);
  return fract(p.x * p.y);
}

// 2D value noise with bilinear interpolation
float valueNoise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  // Smooth interpolation (C2 continuity)
  vec2 u = f * f * (3.0 - 2.0 * f);

  return mix(
    mix(hash(i),           hash(i + vec2(1.0, 0.0)), u.x),
    mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x),
    u.y
  );
}
```

### Simplex-Style Noise (smoother, organic — best for foil shimmer)

```glsl
// Based on Ian McEwan / Stefan Gustavson's simplex noise, adapted for WebGL2
vec3 permute(vec3 x) {
  return mod(((x * 34.0) + 1.0) * x, 289.0);
}

float snoise(vec2 v) {
  const vec4 C = vec4(
    0.211324865405187,   // (3.0-sqrt(3.0))/6.0
    0.366025403784439,   // 0.5*(sqrt(3.0)-1.0)
   -0.577350269189626,   // -1.0 + 2.0 * C.x
    0.024390243902439    // 1.0 / 41.0
  );

  vec2 i  = floor(v + dot(v, C.yy));
  vec2 x0 = v - i + dot(i, C.xx);
  vec2 i1 = (x0.x > x0.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
  vec4 x12 = x0.xyxy + C.xxzz;
  x12.xy -= i1;
  i = mod(i, 289.0);

  vec3 p = permute(permute(i.y + vec3(0.0, i1.y, 1.0))
                 + i.x + vec3(0.0, i1.x, 1.0));

  vec3 m = max(0.5 - vec3(
    dot(x0, x0),
    dot(x12.xy, x12.xy),
    dot(x12.zw, x12.zw)
  ), 0.0);

  m = m * m;
  m = m * m;

  vec3 x = 2.0 * fract(p * C.www) - 1.0;
  vec3 h = abs(x) - 0.5;
  vec3 ox = floor(x + 0.5);
  vec3 a0 = x - ox;
  m *= 1.79284291400159 - 0.85373472095314 * (a0 * a0 + h * h);

  vec3 g;
  g.x  = a0.x  * x0.x   + h.x  * x0.y;
  g.yz = a0.yz * x12.xz + h.yz * x12.yw;

  return 130.0 * dot(m, g);
}
```

### Fractional Brownian Motion (layered noise for organic foil)

```glsl
// fBm: sum multiple noise octaves for more organic motion
// Use 3 octaves for shimmer (fast), 5 for legendary foil (higher quality)
float fbm(vec2 p, int octaves) {
  float value = 0.0;
  float amplitude = 0.5;
  float frequency = 1.0;
  float lacunarity = 2.0;
  float gain = 0.5;

  for (int i = 0; i < 8; i++) {
    if (i >= octaves) break;
    value += amplitude * snoise(p * frequency);
    frequency *= lacunarity;
    amplitude *= gain;
  }
  return value;
}
```

---

## Effect 1: Metallic Shimmer (uncommon)

A single bright band that sweeps diagonally across the card surface. Subtle — opacity capped at 0.3.

```glsl
#version 300 es
precision highp float;

in vec2 v_uv;
out vec4 fragColor;

uniform float u_time;
uniform float u_rarity;   // Expected: 0.25 for uncommon
uniform float u_hover;
uniform vec2  u_resolution;

void main() {
  vec2 uv = v_uv;

  // Diagonal shimmer band: project UV onto diagonal axis
  float diagAxis = uv.x * 0.6 + uv.y * 0.4;

  // Band position oscillates with time, hover accelerates it
  float speed = 0.4 + u_hover * 0.6;
  float bandPos = fract(diagAxis - u_time * speed);

  // Soft band: sharp center, falloff on edges
  float band = smoothstep(0.0, 0.08, bandPos) * smoothstep(0.22, 0.12, bandPos);

  // Silver/white color for metallic feel
  vec3 shimmerColor = vec3(0.85, 0.90, 1.0);

  // Opacity: base 0.15 idle, up to 0.30 on hover
  float opacity = (0.15 + u_hover * 0.15) * band;

  // Vignette: fade toward card edges so effect stays centered
  vec2 centered = uv - 0.5;
  float vignette = 1.0 - smoothstep(0.3, 0.5, length(centered));

  fragColor = vec4(shimmerColor, opacity * vignette);
}
```

---

## Effect 2: Rare Shimmer + Blue Hue Shift

Shimmer band plus a blue-purple hue overlay and edge glow. Intensity doubles on hover.

```glsl
#version 300 es
precision highp float;

in vec2 v_uv;
out vec4 fragColor;

uniform float u_time;
uniform float u_rarity;   // Expected: 0.5 for rare
uniform float u_hover;
uniform vec2  u_mouse;
uniform vec2  u_resolution;
uniform float u_upgraded;

// [Include valueNoise and snoise from above]

// HSV to RGB for color cycling
vec3 hsv2rgb(vec3 c) {
  vec4 K = vec4(1.0, 2.0/3.0, 1.0/3.0, 3.0);
  vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
  return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}

void main() {
  vec2 uv = v_uv;

  // Aspect-correct UVs for 400x560 card (5:7 ratio)
  vec2 aspectUV = vec2(uv.x, uv.y * (560.0 / 400.0));

  // --- Shimmer band (same as uncommon, higher opacity) ---
  float diagAxis = uv.x * 0.6 + uv.y * 0.4;
  float speed = 0.5 + u_hover * 0.8;
  float bandPos = fract(diagAxis - u_time * speed);
  float band = smoothstep(0.0, 0.06, bandPos) * smoothstep(0.18, 0.10, bandPos);

  // --- Blue hue shift layer ---
  // Subtle noise distortion on the UV before hue lookup
  float noiseVal = valueNoise(aspectUV * 3.0 + vec2(u_time * 0.15, u_time * 0.1));
  float hue = 0.62 + noiseVal * 0.08;  // Blue range: 0.58–0.70
  float sat = 0.7 + u_hover * 0.2;
  float val = 0.5 + band * 0.4;
  vec3 hueColor = hsv2rgb(vec3(hue, sat, val));

  // --- Edge pulse ---
  // Glow along card edges, stronger on hover
  vec2 edge = min(uv, 1.0 - uv);
  float edgeDist = min(edge.x, edge.y);
  float edgePulse = 1.0 - smoothstep(0.0, 0.08, edgeDist);
  float pulseAnim = 0.5 + 0.5 * sin(u_time * 2.0 + uv.y * 4.0);
  vec3 edgeColor = vec3(0.3, 0.5, 1.0);  // Blue
  float edgeIntensity = edgePulse * pulseAnim * (0.3 + u_hover * 0.4);

  // --- Upgraded: slightly more intense, slight green tint on edge ---
  vec3 upgradeColor = mix(edgeColor, vec3(0.3, 1.0, 0.5), u_upgraded * 0.3);

  // --- Composite ---
  vec3 finalColor = mix(hueColor, upgradeColor, edgePulse * 0.4);
  float finalOpacity = (0.25 + u_hover * 0.25) * (band * 0.6 + edgeIntensity);

  // Vignette
  vec2 centered = uv - 0.5;
  float vignette = 1.0 - smoothstep(0.25, 0.5, length(centered));

  fragColor = vec4(finalColor, finalOpacity * vignette);
}
```

---

## Effect 3: Energy Pulse (rarity-colored radial)

Radial pulse from card center, color and intensity keyed to `u_rarity`. Used as an ambient idle effect, not dependent on hover.

```glsl
#version 300 es
precision highp float;

in vec2 v_uv;
out vec4 fragColor;

uniform float u_time;
uniform float u_rarity;
uniform float u_hover;
uniform vec2  u_resolution;

void main() {
  vec2 uv = v_uv;
  vec2 centered = uv - 0.5;

  // Aspect-correct distance for non-square cards (400x560)
  centered.y *= (400.0 / 560.0);
  float dist = length(centered);

  // Pulse ring emanates from center
  float pulseSpeed = 0.8 + u_rarity * 0.4;
  float pulse = fract(dist * 2.5 - u_time * pulseSpeed);
  float ring = smoothstep(0.0, 0.1, pulse) * smoothstep(0.3, 0.15, pulse);

  // Falloff: pulses fade as they move outward
  float falloff = 1.0 - smoothstep(0.0, 0.55, dist);

  // Rarity color: common=silver, uncommon=blue, rare=gold, legendary=rainbow
  vec3 rarityColor;
  if (u_rarity < 0.3) {
    rarityColor = vec3(0.6, 0.6, 0.7);  // Silver (uncommon)
  } else if (u_rarity < 0.6) {
    rarityColor = vec3(1.0, 0.72, 0.0);  // Gold (rare) — matches #FFB800
  } else {
    // Legendary: animate through rainbow
    float hue = fract(u_time * 0.15 + dist * 0.5);
    rarityColor = vec3(
      0.5 + 0.5 * cos(6.28318 * (hue + 0.0)),
      0.5 + 0.5 * cos(6.28318 * (hue + 0.333)),
      0.5 + 0.5 * cos(6.28318 * (hue + 0.667))
    );
  }

  float intensity = ring * falloff * (0.4 + u_hover * 0.3);
  fragColor = vec4(rarityColor, intensity);
}
```

---

## UV Coordinate Reference

The card aspect ratio is 400×560 (width × height). When computing effects that need to appear geometrically correct (circles, uniform bands):

```glsl
// Aspect correction: make UV space square for geometric effects
// Multiply y by (width/height) to normalize
vec2 aspectUV = vec2(v_uv.x, v_uv.y * (400.0 / 560.0));

// For distance calculations from center:
vec2 centered = v_uv - 0.5;
centered.y *= (400.0 / 560.0);  // Correct for aspect
float dist = length(centered);   // Now a circle, not an ellipse
```

---

## Anti-Patterns

**Allocating arrays or objects in the fragment shader loop**: GLSL `for` loops with dynamic bounds or large local arrays cause driver stalls. Use a fixed iteration count (e.g., `for (int i = 0; i < 5; i++)`) and use `break` only when the loop count is truly constant.

**Using `gl_FragCoord` for UV**: Derive UVs from `v_uv` (passed from vertex shader), not `gl_FragCoord / u_resolution`. The varyings are more stable and the math is cleaner.

**Sampling `u_time` directly at full speed**: `u_time` increments at 1.0 per second by default. For slow organic movement, multiply by 0.3–0.6. For pulse timing, use `fract()` to loop cleanly instead of `mod()`.

**Opacity above 0.75 for shimmer effects**: Effects above 0.75 opacity obscure the card art and text. Test with `mix-blend-mode: screen` — the effective visual opacity is lower than the alpha value suggests.

**Using WebGL1 (`gl.getContext('webgl')`)**: Always request `webgl2`. WebGL1 lacks `#version 300 es`, `out vec4` fragment outputs, and the `in`/`out` varying syntax. Feature-detect and fall back to CSS if WebGL2 is unavailable.

**Declaring unused uniforms**: GLSL compilers strip uniforms that are declared but never referenced. The JS side calling `gl.getUniformLocation()` on a stripped uniform returns `null`, causing a silent no-op. Either reference every uniform in shader code or remove unused declarations.
