# PixiJS v8 2D Normal Map Lighting Reference

> **Scope**: Custom GLSL ES 3.0 normal map filters, per-pixel lighting, dynamic combat event reactions
> **Version range**: pixi.js ^8.5.0

---

## What Normal Maps Do

A normal map stores surface orientation as RGB. The fragment shader calculates light per pixel, giving flat sprites depth. Inspiration: Slay the Spire 2 achieves this with per-sprite normal maps + 1-3 dynamic lights.

---

## Generating Normal Maps

| Tool | Type | Best for |
|------|------|----------|
| [NormalMap-Online](https://cpetry.github.io/NormalMap-Online/) | Browser, free | Quick iteration |
| [Laigter](https://azagaya.itch.io/laigter) | Desktop, free | Batch processing |
| [SpriteIlluminator](https://www.codeandweb.com/spriteilluminator) | Desktop, paid | Professional output |

Wrestling character settings: Strength 2.5-3.5, Level 7-8, Blur 1-2.
Naming: `player-normal.webp` alongside `player-diffuse.webp`.

---

## Custom Normal Map Filter (GLSL ES 3.0)

PixiJS v8 uses GLSL ES 3.0: `in`/`out` not `varying`, `texture()` not `texture2D`.

```typescript
import { Filter, GlProgram } from 'pixi.js';

const VERTEX_SRC = `
  #version 300 es
  in vec2 aPosition;
  out vec2 vTextureCoord;
  uniform vec4 uInputSize;
  uniform vec4 uOutputFrame;
  uniform vec4 uOutputTexture;

  void main(void) {
    vec2 position = aPosition * uOutputFrame.zw + uOutputFrame.xy;
    position.x = position.x * (2.0 / uOutputTexture.x) - 1.0;
    position.y = position.y * (2.0 / uOutputTexture.y) - 1.0;
    gl_Position = vec4(position, 0.0, 1.0);
    vTextureCoord = aPosition * (uOutputFrame.zw * uInputSize.zw);
  }
`;

const FRAGMENT_SRC = `
  #version 300 es
  precision mediump float;
  in vec2 vTextureCoord;
  out vec4 fragColor;
  uniform sampler2D uTexture;
  uniform sampler2D uNormalMap;
  uniform vec3 uLightPos;        // x,y normalized 0-1, z height 0.05-0.5
  uniform vec3 uLightColor;      // RGB 0-1
  uniform float uLightIntensity; // 0-2
  uniform float uAmbientLight;   // 0-0.5

  void main(void) {
    vec4 diffuse = texture(uTexture, vTextureCoord);
    if (diffuse.a < 0.01) { fragColor = diffuse; return; }
    vec3 normal = normalize(texture(uNormalMap, vTextureCoord).rgb * 2.0 - 1.0);
    vec3 lightDir = normalize(uLightPos - vec3(vTextureCoord, 0.0));
    float diff = max(dot(normal, lightDir), 0.0);
    vec3 lighting = uAmbientLight + uLightColor * diff * uLightIntensity;
    fragColor = vec4(diffuse.rgb * lighting, diffuse.a);
  }
`;

export interface LightSource {
  x: number; y: number; z: number;
  color: [number, number, number];
  intensity: number;
}

export class NormalMapFilter extends Filter {
  constructor(normalMapTexture: unknown) {
    super({
      glProgram: GlProgram.from({ vertex: VERTEX_SRC, fragment: FRAGMENT_SRC }),
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
  }

  set light(source: LightSource) {
    const u = this.resources.normalMapUniforms.uniforms;
    u.uLightPos = [source.x, source.y, source.z];
    u.uLightColor = source.color;
    u.uLightIntensity = source.intensity;
  }
  set ambientLight(value: number) { this.resources.normalMapUniforms.uniforms.uAmbientLight = value; }
}
```

---

## Applying to Combat Characters

Apply to character containers, not root scene.

```typescript
const BASE_LIGHT: LightSource = { x: 0.4, y: 0.2, z: 0.25, color: [1.0, 0.92, 0.78], intensity: 1.1 };

export function PlayerSprite(): React.JSX.Element {
  const containerRef = useRef<Container>(null);
  const filterRef = useRef<NormalMapFilter | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    Assets.load('/sprites/player-normal.webp').then((normalTexture: Texture) => {
      const filter = new NormalMapFilter(normalTexture);
      filter.resolution = app.renderer.resolution;
      filter.light = BASE_LIGHT;
      if (containerRef.current) { containerRef.current.filters = [filter]; filterRef.current = filter; }
    });
    return () => { if (containerRef.current) containerRef.current.filters = []; };
  }, [app.renderer.resolution]);

  useEffect(() => {
    return useCombatStore.subscribe(
      (state) => state.lastEffectType,
      (effectType) => { if (filterRef.current && effectType) reactLightToEffect(filterRef.current, effectType); }
    );
  }, []);

  return <container ref={containerRef}><sprite texture={playerTexture} anchor={{ x: 0.5, y: 1 }} /></container>;
}
```

---

## Dynamic Light Reactions

```typescript
const LIGHT_REACTIONS: Record<EffectType, LightAnimation> = {
  strike:     { targetLight: { x: 0.9, y: 0.5, z: 0.1, color: [1.0, 0.5, 0.1], intensity: 2.0 }, duration: 80, returnAfter: 300 },
  aerial:     { targetLight: { x: 0.5, y: 0.05, z: 0.4, color: [0.8, 0.9, 1.0], intensity: 1.5 }, duration: 150, returnAfter: 500 },
  submission: { targetLight: { x: 0.3, y: 0.6, z: 0.15, color: [0.2, 0.6, 1.0], intensity: 1.3 }, duration: 200, returnAfter: 2000 },
  block:      { targetLight: { x: 0.5, y: 0.4, z: 0.1, color: [0.5, 0.8, 1.0], intensity: 1.8 }, duration: 60, returnAfter: 200 },
  finisher:   { targetLight: { x: 0.5, y: 0.5, z: 0.05, color: [1.0, 0.85, 0.0], intensity: 2.0 }, duration: 300, returnAfter: 1500 },
  heal:       { targetLight: { x: 0.5, y: 0.1, z: 0.3, color: [0.3, 1.0, 0.4], intensity: 1.2 }, duration: 400, returnAfter: 800 },
};

export function reactLightToEffect(filter: NormalMapFilter, effectType: string): void {
  const reaction = LIGHT_REACTIONS[effectType as EffectType];
  if (!reaction) return;
  filter.light = reaction.targetLight;
  setTimeout(() => { filter.light = BASE_LIGHT; }, reaction.returnAfter);
}
```

---

## Performance

| Scenario | Cost |
|----------|------|
| Player sprite (400x400) | Low — ~160K pixels |
| Enemy sprite (900px) | Medium — ~500K pixels |
| Full-screen / background | Prohibitive — avoid |

Mobile: disable normal map filters entirely (4-8x GPU fillrate gap).
Max 2 lights desktop, 1 mobile.

---

## Patterns to Fix

- **Apply to character containers only** — root container processes every pixel including background.
- **Use GLSL ES 3.0 in v8** — `varying` → `in`/`out`, `texture2D` → `texture`, `gl_FragColor` → `out vec4`.
- **Set filter.resolution on retina** — without it, renders at 1x, appears blurry.
- **Create NormalMapFilter once, reuse** — shader compilation is expensive. Store in useRef, update uniforms.
