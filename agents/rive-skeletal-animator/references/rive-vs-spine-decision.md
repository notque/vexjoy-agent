# Rive vs Spine2D Decision Reference
<!-- Loaded by rive-skeletal-animator when task involves: choosing between Rive and Spine2D, comparing animation runtimes, bundle size tradeoffs, editor cost comparison, React integration comparison -->

This reference answers the question: for a React-based web game like Road to AEW, should we use Rive or Spine2D for skeletal character animation? The short answer is Rive. This document explains why, and identifies the cases where Spine2D would be the better choice.

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

**Verdict for web/React projects**: Rive wins on runtime integration, editor accessibility, and file management. Spine2D's advantages are in game engine ecosystems and longer community maturity — neither of which applies to a React web game.

## Runtime Integration Comparison

### Rive in React

```tsx
// 3 lines to display a fully animated character with state machine
import { useRive } from '@rive-app/react-canvas';

const { RiveComponent } = useRive({
  src: '/characters/player.riv',
  stateMachines: 'CombatStateMachine',
  autoplay: true,
});

return <div style={{ width: 400, height: 400 }}><RiveComponent /></div>;
```

First-party hooks (`useRive`, `useStateMachineInput`) handle canvas lifecycle, WASM loading, resize, and cleanup. Zero boilerplate for basic use cases.

### Spine2D in React

Spine2D has no first-party React package. Integration requires:

1. Install `@esotericsoftware/spine-webgl` or `@esotericsoftware/spine-canvas`
2. Create a canvas element manually with `useRef`
3. Load `.skel` + `.atlas` + texture files separately
4. Build the WebGL/Canvas rendering loop imperatively
5. Manage resize observers manually
6. Handle animation state machine changes via the Spine `AnimationState` API directly

```tsx
// Rough Spine2D React skeleton (no pun intended)
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

Community wrappers exist (e.g., `react-spine`) but are not officially maintained and may lag behind Spine runtime updates.

## Bundle Size Analysis

### Rive

- `@rive-app/react-canvas`: ~150KB gzip (includes WASM renderer)
- `.riv` character files: target < 100KB each (images + animation data embedded)
- Total for two characters: ~350KB (runtime) + ~200KB (2 characters) = **~550KB**

The runtime loads once; additional characters only add their `.riv` file cost.

### Spine2D

- `@esotericsoftware/spine-canvas`: ~80KB gzip (JS only)
- `.skel` skeleton file: 10–50KB per character
- `.atlas` file: 1–5KB per character
- Atlas texture PNG: 100–500KB per character (depends on art resolution)
- Total for two characters: ~80KB + 2×(30KB + 300KB) = **~740KB** (or much more with high-res textures)

Spine texture atlases pack multiple sprites into a single PNG, but for realistic wrestler art at game-ready resolution, the textures dominate the bundle. Rive embeds image data in the `.riv` file with built-in compression.

**Note**: Spine's 80KB runtime is smaller than Rive's 150KB runtime. But Spine's texture requirement means total asset weight is typically higher for art-heavy characters.

## State Machine Comparison

### Rive State Machines

Built directly into the Rive Editor. Visual graph: drag states, draw transitions, set conditions. Designers can build and test state machines without any code. Inputs (Trigger, Boolean, Number) are defined in the Editor and accessed by name in code.

Rive state machines preview in the Editor with live input controls — click a trigger, flip a boolean, and watch the character respond in real time.

### Spine2D State Machines

No visual state machine editor. Animation logic is entirely code-driven:

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

Transitions, conditions, and blending are all coded manually. Designers must communicate with engineers to change any state machine logic. This increases iteration time significantly for the kind of rapid gameplay tuning a wrestling game requires.

## Editor Comparison

### Rive Editor (rive.app)

- Free for unlimited projects (paid tiers add team collaboration features)
- Web-based: runs in the browser, no install, available on any OS
- Autosaves to cloud, export `.riv` on demand
- Direct designer/developer handoff: share a Rive file link, developer copies the state machine input names into code
- Supports: bones, mesh deformation, constraints (IK, transform), state machines, events, blend modes

### Spine2D Editor

- Essential: $69 one-time (export to runtimes)
- Professional: $299 one-time (mesh deformation, skins, IK full feature set)
- Desktop app: Windows or macOS only
- Project files are binary `.spine` format — not text, harder to diff in version control
- Very mature: 10+ years of development, extensive documentation, large tutorial ecosystem

For an indie wrestling game being built in React: the Rive Editor's free web access removes a meaningful barrier to getting artists contributing without budget allocation for tooling.

## When to Choose Spine2D Instead

Spine2D wins in these scenarios:

| Scenario | Reason |
|----------|--------|
| Shipping to Unity/Unreal/Godot | Spine has official, production-grade game engine runtimes |
| Team already has Spine licenses | No reason to retrain or rebuild existing rigs |
| Game is primarily a native app (not web) | Rive's web-first design is a disadvantage in native contexts |
| Need battle-tested stability (10+ years) | Spine has deeper track record in shipped games |
| Very complex mesh deformation (clothing physics, jiggle) | Spine's Professional tier has more deformation tooling |

For the Road to AEW game specifically — React 19, web/browser, no game engine — Spine2D offers no meaningful advantages over Rive, and its lack of a first-party React runtime would require significant custom integration work.

## Migration Path (if ever needed)

If the game later expands to a native app (Capacitor, React Native, or full game engine port), the animation work in Rive is not wasted. Options:

1. **Keep Rive for web, rebuild in Spine for native**: Art assets (decomposed layers) are reusable across both tools. The rigging and animation work would need to be redone in Spine, but the character designs carry over.

2. **Use Rive on mobile too**: Rive has iOS and Android runtimes — `rive-ios` and `rive-android`. If the mobile port stays as a WebView (Capacitor), the web runtime continues to work unchanged.

3. **WebGL export via Rive**: Rive's canvas renderer works in any WebGL context, including game engines that support WebViews for UI layers.

The decision to use Rive does not lock the project out of future native expansion — it defers that complexity until the platform requires it.

## Summary

For React web games, Rive is the pragmatic choice:
- No extra integration work (first-party hooks)
- Free editor removes tooling cost barriers
- Single-file format simplifies asset management
- State machine UI accelerates gameplay iteration
- 150KB runtime cost is acceptable at the combat screen boundary

Spine2D is the industry standard for game engine projects and has a deeper catalog of learning resources — but its advantages don't translate to a web/React context without significant custom plumbing.
