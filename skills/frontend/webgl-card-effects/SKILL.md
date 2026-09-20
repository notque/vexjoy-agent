---
name: webgl-card-effects
promoted_to: frontend
description: "Implement or debug pooled WebGL2 holographic/foil effects on React card grids, including rarity uniforms, context-loss handling, and CSS fallback."
agent: typescript-frontend-engineer
user-invocable: false
routing:
  triggers: [card effects, holographic, holographic card, foil effect, foil shader, card shimmer, card glow, shader card, WebGL card, card WebGL, rarity effects, rarity shader, Balatro effect, Balatro shader, card visual effects]
  not_for: "general Three.js scenes or ordinary CSS card styling"
  category: frontend
  pairs_with: [typescript-frontend-engineer, ui-design-engineer]
---

# WebGL Card Effects

Use this only when a real shader is warranted. Static cards and subtle sheen should remain CSS; one WebGL context per card is not an acceptable grid architecture.

## Local architecture

Read `references/runtime-contracts.md` before implementation. Its shared-context pool, uniform contract, React cleanup rules, and failure mappings are the durable requirements.

Load `references/balatro-shader-breakdown.md` only when the layered foil math or complete shader is needed. Simpler rarity effects should adapt that contract rather than load a second overlapping shader manual.

Implementation sequence:

1. Detect WebGL2. Choose CSS fallback immediately when absent or reduced-motion/performance policy requires it.
2. Reuse the shared renderer/context contract; allocate per-card state, not per-card contexts.
3. Map application rarity/state to bounded uniforms in code.
4. Update resolution from the canvas's drawing-buffer size and cap DPR.
5. Pause offscreen work and clean up observers, handlers, RAF ownership, GPU buffers, and pool registration on unmount.
6. Verify several cards together, resize, scroll/offscreen behavior, context loss, and fallback—not merely a single demo card.

Preserve the repository's existing component API. Shader aesthetics may change; resource ownership and fallback semantics may not.
