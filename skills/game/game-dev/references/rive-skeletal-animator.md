# Rive Skeletal Animation

Rive skeletal animation for React apps: `@rive-app/react-canvas` runtime integration, Rive Editor rigging and animation workflows, state machine design for game characters, and performance budgets for 60fps mobile targets. Primary context: the Road to AEW wrestling game (React 19, Vite 7, Zustand, CombatEngine event dispatch), replacing Framer Motion sprite animations with Rive skeletal characters.

Not for: GPU particle and WebGL combat rendering (`pixijs-combat-renderer.md`); CSS or Framer Motion effects (`combat-effects-upgrade.md`); 2D sprite-sheet generation pipelines (Sprite mode in this skill); 3D scene animation (`frontend` skill, THREEJS mode).

Domains:
- **Rive Runtime API**: `useRive` hook, `useStateMachineInput`, `RiveComponent`, `.riv` file loading, async instance lifecycle
- **State Machine Design**: Boolean/Number/Trigger inputs, layer blending, transition conditions, default states, animation layering for combat
- **Character Rigging**: Bone hierarchies for bipedal wrestlers, vertex weighting at joints, mesh deformation for organic motion, IK constraints
- **Art Pipeline**: Sprite decomposition → Rive Editor rigging → animation → `.riv` export, file size targeting under 100KB per character
- **React 19 Integration**: Canvas mounting, Zustand store → Rive input bridging, CombatEngine event → animation trigger wiring
- **Performance**: 60fps mobile target, WebGL context limits, canvas size budgets, lazy runtime loading

## Phases

### ASSESS
- Read CLAUDE.md and any existing combat component files before touching anything, because project conventions override these defaults
- Identify current animation approach: which components use Framer Motion, what animation variants exist, what CombatEngine events are dispatched
- Confirm React version (19 assumed; patterns differ for 18), Vite config for WASM/asset loading, Zustand store shape
- Check `package.json` for `@rive-app/react-canvas`; if absent, install before any integration work

### PIPELINE
Load `rive-skeletal-animator/rive-character-pipeline.md` when the task involves art creation, rigging, or `.riv` export.

- Decompose sprite into separate body part layers before importing to Rive Editor
- Build bone hierarchy: Root → Spine → Chest → Shoulders → (Upper/Lower Arms, Hands) + (Upper/Lower Legs, Feet) + Head/Neck
- Weight vertices at joint areas with blended influence (50/50 at elbows, knees)
- Build animation clips for the standard wrestling animation set (see `rive-skeletal-animator/rive-animation-library.md`)
- Export `.riv` and place in `src/assets/characters/`; keep under 100KB per file

### INTEGRATE
Load `rive-skeletal-animator/rive-react-setup.md` when the task involves mounting Rive in React, wiring Zustand, or handling CombatEngine events.

- Replace `<img>` sprite + `<motion.div>` wrapper with `<RiveComponent>`; do not coexist, do not wrap Rive in Framer Motion
- Mount canvas at the same pixel dimensions as the original sprite (400×400 for PlayerCharacter, 900px for EnemyCharacter)
- Connect Zustand combat state to Rive inputs via `useStateMachineInput`; state changes drive inputs, not imperative calls scattered across components
- Wire CombatEngine events to trigger inputs (attacks, hits, blocks) and boolean inputs (isBlocking, isStunned)
- Lazy-load the Rive runtime: only load `@rive-app/react-canvas` when the combat screen mounts, because the WASM bundle is ~150KB

### ANIMATE
Load `rive-skeletal-animator/rive-animation-library.md` when building or debugging animations, state machine transitions, or timing sync.

- Default state machine entry: `idle` loop
- Attack sequence: `attack_windup` → `attack_strike` → `attack_recover` → back to `idle`
- Hit response: `hit_react` trigger interrupts current state, returns to `idle` after 0.4s
- Block: boolean input `isBlocking` drives guard pose hold
- Animation durations must match CombatEngine timing: if the engine expects a 0.2s strike window, the `attack_strike` clip is 0.2s exactly

### VALIDATE
- Verify 60fps at target canvas size on mobile viewport (375px wide baseline)
- Check `.riv` file size; flag if over 100KB per character
- Confirm state machine has no dead-end states (every state has a path back to idle)
- Run `tsc --noEmit` after integration: no implicit `any`, all Rive hook return types used correctly
- Test all CombatEngine event paths trigger their corresponding animations
- Remove old Framer Motion imports from migrated components; they should not coexist

## Reference loading table

| Signal | Load |
|--------|------|
| Installing Rive, mounting canvas, useRive hook, useStateMachineInput, Zustand wiring, CombatEngine events, lazy loading, Vite config | `rive-skeletal-animator/rive-react-setup.md` |
| Sprite decomposition, Rive Editor rigging, bone hierarchy, vertex weighting, exporting .riv files | `rive-skeletal-animator/rive-character-pipeline.md` |
| Animation set design, state machine inputs, clip durations, idle/attack/hit/block animations, timing sync | `rive-skeletal-animator/rive-animation-library.md` |
| Choosing between Rive and Spine2D, bundle size tradeoffs, React runtime comparison, editor cost | `rive-skeletal-animator/rive-vs-spine-decision.md` |
| 60fps drops, WebGL context limits, canvas size, lazy loading WASM, Framer Motion wrapping, SharedRenderer | `rive-skeletal-animator/rive-performance.md` |
| rive instance null errors, onLoad vs useEffect, onStateChange, setTimeout sequencing, Zustand bridging | `rive-skeletal-animator/rive-async-patterns.md` |

## Key files (Road to AEW)

| File | Purpose |
|------|---------|
| `src/components/PlayerCharacter.tsx` | Current 400×400 sprite with Framer Motion idle bob and hit react |
| `src/components/EnemyCharacter.tsx` | Current 900px sprite with same animation patterns |
| `src/stores/combatStore.ts` | Zustand store: source of truth for combat state that drives Rive inputs |
| `src/engine/CombatEngine.ts` | Dispatches attack/block/hit events; wire to Rive trigger inputs here |
| `src/assets/characters/` | Target location for `.riv` character files |

## Related references

| Need | Load |
|------|------|
| TypeScript frontend architecture: type-safe components, state management, build optimization | `skills/frontend/frontend/references/typescript-frontend.md` |
| UI/UX design: design systems, responsive layouts, accessibility, animations | `skills/frontend/frontend/references/ui-design.md` |
| PixiJS v8 2D WebGL combat rendering: @pixi/react hybrid canvas, normal maps, GPU particles, post-processing | `pixijs-combat-renderer.md` |

## Error handling

**useRive returns null canvas**: The Rive instance loads asynchronously; guard with `if (!rive)` before accessing state machine inputs. Never fire inputs on a null rive instance.

**State machine input not found**: `useStateMachineInput` returns `null` if the input name doesn't match the `.riv` file exactly. Log the mismatch and check the Rive Editor for the exact string; names are case-sensitive.

**WASM load failure in Vite**: Add `?url` suffix to the WASM import or configure `vite.config.ts` with `assetsInclude: ['**/*.wasm']`. Load `rive-skeletal-animator/rive-react-setup.md` for the full Vite config pattern.

**Canvas size mismatch**: `RiveComponent` fills its container. Set explicit width/height on the wrapping div, not on `RiveComponent` directly.

**60fps drop on mobile**: Canvas at 900px is expensive. Load `rive-skeletal-animator/rive-react-setup.md` for the WebGL context sharing pattern and canvas downscale strategy.

**Animation duration drift**: If the combat engine dispatches the next event before animation completes, load `rive-skeletal-animator/rive-animation-library.md` for the timing sync table and the `onStateChange` callback pattern.
