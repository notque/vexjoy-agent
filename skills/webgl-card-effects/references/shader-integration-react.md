# Shader Integration in React 19

Mounting standalone WebGL2 fragment shaders on React card components without Three.js. Covers the shared context singleton pattern, the `useCardShader` hook, visibility gating with IntersectionObserver, and the mobile CSS fallback.

---

## The Context Limit Problem

Browsers cap WebGL contexts at 8–16 per page. A hand of 8 cards each creating their own WebGL2 context hits this limit immediately. The solution is a single shared WebGL2 rendering context that draws to an offscreen buffer, then blits the result to each card's 2D canvas.

**Architecture:**

```
WebGL2 singleton (1 context total)
  ├── Renders to shared offscreen texture
  ├── Card A: HTMLCanvasElement (2D context) ← receives blit
  ├── Card B: HTMLCanvasElement (2D context) ← receives blit
  └── Card C: HTMLCanvasElement (2D context) ← receives blit
```

Each card has a `<canvas>` element with a `2D` rendering context. The singleton WebGL2 context renders the shader, then `drawImage` copies the rendered frame to each card's 2D canvas. This uses only 1 WebGL2 context total regardless of how many cards are on screen.

---

## WebGL2 Feature Detection

Always check before attempting WebGL2. Fall back to CSS — do not throw or log errors that flood the console.

```typescript
// src/components/cards/effects/webglSupport.ts

let _supportsWebGL2: boolean | null = null;

export function supportsWebGL2(): boolean {
  if (_supportsWebGL2 !== null) return _supportsWebGL2;

  try {
    const canvas = document.createElement('canvas');
    _supportsWebGL2 = !!canvas.getContext('webgl2');
  } catch {
    _supportsWebGL2 = false;
  }

  return _supportsWebGL2;
}
```

---

## Shared WebGL2 Context Singleton

```typescript
// src/components/cards/effects/webglContext.ts

import type { RefObject } from 'react';

interface CardShaderEntry {
  canvasRef: RefObject<HTMLCanvasElement | null>;
  rarity: string;
  isHovered: boolean;
  isUpgraded: boolean;
  isVisible: boolean;
  mouseX: number;
  mouseY: number;
}

interface ShaderProgram {
  program: WebGLProgram;
  locations: {
    u_time: WebGLUniformLocation | null;
    u_rarity: WebGLUniformLocation | null;
    u_hover: WebGLUniformLocation | null;
    u_mouse: WebGLUniformLocation | null;
    u_resolution: WebGLUniformLocation | null;
    u_upgraded: WebGLUniformLocation | null;
  };
}

// Singleton state — module-level, lives for the page lifetime
let gl: WebGL2RenderingContext | null = null;
let offscreenCanvas: HTMLCanvasElement | null = null;
let shimmerProgram: ShaderProgram | null = null;
let rareProgram: ShaderProgram | null = null;
let legendaryProgram: ShaderProgram | null = null;
let quadVAO: WebGLVertexArrayObject | null = null;
let rafId: number | null = null;
let startTime: number | null = null;
let hoverValues = new Map<string, number>(); // cardId → current lerped hover value

const registeredCards = new Map<string, CardShaderEntry>();

// --- Shader source imports ---
// Import from cardShaders.ts (see below for sources)
import { VERTEX_SHADER, SHIMMER_FRAG, RARE_FRAG, LEGENDARY_FRAG } from './cardShaders';

function compileShader(
  gl: WebGL2RenderingContext,
  source: string,
  type: number
): WebGLShader {
  const shader = gl.createShader(type);
  if (!shader) throw new Error('Failed to create shader');

  gl.shaderSource(shader, source);
  gl.compileShader(shader);

  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    const log = gl.getShaderInfoLog(shader);
    gl.deleteShader(shader);
    throw new Error(`Shader compile error: ${log ?? 'unknown'}`);
  }

  return shader;
}

function createProgram(
  gl: WebGL2RenderingContext,
  vertSrc: string,
  fragSrc: string
): ShaderProgram {
  const vert = compileShader(gl, vertSrc, gl.VERTEX_SHADER);
  const frag = compileShader(gl, fragSrc, gl.FRAGMENT_SHADER);

  const program = gl.createProgram();
  if (!program) throw new Error('Failed to create program');

  gl.attachShader(program, vert);
  gl.attachShader(program, frag);
  gl.linkProgram(program);

  gl.deleteShader(vert);
  gl.deleteShader(frag);

  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    const log = gl.getProgramInfoLog(program);
    gl.deleteProgram(program);
    throw new Error(`Program link error: ${log ?? 'unknown'}`);
  }

  return {
    program,
    locations: {
      u_time: gl.getUniformLocation(program, 'u_time'),
      u_rarity: gl.getUniformLocation(program, 'u_rarity'),
      u_hover: gl.getUniformLocation(program, 'u_hover'),
      u_mouse: gl.getUniformLocation(program, 'u_mouse'),
      u_resolution: gl.getUniformLocation(program, 'u_resolution'),
      u_upgraded: gl.getUniformLocation(program, 'u_upgraded'),
    },
  };
}

function initSingleton(): boolean {
  if (gl !== null) return true; // Already initialized

  try {
    offscreenCanvas = document.createElement('canvas');
    offscreenCanvas.width = 400;
    offscreenCanvas.height = 560;

    const ctx = offscreenCanvas.getContext('webgl2');
    if (!ctx) return false;
    gl = ctx;

    // Compile all three shader programs upfront
    shimmerProgram = createProgram(gl, VERTEX_SHADER, SHIMMER_FRAG);
    rareProgram = createProgram(gl, VERTEX_SHADER, RARE_FRAG);
    legendaryProgram = createProgram(gl, VERTEX_SHADER, LEGENDARY_FRAG);

    // Create quad VAO
    quadVAO = gl.createVertexArray();
    gl.bindVertexArray(quadVAO);

    const vbo = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, vbo);
    gl.bufferData(
      gl.ARRAY_BUFFER,
      new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]),
      gl.STATIC_DRAW
    );

    // a_position is always location 0 — bind it once
    gl.enableVertexAttribArray(0);
    gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    gl.bindVertexArray(null);

    // Enable blending for screen blend mode
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

    startRenderLoop();
    return true;
  } catch (err) {
    console.warn('[webgl-card-effects] WebGL2 init failed:', err);
    gl = null;
    return false;
  }
}

function rarityToUniform(rarity: string): number {
  const map: Record<string, number> = {
    starter: 0.0,
    common: 0.0,
    uncommon: 0.25,
    rare: 0.5,
    legendary: 1.0,
  };
  return map[rarity] ?? 0.0;
}

function selectProgram(rarity: string): ShaderProgram | null {
  if (rarity === 'legendary') return legendaryProgram;
  if (rarity === 'rare') return rareProgram;
  if (rarity === 'uncommon') return shimmerProgram;
  return null;
}

function renderFrame(timestamp: number): void {
  if (!gl || !offscreenCanvas || !quadVAO) return;

  const elapsed = startTime === null ? 0 : (timestamp - startTime) / 1000;
  // Wrap at 1000 seconds to avoid float precision loss in the shader
  const u_time = elapsed % 1000.0;

  let anyVisible = false;

  for (const [cardId, entry] of registeredCards) {
    if (!entry.isVisible) continue;
    anyVisible = true;

    const program = selectProgram(entry.rarity);
    if (!program) continue;

    const canvas = entry.canvasRef.current;
    if (!canvas) continue;

    const ctx2d = canvas.getContext('2d');
    if (!ctx2d) continue;

    const w = canvas.width || canvas.clientWidth;
    const h = canvas.height || canvas.clientHeight;

    // Resize offscreen canvas to match card canvas if needed
    if (offscreenCanvas.width !== w || offscreenCanvas.height !== h) {
      offscreenCanvas.width = w;
      offscreenCanvas.height = h;
    }

    // Lerp hover value toward target
    const targetHover = entry.isHovered ? 1.0 : 0.0;
    const currentHover = hoverValues.get(cardId) ?? 0.0;
    const lerpedHover = currentHover + (targetHover - currentHover) * 0.12;
    hoverValues.set(cardId, lerpedHover);

    // Render
    gl.viewport(0, 0, w, h);
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);

    gl.useProgram(program.program);
    gl.bindVertexArray(quadVAO);

    const loc = program.locations;
    gl.uniform1f(loc.u_time, u_time);
    gl.uniform1f(loc.u_rarity, rarityToUniform(entry.rarity));
    gl.uniform1f(loc.u_hover, lerpedHover);
    gl.uniform2f(loc.u_mouse, entry.mouseX, entry.mouseY);
    gl.uniform2f(loc.u_resolution, w, h);
    gl.uniform1f(loc.u_upgraded, entry.isUpgraded ? 1.0 : 0.0);

    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    gl.bindVertexArray(null);

    // Blit offscreen WebGL result to the card's 2D canvas
    ctx2d.clearRect(0, 0, w, h);
    ctx2d.drawImage(offscreenCanvas, 0, 0, w, h);
  }

  // If nothing is visible, slow down RAF to save power
  if (!anyVisible) {
    rafId = requestAnimationFrame(renderFrame);
    return;
  }

  rafId = requestAnimationFrame(renderFrame);
}

// 30fps throttle — card shimmer does not need 60fps
let _lastRenderTime = 0;
const TARGET_FRAME_MS = 1000 / 30;

function renderFrameThrottled(timestamp: number): void {
  if (startTime === null) startTime = timestamp;

  if (timestamp - _lastRenderTime >= TARGET_FRAME_MS) {
    _lastRenderTime = timestamp;
    renderFrame(timestamp);
  } else {
    rafId = requestAnimationFrame(renderFrameThrottled);
  }
}

function startRenderLoop(): void {
  if (rafId !== null) return;
  rafId = requestAnimationFrame(renderFrameThrottled);
}

// --- Public API ---

export function registerCard(cardId: string, entry: CardShaderEntry): boolean {
  if (!initSingleton()) return false;
  registeredCards.set(cardId, entry);
  hoverValues.set(cardId, 0.0);
  return true;
}

export function updateCard(
  cardId: string,
  updates: Partial<Omit<CardShaderEntry, 'canvasRef'>>
): void {
  const existing = registeredCards.get(cardId);
  if (!existing) return;
  registeredCards.set(cardId, { ...existing, ...updates });
}

export function unregisterCard(cardId: string): void {
  registeredCards.delete(cardId);
  hoverValues.delete(cardId);

  // Stop RAF if no cards remain
  if (registeredCards.size === 0 && rafId !== null) {
    cancelAnimationFrame(rafId);
    rafId = null;
  }
}
```

---

## useCardShader Hook

```typescript
// src/components/cards/effects/useCardShader.ts

import { useEffect, useRef, useId } from 'react';
import type { RefObject } from 'react';
import { supportsWebGL2 } from './webglSupport';
import { registerCard, updateCard, unregisterCard } from './webglContext';

interface UseCardShaderOptions {
  rarity: string;
  isHovered: boolean;
  isUpgraded: boolean;
  enabled: boolean;
}

export function useCardShader(
  options: UseCardShaderOptions
): RefObject<HTMLCanvasElement | null> {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  // useId provides a stable unique ID per component instance
  const cardId = useId();
  const observerRef = useRef<IntersectionObserver | null>(null);
  const isRegisteredRef = useRef(false);

  const { rarity, isHovered, isUpgraded, enabled } = options;

  // Registration effect: runs once on mount, cleans up on unmount
  useEffect(() => {
    if (!enabled || !supportsWebGL2()) return;

    const canvas = canvasRef.current;
    if (!canvas) return;

    // Size the canvas to match its CSS-rendered dimensions
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(rect.width * dpr);
    canvas.height = Math.round(rect.height * dpr);

    const registered = registerCard(cardId, {
      canvasRef,
      rarity,
      isHovered,
      isUpgraded,
      isVisible: false,
      mouseX: 0.5,
      mouseY: 0.5,
    });

    if (!registered) return;
    isRegisteredRef.current = true;

    // IntersectionObserver: only animate when card is in viewport
    observerRef.current = new IntersectionObserver(
      (entries) => {
        const isVisible = entries[0]?.isIntersecting ?? false;
        updateCard(cardId, { isVisible });
      },
      { threshold: 0.1 }
    );
    observerRef.current.observe(canvas);

    // ResizeObserver: keep canvas pixel dimensions in sync with CSS
    const resizeObserver = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      const dpr = window.devicePixelRatio || 1;
      const w = Math.round(entry.contentRect.width * dpr);
      const h = Math.round(entry.contentRect.height * dpr);
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w;
        canvas.height = h;
      }
    });
    resizeObserver.observe(canvas);

    return () => {
      observerRef.current?.disconnect();
      resizeObserver.disconnect();
      if (isRegisteredRef.current) {
        unregisterCard(cardId);
        isRegisteredRef.current = false;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, cardId]); // Only re-register if enabled or ID changes

  // Update effect: syncs reactive state to the singleton each render
  useEffect(() => {
    if (!isRegisteredRef.current) return;
    updateCard(cardId, { rarity, isHovered, isUpgraded });
  }, [cardId, rarity, isHovered, isUpgraded]);

  // Mouse tracking effect
  useEffect(() => {
    if (!enabled || !isRegisteredRef.current) return;

    const canvas = canvasRef.current;
    if (!canvas) return;

    function handleMouseMove(e: MouseEvent): void {
      const rect = canvas!.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width;
      const y = 1.0 - (e.clientY - rect.top) / rect.height; // Flip Y for GL coords
      updateCard(cardId, { mouseX: x, mouseY: y });
    }

    function handleMouseLeave(): void {
      updateCard(cardId, { mouseX: 0.5, mouseY: 0.5 });
    }

    // Walk up to the card container (canvas is a child of the card div)
    const cardContainer = canvas.closest('[data-card-container]') ?? canvas.parentElement;
    if (!cardContainer) return;

    cardContainer.addEventListener('mousemove', handleMouseMove as EventListener);
    cardContainer.addEventListener('mouseleave', handleMouseLeave);

    return () => {
      cardContainer.removeEventListener('mousemove', handleMouseMove as EventListener);
      cardContainer.removeEventListener('mouseleave', handleMouseLeave);
    };
  }, [enabled, cardId]);

  return canvasRef;
}
```

---

## Integrating Mouse Tracking in FramedCard

Add `data-card-container` to the `motion.div` in `FramedCard.tsx` so `useCardShader` can locate the event target:

```tsx
<motion.div
  ref={cardRef}
  data-card-container
  // ... existing props
>
```

The hook's mouse listener walks up the DOM to find this attribute. This keeps the hook self-contained and avoids prop drilling mouse coordinates.

---

## Rarity-to-Uniform Mapping

```typescript
// src/components/cards/effects/cardShaders.ts (mapping export)

export type CardRarity = 'starter' | 'common' | 'uncommon' | 'rare' | 'legendary';

export function rarityToFloat(rarity: CardRarity | string): number {
  const map: Record<string, number> = {
    starter:  0.0,
    common:   0.0,
    uncommon: 0.25,
    rare:     0.5,
    legendary: 1.0,
  };
  return map[rarity] ?? 0.0;
}

// Which shader tier to use per rarity
export function shouldUseShader(rarity: string, size: string): boolean {
  if (size === 'xs' || size === 'sm') return false;
  return ['uncommon', 'rare', 'legendary'].includes(rarity);
}
```

---

## CSS Fallback

When WebGL2 is unavailable, the `<canvas>` element is not rendered (because `shouldRenderShader` is false). The existing CSS shimmer class from `FramedCard.tsx` handles the fallback automatically — no extra code needed.

To test the fallback path locally, temporarily override `supportsWebGL2` to return false:

```typescript
// For testing only — remove before committing
import { supportsWebGL2 } from './webglSupport';
// @ts-expect-error: test override
supportsWebGL2._override = false;
```

---

## Anti-Patterns

**Creating a new WebGL2 context per card instance**: Browsers cap at 8–16 total contexts. With a hand of 8+ cards, you will hit this limit. The singleton pattern above is non-negotiable.

**Running RAF at 60fps for card shimmer**: Card shimmer doesn't need 60fps. The 30fps throttle (`TARGET_FRAME_MS = 1000 / 30`) halves GPU load with no perceptible quality difference for a slow organic shimmer.

**Skipping IntersectionObserver**: Cards not in the viewport still consume RAF budget without the observer. For a game with a large card collection view, this wastes significant CPU/GPU.

**Forgetting canvas `width`/`height` vs CSS size**: CSS `w-full h-full` sets display size. `canvas.width` and `canvas.height` set the drawing buffer. On a 2x DPI display, a CSS `200px` canvas with `canvas.width = 200` renders blurry. Always multiply by `devicePixelRatio`.

**Using `getContext('webgl')` (WebGL1)**: The GLSL shaders in this skill use `#version 300 es` which requires WebGL2. WebGL1 contexts will fail to compile these shaders. Always call `getContext('webgl2')`.

**Not cleaning up on unmount**: If `unregisterCard` isn't called in the cleanup function, the singleton continues rendering to a destroyed canvas. The `RefObject` will still hold a reference preventing GC, but `drawImage` will fail silently.
