---
name: Three.js Shader Patterns
description: Custom GLSL shaders in Three.js — ShaderMaterial, vertex displacement, fragment effects, and EffectComposer postprocessing pipeline
agent: threejs-builder
category: visual-techniques
version_range: "Three.js r150+"
---

# Shader Patterns Reference

> **Scope**: Writing custom GLSL for Three.js — ShaderMaterial vs RawShaderMaterial, vertex displacement, fragment effects, postprocessing with EffectComposer. Does NOT cover TSL/WebGPU node materials (see webgpu.md).
> **Version range**: Three.js r150+
> **Generated**: 2026-04-08

---

## ShaderMaterial vs RawShaderMaterial

| Class | Preprocessor Includes | Built-in Uniforms | Use When |
|-------|----------------------|-------------------|----------|
| `ShaderMaterial` | Yes — Three.js injects `#include <common>`, fog, lights | `projectionMatrix`, `modelViewMatrix`, `normalMatrix` auto-bound | Custom effects that still need Three.js lighting chunks |
| `RawShaderMaterial` | None — full GLSL control | Must declare ALL uniforms manually, including matrices | Full shader control, when Three.js chunks cause conflicts |

The most common mistake: using `RawShaderMaterial` and forgetting to declare `projectionMatrix` and `modelViewMatrix`, then wondering why geometry doesn't render.

```javascript
// ShaderMaterial — Three.js injects precision, matrices, and chunk definitions
const mat = new THREE.ShaderMaterial({
  uniforms: {
    uTime: { value: 0.0 },
    uColor: { value: new THREE.Color(0x00ffcc) },
  },
  vertexShader: /* glsl */`
    uniform float uTime;
    varying vec2 vUv;

    void main() {
      vUv = uv;
      // projectionMatrix and modelViewMatrix are injected by Three.js
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
  `,
  fragmentShader: /* glsl */`
    uniform vec3 uColor;
    varying vec2 vUv;

    void main() {
      gl_FragColor = vec4(uColor * vUv.x, 1.0);
    }
  `,
});

// In animation loop:
mat.uniforms.uTime.value = clock.getElapsedTime();
```

```javascript
// RawShaderMaterial — must declare ALL uniforms and precision
const mat = new THREE.RawShaderMaterial({
  uniforms: {
    uTime: { value: 0.0 },
  },
  vertexShader: /* glsl */`
    precision mediump float;

    uniform mat4 projectionMatrix;
    uniform mat4 modelViewMatrix;
    uniform float uTime;
    attribute vec3 position;
    attribute vec2 uv;
    varying vec2 vUv;

    void main() {
      vUv = uv;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
  `,
  fragmentShader: /* glsl */`
    precision mediump float;
    varying vec2 vUv;

    void main() {
      gl_FragColor = vec4(vUv, 0.5, 1.0);
    }
  `,
});
```

---

## Vertex Displacement Shaders

### Noise-Based Terrain

```javascript
// Simplex noise via glsl-noise (CDN) or inline implementation
// Three.js r150+ includes ShaderChunk — use #include <common> for noise utilities

const terrainMat = new THREE.ShaderMaterial({
  uniforms: {
    uTime: { value: 0 },
    uStrength: { value: 2.0 },
    uFrequency: { value: 0.5 },
  },
  vertexShader: /* glsl */`
    #include <common>  // includes noise utilities in Three.js r150+

    uniform float uTime;
    uniform float uStrength;
    uniform float uFrequency;
    varying float vElevation;

    // Classic Perlin noise — available after #include <common>
    void main() {
      vec4 modelPosition = modelMatrix * vec4(position, 1.0);

      float elevation =
        sin(modelPosition.x * uFrequency + uTime) *
        sin(modelPosition.z * uFrequency + uTime) *
        uStrength;

      modelPosition.y += elevation;
      vElevation = elevation;

      gl_Position = projectionMatrix * viewMatrix * modelPosition;
    }
  `,
  fragmentShader: /* glsl */`
    varying float vElevation;

    void main() {
      // Map elevation to color gradient
      float t = (vElevation + 2.0) / 4.0; // normalize to 0-1
      vec3 low  = vec3(0.04, 0.08, 0.2);  // deep water
      vec3 high = vec3(0.8, 0.95, 0.9);   // snow cap
      gl_FragColor = vec4(mix(low, high, t), 1.0);
    }
  `,
  side: THREE.DoubleSide,
  wireframe: false,
});
```

### Water Wave Displacement

```javascript
// Key pattern: multi-octave wave displacement with layered cnoise ripples
const waterMat = new THREE.ShaderMaterial({
  uniforms: {
    uTime: { value: 0 },
    uBigWavesElevation: { value: 0.2 },
    uBigWavesFrequency: { value: new THREE.Vector2(4, 1.5) },
    uSmallWavesElevation: { value: 0.15 },
    uDepthColor: { value: new THREE.Color('#186691') },
    uSurfaceColor: { value: new THREE.Color('#9bd8ff') },
  },
  vertexShader: /* glsl */`
    #include <common>
    uniform float uTime;
    uniform vec2 uBigWavesFrequency;
    uniform float uBigWavesElevation;
    uniform float uSmallWavesElevation;
    varying float vElevation;
    void main() {
      vec4 modelPosition = modelMatrix * vec4(position, 1.0);
      float elevation =
        sin(modelPosition.x * uBigWavesFrequency.x + uTime) *
        sin(modelPosition.z * uBigWavesFrequency.y + uTime) *
        uBigWavesElevation;
      // Layer 3 octaves of cnoise for organic ripples
      for(float i = 1.0; i <= 3.0; i++) {
        elevation -= abs(cnoise(vec3(modelPosition.xz * 3.0 * i, uTime * 0.2))) * uSmallWavesElevation / i;
      }
      modelPosition.y += elevation;
      vElevation = elevation;
      gl_Position = projectionMatrix * viewMatrix * modelPosition;
    }
  `,
  fragmentShader: /* glsl */`
    uniform vec3 uDepthColor;
    uniform vec3 uSurfaceColor;
    varying float vElevation;
    void main() {
      gl_FragColor = vec4(mix(uDepthColor, uSurfaceColor, (vElevation + 0.1) * 5.0), 1.0);
    }
  `,
});
```

---

## Fragment Shader Effects

### Holographic Effect

```javascript
const holoMat = new THREE.ShaderMaterial({
  uniforms: {
    uTime: { value: 0 },
    uColor: { value: new THREE.Color(0x70c5e8) },
  },
  transparent: true,
  side: THREE.DoubleSide,
  depthWrite: false,
  blending: THREE.AdditiveBlending,
  vertexShader: /* glsl */`
    varying vec2 vUv;
    varying float vNormal;
    void main() {
      vUv = uv;
      vec4 normalModelView = normalMatrix * vec4(normal, 0.0);
      // Fresnel-like rim lighting
      vNormal = abs(dot(normalize(normalModelView.xyz), vec3(0,0,1)));
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
  `,
  fragmentShader: /* glsl */`
    uniform float uTime;
    uniform vec3 uColor;
    varying vec2 vUv;
    varying float vNormal;

    void main() {
      // Horizontal scan lines
      float scanLine = step(0.5, fract(vUv.y * 50.0 - uTime * 0.5));
      // Rim glow (edges = bright)
      float rim = 1.0 - vNormal;
      float alpha = (scanLine * 0.1 + rim * 0.5) * 0.85;
      gl_FragColor = vec4(uColor, alpha);
    }
  `,
});
```

### Dissolve Shader

```javascript
const dissolveMat = new THREE.ShaderMaterial({
  uniforms: {
    uTime: { value: 0 },
    uProgress: { value: 0 },   // 0 = solid, 1 = fully dissolved
    uEdgeColor: { value: new THREE.Color(0xff6600) },
    uNoiseScale: { value: 3.0 },
  },
  transparent: true,
  side: THREE.DoubleSide,
  vertexShader: /* glsl */`
    varying vec2 vUv;
    void main() {
      vUv = uv;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
  `,
  fragmentShader: /* glsl */`
    #include <common>
    uniform float uProgress;
    uniform vec3 uEdgeColor;
    uniform float uNoiseScale;
    varying vec2 vUv;

    void main() {
      float noise = cnoise(vec3(vUv * uNoiseScale, 0.0)) * 0.5 + 0.5;
      float edge = 0.05; // edge band width

      if (noise < uProgress) discard; // dissolve away

      float edgeMix = smoothstep(uProgress, uProgress + edge, noise);
      vec3 color = mix(uEdgeColor, vec3(1.0), edgeMix);
      float alpha = step(uProgress + edge, noise) * 1.0 + (1.0 - edgeMix) * 0.8;

      gl_FragColor = vec4(color, alpha);
    }
  `,
});
```

### Chromatic Aberration (Postprocessing Shader)

```javascript
// Use as EffectComposer ShaderPass
const ChromaticAberrationShader = {
  uniforms: {
    tDiffuse: { value: null },
    uOffset: { value: new THREE.Vector2(0.003, 0.003) },
  },
  vertexShader: /* glsl */`
    varying vec2 vUv;
    void main() {
      vUv = uv;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
  `,
  fragmentShader: /* glsl */`
    uniform sampler2D tDiffuse;
    uniform vec2 uOffset;
    varying vec2 vUv;
    void main() {
      float r = texture2D(tDiffuse, vUv + uOffset).r;
      float g = texture2D(tDiffuse, vUv).g;
      float b = texture2D(tDiffuse, vUv - uOffset).b;
      gl_FragColor = vec4(r, g, b, 1.0);
    }
  `,
};
```

---

## Postprocessing Pipeline with EffectComposer

```javascript
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { SSAOPass } from 'three/addons/postprocessing/SSAOPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

const composer = new EffectComposer(renderer);

// 1. Base render pass — always first
composer.addPass(new RenderPass(scene, camera));

// 2. SSAO — ambient occlusion adds depth (r150+)
const ssaoPass = new SSAOPass(scene, camera, width, height);
ssaoPass.kernelRadius = 16;
ssaoPass.minDistance = 0.005;
ssaoPass.maxDistance = 0.1;
composer.addPass(ssaoPass);

// 3. Bloom — selective bloom via layers (r150+)
const bloomPass = new UnrealBloomPass(
  new THREE.Vector2(width, height),
  1.5,   // strength: 0-3, start at 1.5
  0.4,   // radius: 0-1
  0.85   // threshold: 0-1 (luminance required to bloom)
);
composer.addPass(bloomPass);

// 4. Custom shader passes
composer.addPass(new ShaderPass(ChromaticAberrationShader));

// 5. Output — color space correction (required in r150+, replaces GammaCorrectionShader)
composer.addPass(new OutputPass());

// In animation loop — use composer.render() instead of renderer.render()
renderer.setAnimationLoop((time) => {
  controls.update();
  composer.render();  // NOT renderer.render(scene, camera)
});

// Resize handler
window.addEventListener('resize', () => {
  composer.setSize(window.innerWidth, window.innerHeight);
  bloomPass.resolution.set(window.innerWidth, window.innerHeight);
});
```

---

## Uniform Patterns and Texture Sampling

### Passing Textures as Uniforms

```javascript
const textureLoader = new THREE.TextureLoader();
const texture = textureLoader.load('/textures/diffuse.jpg');

const mat = new THREE.ShaderMaterial({
  uniforms: {
    uTexture: { value: texture },       // sampler2D
    uTime: { value: 0 },                // float
    uResolution: { value: new THREE.Vector2(width, height) }, // vec2
    uMouse: { value: new THREE.Vector2() },  // vec2
  },
  fragmentShader: /* glsl */`
    uniform sampler2D uTexture;
    uniform float uTime;
    uniform vec2 uResolution;
    varying vec2 vUv;

    void main() {
      // Animated UV distortion using texture
      vec2 distortedUv = vUv + vec2(
        sin(vUv.y * 10.0 + uTime) * 0.02,
        cos(vUv.x * 10.0 + uTime) * 0.02
      );
      vec4 texColor = texture2D(uTexture, distortedUv);
      gl_FragColor = texColor;
    }
  `,
});
```

---

## Anti-Pattern Catalog

### ❌ Recreating ShaderMaterial in Animation Loop

**Detection**:
```bash
grep -rn "new THREE.ShaderMaterial" --include="*.js" --include="*.ts"
rg "new THREE\.ShaderMaterial" --type js
```

**What it looks like**:
```javascript
renderer.setAnimationLoop((time) => {
  // BAD: creates new material every frame — leaks GPU memory
  mesh.material = new THREE.ShaderMaterial({
    uniforms: { uTime: { value: time } },
    ...
  });
  renderer.render(scene, camera);
});
```

**Why wrong**: GPU memory leak. Each new `ShaderMaterial` allocates shader programs on the GPU. After 60 seconds at 60fps, you've allocated 3600 programs that are never freed.

**Fix**:
```javascript
// Create once, update uniform
const mat = new THREE.ShaderMaterial({ uniforms: { uTime: { value: 0 } }, ... });
mesh.material = mat;

renderer.setAnimationLoop((time) => {
  mat.uniforms.uTime.value = time * 0.001; // update, don't recreate
  renderer.render(scene, camera);
});
```

---

### ❌ Forgetting OutputPass (Washed-Out Colors in r150+)

**Detection**:
```bash
grep -rn "EffectComposer" --include="*.js" --include="*.ts" -l
rg "GammaCorrectionShader" --type js
```

**What it looks like**:
```javascript
// r150+ — GammaCorrectionShader is deprecated, OutputPass is required
import { GammaCorrectionShader } from 'three/addons/shaders/GammaCorrectionShader.js'; // deprecated r154+
```

**Why wrong**: In Three.js r150+, `renderer.outputColorSpace` defaults to `SRGBColorSpace`. Without `OutputPass` at the end of the composer chain, colors appear washed out or double-gamma-corrected.

**Fix**:
```javascript
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
composer.addPass(new OutputPass()); // always last pass
```

**Version note**: `OutputPass` introduced in r152. For r148-r151, use `ShaderPass(GammaCorrectionShader)` as last pass.

---

### ❌ Using ShaderChunk Injection Without Understanding Side Effects

**Detection**:
```bash
grep -rn "onBeforeCompile" --include="*.js" --include="*.ts"
rg "shader\.vertexShader\.replace" --type js
```

**What it looks like**:
```javascript
material.onBeforeCompile = (shader) => {
  shader.vertexShader = shader.vertexShader.replace(
    '#include <begin_vertex>',
    `vec3 transformed = position + vec3(sin(uTime), 0.0, 0.0);`
  );
};
```

**Why wrong**: `#include` tokens change between Three.js versions. Replacing `<begin_vertex>` in r155 may not match the chunk in r160. The material silently renders incorrectly with no error.

**Fix**: Use `ShaderMaterial` for custom vertex displacement instead of patching `onBeforeCompile`. Reserve `onBeforeCompile` only for lightweight additions to standard materials (fog, lights) where a custom `ShaderMaterial` would be too verbose.

---

## Error-Fix Mappings

| Error | Root Cause | Fix |
|-------|-----------|-----|
| `WebGL: INVALID_OPERATION: uniform not set` | Uniform declared in GLSL but not in `uniforms: {}` object | Add missing uniform key with initial value |
| `THREE.WebGLProgram: Shader error — 'cnoise' undefined` | Using `cnoise` without `#include <common>` in ShaderMaterial | Add `#include <common>` at top of vertex shader |
| Black screen with EffectComposer | Missing `OutputPass` or `GammaCorrectionShader` | Add `composer.addPass(new OutputPass())` as final pass |
| `Cannot read 'value' of undefined` | Accessing `mat.uniforms.uTime` before material created | Create material before animation loop, guard `if (!mat.uniforms)` |
| Bloom affecting UI elements | No bloom layer separation | Set emissive objects to `mesh.layers.enable(BLOOM_LAYER)`, use selective bloom technique |

---

## See Also

- `references/visual-polish.md` — HDR environments, PBR material recipes, lighting setups
- `references/webgpu.md` — TSL node materials for WebGPU renderer (different system)
- `references/performance-patterns.md` — InstancedMesh, BufferGeometry optimization