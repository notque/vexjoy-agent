# Rive vs Spine2D Decision Reference
<!-- Loaded by rive-skeletal-animator when task involves: choosing between Rive and Spine2D, comparing animation runtimes, bundle size tradeoffs, editor cost comparison, React integration comparison -->

For React web games (Road to AEW): use Rive. Below is why, and when Spine2D is better.

## Decision Matrix

| Criterion | Rive | Spine2D | Winner |
|-----------|------|---------|--------|
| React runtime | First-class (`@rive-app/react-canvas`, hooks) | Manual integration required | **Rive** |
| Editor cost | Free (web-based at rive.app) | $69 Essential / $299 Professional | **Rive** |
| Editor access | Browser-based, no install | Desktop app (Windows/macOS) | **Rive** |
| File format | Single `.riv` | `.skel` + `.atlas` + `.png` (3+ files) | **Rive** |
| Runtime bundle | ~150KB WASM (includes renderer) | ~80KB JS + atlas textures (varies) | Spine has smaller JS, but textures add up |
| State machines | Built into Editor UI | Code-based (no visual editor) | **Rive** |
| Game engine integration | Limited (web/React first) | Excellent (Unity, Unreal, Godot, Cocos2d) | **Spine** |
| Community & tutorials | Growing fast (2023+) | Mature, large (10+ years) | Spine |
| Animation quality ceiling | Very high | Industry standard | Tie |
| Version control | Single `.riv` file, binary | Multiple files, binary | **Rive** (simpler) |

**Verdict for web/React**: Rive wins on runtime integration, editor access, and file management. Spine2D's advantages (game engine ecosystems, community maturity) don't apply to React web games.

## Runtime Integration Comparison

### Rive in React

```tsx
import { useRive } from '@rive-app/react-canvas';

const { RiveComponent } = useRive({
  src: '/characters/player.riv',
  stateMachines: 'CombatStateMachine',
  autoplay: true,
});

return <div style={{ width: 400, height: 400 }}><RiveComponent /></div>;
```

First-party hooks handle canvas lifecycle, WASM loading, resize, cleanup.

### Spine2D in React

No first-party React package. Integration requires:

1. Install `@esotericsoftware/spine-webgl` or `@esotericsoftware/spine-canvas`
2. Create a canvas element manually with `useRef`
3. Load `.skel` + `.atlas` + texture files separately
4. Build the WebGL/Canvas rendering loop imperatively
5. Manage resize observers manually
6. Handle animation state machine changes via the Spine `AnimationState` API directly

```tsx
function SpineCharacter() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!canvasRef.current) return;

    const canvas = canvasRef.current;
    const gl = canvas.getContext('webgl2');
    // ... load atlas, load skeleton data, create SkeletonRenderer
    // ... set up animation state, request animation frame loop
    // ... 100+ lines of setup code

    return () => { /* cleanup */ };
  }, []);

  return <canvas ref={canvasRef} width={400} height={400} />;
}
```

Community wrappers (e.g., `react-spine`) are unofficial and may lag behind Spine runtime updates.

## Bundle Size Analysis

### Rive

- Runtime: ~150KB gzip (includes WASM renderer), loads once
- `.riv` files: target <100KB each (images + animation embedded)
- **Two characters total: ~550KB**

### Spine2D

- Runtime: ~80KB gzip (JS only)
- Per character: `.skel` (10–50KB) + `.atlas` (1–5KB) + texture PNG (100–500KB)
- **Two characters total: ~740KB+** (textures dominate for art-heavy characters)

Spine's runtime is smaller, but total asset weight is typically higher because of texture atlases.

## State Machine Comparison

### Rive State Machines

Built into Rive Editor as visual graph. Designers build and test state machines without code. Inputs (Trigger, Boolean, Number) defined in Editor, accessed by name in code. Live preview with input controls.

### Spine2D State Machines

No visual state machine editor. Entirely code-driven:

```ts
// Spine2D animation state example
animationState.setAnimation(0, 'idle', true); // track, name, loop
animationState.addAnimation(0, 'attack', false, 0); // queues after idle
animationState.addListener({
  complete: (entry) => {
    if (entry.animation.name === 'attack') {
      animationState.setAnimation(0, 'idle', true);
    }
  }
});
```

All transitions, conditions, and blending coded manually. Designers must communicate with engineers for any state machine change.

## Editor Comparison

### Rive Editor (rive.app)

- Free for unlimited projects (paid tiers add team collaboration)
- Web-based, no install, any OS
- Supports: bones, mesh deformation, constraints (IK, transform), state machines, events, blend modes

### Spine2D Editor

- Essential: $69 / Professional: $299 (one-time)
- Desktop app: Windows or macOS only
- Binary `.spine` format, hard to diff
- Mature: 10+ years, extensive docs and tutorials

## When to Choose Spine2D Instead

| Scenario | Reason |
|----------|--------|
| Shipping to Unity/Unreal/Godot | Spine has official, production-grade game engine runtimes |
| Team already has Spine licenses | No reason to retrain or rebuild existing rigs |
| Game is primarily a native app (not web) | Rive's web-first design is a disadvantage in native contexts |
| Need battle-tested stability (10+ years) | Spine has deeper track record in shipped games |
| Very complex mesh deformation (clothing physics, jiggle) | Spine's Professional tier has more deformation tooling |

For Road to AEW (React 19, web, no game engine): Spine2D offers no advantages over Rive and lacks a first-party React runtime.

## Migration Path

If the game expands to native:

1. **Rive for web, Spine for native**: Art assets reusable; rigging/animation redone in Spine
2. **Rive on mobile**: `rive-ios` and `rive-android` runtimes available. Capacitor WebView uses web runtime unchanged
3. **WebGL**: Rive canvas renderer works in any WebGL context

Rive does not lock out native expansion — it defers that complexity.

## Summary

Rive for React web games:
- First-party hooks, zero integration work
- Free editor, single-file format
- State machine UI accelerates gameplay iteration
- 150KB runtime acceptable at combat screen boundary
