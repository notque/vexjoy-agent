# PixiJS v8 2D Normal Map Lighting Reference

> **Scope**: Custom GLSL ES 3.0 normal map filters, per-pixel lighting, light source uniforms, dynamic combat event reactions
> **Version range**: pixi.js ^8.5.0
> **Inspiration**: Slay the Spire 2 achieves depth on flat 2D sprites using per-sprite normal maps with 1-3 dynamic light sources

---

## What Normal Maps Do for 2D Sprites

A normal map is a texture that stores surface orientation data (x, y, z vectors encoded as RGB). When a fragment shader receives both the sprite color texture and the normal map texture, it can calculate how much light hits each pixel based on the light source direction — giving flat sprites the appearance of three-dimensional depth.

Without normal map: sprite appears flat, uniform brightness across the body.
With normal map + directional light: edges catch light, recessed areas darken, giving volume.

---

## Generating Normal Maps for 2D Sprites

Three tools suitable for wrestling sprite assets:

| Tool | Type | Best for |
|------|------|----------|
| [NormalMap-Online](https://cpetry.github.io/NormalMap-Online/) | Browser, free | Quick iteration, PNG sprites |
| [Laigter](https://azagaya.itch.io/laigter) | Desktop, free | Batch processing, animation sheets |
| [SpriteIlluminator](https://www.codeandweb.com/spriteilluminator) | Desktop, paid | Professional output, real-time preview |

For wrestling characters, use:
- **Strength**: 2.5–3.5 (strong lighting response)
- **Level**: 7–8 (how much height variation is implied)
- **Blur**: 1–2 (smoothing, avoids pixel artifacts)

Name convention: `player-normal.webp` alongside `player-diffuse.webp`. Store both in the same spritesheet directory.

---

## Custom Normal Map Filter (GLSL ES 3.0)

PixiJS v8 uses GLSL ES 3.0 — `in`/`out` instead of `varying`, `texture()` instead of `texture2D`.

```typescript
// src/combat/filters/NormalMapFilter.ts
import { Filter, GlProgram } from 'pixi.js';

const VERTEX_SRC = `
  #version 300 es
  in vec2 aPosition;
  out vec2 vTextureCoord;

  uniform vec4 uInputSize;
  uniform vec4 uOutputFrame;
  uniform vec4 uOutputTexture;

  vec4 filterVertexPosition(void) {
    vec2 position = aPosition * uOutputFrame.zw + uOutputFrame.xy;
    position.x = position.x * (2.0 / uOutputTexture.x) - 1.0;
    position.y = position.y * (2.0 / uOutputTexture.y) - 1.0;
    return vec4(position, 0.0, 1.0);
  }

  vec2 filterTextureCoord(void) {
    return aPosition * (uOutputFrame.zw * uInputSize.zw);
  }

  void main(void) {
    gl_Position = filterVertexPosition();
    vTextureCoord = filterTextureCoord();
  }
`;

const FRAGMENT_SRC = `
  #version 300 es
  precision mediump float;

  in vec2 vTextureCoord;
  out vec4 fragColor;

  uniform sampler2D uTexture;       // diffuse sprite texture (auto-provided by PixiJS)
  uniform sampler2D uNormalMap;     // normal map texture

  // Light uniforms — set dynamically from combat events
  uniform vec3 uLightPos;           // x, y in canvas coords (0-1 normalized), z is height (0.05-0.5)
  uniform vec3 uLightColor;         // RGB, each 0-1
  uniform float uLightIntensity;    // 0-2 range
  uniform float uAmbientLight;      // 0-0.5, prevents total darkness

  void main(void) {
    vec4 diffuse = texture(uTexture, vTextureCoord);

    // Early-out for transparent pixels
    if (diffuse.a < 0.01) {
      fragColor = diffuse;
      return;
    }

    // Sample normal map, remap from [0,1] to [-1,1]
    vec3 normal = texture(uNormalMap, vTextureCoord).rgb;
    normal = normalize(normal * 2.0 - 1.0);

    // Light direction from surface to light (normalized)
    vec3 lightDir = normalize(uLightPos - vec3(vTextureCoord, 0.0));

    // Lambertian diffuse lighting
    float diff = max(dot(normal, lightDir), 0.0);

    // Combine ambient + diffuse
    vec3 lighting = uAmbientLight + uLightColor * diff * uLightIntensity;

    fragColor = vec4(diffuse.rgb * lighting, diffuse.a);
  }
`;

export interface LightSource {
  x: number;       // 0-1 normalized canvas x position
  y: number;       // 0-1 normalized canvas y position
  z: number;       // height above plane, 0.05 (flat) to 0.5 (overhead)
  color: [number, number, number];  // RGB 0-1 each
  intensity: number;  // 0-2
}

export class NormalMapFilter extends Filter {
  private _normalTexture: unknown;

  constructor(normalMapTexture: unknown) {
    const glProgram = GlProgram.from({
      vertex: VERTEX_SRC,
      fragment: FRAGMENT_SRC,
    });

    super({
      glProgram,
      resources: {
        normalMapUniforms: {
          uNormalMap: { value: normalMapTexture, type: 'sampler2D' },
          uLightPos: { value: [0.5, 0.3, 0.2], type: 'vec3<f32>' },
          uLightColor: { value: [1.0, 0.95, 0.8], type: 'vec3<f32>' },
          uLightIntensity: { value: 1.0, type: 'f32' },
          uAmbientLight: { value: 0.25, type: 'f32' },
        },
      },
    });

    this._normalTexture = normalMapTexture;
  }

  set light(source: LightSource) {
    const uniforms = this.resources.normalMapUniforms.uniforms;
    uniforms.uLightPos = [source.x, source.y, source.z];
    uniforms.uLightColor = source.color;
    uniforms.uLightIntensity = source.intensity;
  }

  set ambientLight(value: number) {
    this.resources.normalMapUniforms.uniforms.uAmbientLight = value;
  }
}
```

---

## Applying the Filter to Combat Characters

Apply the filter to character containers, not to the root scene — keeps the effect isolated to characters:

```typescript
// src/combat/CombatScene.tsx
import { useEffect, useRef } from 'react';
import { useTick, useApp } from '@pixi/react';
import { Assets, Container, Texture } from 'pixi.js';
import { NormalMapFilter, LightSource } from './filters/NormalMapFilter';
import { useCombatStore } from '../stores/combatStore';

// Base scene light — warm overhead light, slight left offset
const BASE_LIGHT: LightSource = {
  x: 0.4,
  y: 0.2,
  z: 0.25,
  color: [1.0, 0.92, 0.78],  // warm tungsten
  intensity: 1.1,
};

export function PlayerSprite(): React.JSX.Element {
  const containerRef = useRef<Container>(null);
  const filterRef = useRef<NormalMapFilter | null>(null);
  const app = useApp();

  useEffect(() => {
    if (!containerRef.current) return;

    // Load normal map alongside diffuse sprite
    Assets.load('/sprites/player-normal.webp').then((normalTexture: Texture) => {
      const filter = new NormalMapFilter(normalTexture);
      filter.resolution = app.renderer.resolution;
      filter.light = BASE_LIGHT;
      filter.ambientLight = 0.25;

      if (containerRef.current) {
        containerRef.current.filters = [filter];
        filterRef.current = filter;
      }
    });

    return () => {
      // Cleanup on unmount
      if (containerRef.current) containerRef.current.filters = [];
    };
  }, [app.renderer.resolution]);

  // Subscribe to combat events — react with light changes
  useEffect(() => {
    return useCombatStore.subscribe(
      (state) => state.lastEffectType,
      (effectType) => {
        if (!filterRef.current || !effectType) return;
        reactLightToEffect(filterRef.current, effectType);
      }
    );
  }, []);

  return (
    <container ref={containerRef}>
      <sprite texture={playerTexture} anchor={{ x: 0.5, y: 1 }} />
    </container>
  );
}
```

---

## Dynamic Light Reactions to Combat Events

Light reacts to game events to reinforce feedback. These are spring-animated light shifts, not instant jumps:

```typescript
// src/combat/filters/lightReactions.ts
import { NormalMapFilter, LightSource } from './NormalMapFilter';

type EffectType = 'strike' | 'aerial' | 'submission' | 'block' | 'finisher' | 'heal';

interface LightAnimation {
  targetLight: LightSource;
  duration: number;   // ms
  returnAfter: number; // ms before returning to base
}

const BASE_LIGHT: LightSource = {
  x: 0.4, y: 0.2, z: 0.25,
  color: [1.0, 0.92, 0.78],
  intensity: 1.1,
};

const LIGHT_REACTIONS: Record<EffectType, LightAnimation> = {
  strike: {
    targetLight: { x: 0.9, y: 0.5, z: 0.1, color: [1.0, 0.5, 0.1], intensity: 2.0 },
    duration: 80,
    returnAfter: 300,
  },
  aerial: {
    targetLight: { x: 0.5, y: 0.05, z: 0.4, color: [0.8, 0.9, 1.0], intensity: 1.5 },
    duration: 150,
    returnAfter: 500,
  },
  submission: {
    targetLight: { x: 0.3, y: 0.6, z: 0.15, color: [0.2, 0.6, 1.0], intensity: 1.3 },
    duration: 200,
    returnAfter: 2000, // persistent while submission is active
  },
  block: {
    targetLight: { x: 0.5, y: 0.4, z: 0.1, color: [0.5, 0.8, 1.0], intensity: 1.8 },
    duration: 60,
    returnAfter: 200,
  },
  finisher: {
    targetLight: { x: 0.5, y: 0.5, z: 0.05, color: [1.0, 0.85, 0.0], intensity: 2.0 },
    duration: 300,
    returnAfter: 1500,
  },
  heal: {
    targetLight: { x: 0.5, y: 0.1, z: 0.3, color: [0.3, 1.0, 0.4], intensity: 1.2 },
    duration: 400,
    returnAfter: 800,
  },
};

export function reactLightToEffect(filter: NormalMapFilter, effectType: string): void {
  const reaction = LIGHT_REACTIONS[effectType as EffectType];
  if (!reaction) return;

  // Snap to effect light
  filter.light = reaction.targetLight;

  // Return to base after the reaction window
  setTimeout(() => {
    filter.light = BASE_LIGHT;
  }, reaction.returnAfter);
}
```

---

## Performance Considerations

Normal map filtering is GPU fillrate-bound. Each pixel in the sprite container is processed by the fragment shader.

| Scenario | Cost |
|----------|------|
| Player sprite (400x400) | Low — ~160K pixels |
| Enemy sprite (900px tall) | Medium — up to ~500K pixels |
| Full-screen normal map | Prohibitive — avoid entirely |
| Background normal map | Not recommended — low visual payoff, high cost |

Mobile rule: disable normal map filters entirely on mobile. The GPU fillrate difference between desktop and mobile is 4-8x.

```typescript
const isMobile = /iPhone|iPad|Android/i.test(navigator.userAgent);

if (!isMobile) {
  container.filters = [normalMapFilter];
}
```

Multiple light sources: the shader above handles one light. For two lights (e.g., scene light + finisher flash), add a second `uLight2` uniform block and sum the lighting contributions. Do not add more than two lights on desktop or one on mobile.

---

## Anti-Patterns

### ❌ Applying normal map to the root scene container
Filters applied to the root container process every pixel in the entire canvas at every frame — including the background, UI chrome, and all sprites simultaneously. Apply filters to character containers only.

### ❌ Using GLSL ES 1.0 syntax in v8
PixiJS v8 requires GLSL ES 3.0. `varying` → `in`/`out`, `texture2D()` → `texture()`, `gl_FragColor` → custom `out vec4 fragColor`. The v8 renderer will silently fail to compile v1.0 shaders.

### ❌ Not setting filter.resolution on retina displays
A filter created without setting `resolution = window.devicePixelRatio` will render at 1x on retina displays, appearing blurry. Always set resolution from `app.renderer.resolution` after the application initializes.

### ❌ Creating a new NormalMapFilter on every render
Filter creation compiles a shader program on the GPU — expensive. Create the filter once in `useEffect`, store it in `useRef`, and update uniforms each frame rather than recreating the filter.
