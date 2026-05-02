---
name: phaser-gamedev
description: "Phaser 3 2D game dev: scenes, physics, tilemaps, sprites, polish."
agent: typescript-frontend-engineer
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
routing:
  triggers:
    - phaser
    - 2d game
    - platformer
    - arcade physics
    - tilemap
    - sprite sheet
    - side scroller
  pairs_with:
    - typescript-frontend-engineer
    - game-asset-generator
  complexity: Medium
  category: game-development
---

# Phaser Gamedev Skill

Builds Phaser 3.60+ 2D games: DESIGN → BUILD → ANIMATE → POLISH. Covers platformers, arcade shooters, top-down RPGs, puzzle games, side-scrollers. Use `threejs-builder` for 3D or non-Phaser work.

---

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| `references/core-patterns.md` | `core-patterns.md` | Always |
| `references/build-scaffolds.md` | `build-scaffolds.md` | Phase 2 BUILD |
| `references/animate-scaffolds.md` | `animate-scaffolds.md` | Phase 3 ANIMATE |
| `references/polish-scaffolds.md` | `polish-scaffolds.md` | Phase 4 POLISH |
| `references/errors.md` | `errors.md` | Error Handling |
| `references/arcade-physics.md` | `arcade-physics.md` | Arcade physics |
| `references/tilemaps.md` | `tilemaps.md` | Tilemap / Tiled |
| `references/spritesheets.md` | `spritesheets.md` | Sprites / animation |
| `references/performance.md` | `performance.md` | Performance concern |
| `references/game-feel-patterns.md` | `game-feel-patterns.md` | Polish / juice signal |
| `references/tilemaps-and-physics.md` | `tilemaps-and-physics.md` | Complex maps / Matter.js |

## Instructions

### Phase 1: DESIGN

**Goal**: Plan game type, physics system, and scene graph before writing code.

**Core constraints**:
- Read repository CLAUDE.md first -- local standards override defaults
- Select physics system before any other decision -- Arcade/Matter.js/None cannot be mixed per scene without deliberate design
- Plan scenes upfront -- Boot → Preload → Game → UI is standard; diverge only when required

**Step 1: Identify the game type**

Determine: genre (platformer, shooter, RPG, puzzle, side-scroller), physics need, scene count, tilemap vs procedural world, spritesheet vs texture atlas.

**Step 2: Select the physics system**

| Physics | Use When | Not For |
|---------|----------|---------|
| Arcade | Platformers, shooters, simple AABB | Rotating bodies, non-rectangular shapes |
| Matter.js | Physics puzzles, destructible terrain | Performance-critical (100+ bodies) |
| None | Puzzles, card games, UI-only | Any collision detection |

**Step 3: Document scene plan and load references**

Write a short markdown scene plan: Boot, Game, UI, Physics choice, World, Sprites (measured frame dimensions).

Load references based on plan:
- Always: `references/core-patterns.md`
- Tilemap: `references/tilemaps.md`
- Sprites/animation: `references/spritesheets.md`
- Arcade physics: `references/arcade-physics.md`
- Performance concern / many objects: `references/performance.md`
- Polish / game feel / juice ("screen shake", "particles", "hit feedback"): `references/game-feel-patterns.md`
- Matter.js, slopes, object layers, complex collision, Tiled spawning: `references/tilemaps-and-physics.md`

**Gate**: Scene plan documented. Physics selected. References loaded.

---

### Phase 2: BUILD

**Goal**: Implement scene lifecycle skeleton, load assets, place sprites, wire tilemaps.

**Core constraints**:
- **MEASURE spritesheet frames before loading** -- wrong `frameWidth`/`frameHeight` is the #1 Phaser bug; count pixels per frame before writing `this.load.spritesheet()`
- **Preload all assets in `preload()`** -- never in `create()` or `update()`
- **Use a Boot scene for asset loading** -- progress bar, keeps Game scene clean

TypeScript scaffolds: `references/build-scaffolds.md`.

**Gate**: Boot and Game scenes compile. Assets load without errors. Scene transitions work.

---

### Phase 3: ANIMATE

**Goal**: Add physics movement, animation state machines, and input.

**Core constraints**:
- **Never allocate in `update()`** -- no `new Phaser.Math.Vector2()`, no `this.physics.add.sprite()`, no per-frame arrays; allocate in `create()`, reuse in `update()`
- **Use `delta` for frame-rate-independent movement** -- `velocity = speed * (delta / 1000)`
- **State machine over boolean flags** -- `'idle' | 'walk' | 'jump' | 'attack' | 'dead'` prevents impossible states like `isJumping && isAttacking`

Animation and input scaffolds: `references/animate-scaffolds.md`. Collision and physics tuning: `references/arcade-physics.md`.

**Gate**: Player moves. Animations transition correctly. No impossible state combinations. No per-frame allocations.

---

### Phase 4: POLISH

**Goal**: Camera work, particles, tweens, sound, mobile controls. Verify performance.

**Core constraints**:
- Remove `debug: true` from physics config before shipping
- Remove all `console.log` calls unless explicitly requested
- **60 FPS budget** -- Arcade + 200 bodies + 50 particles is the ceiling on mid-range mobile

Scaffolds: `references/polish-scaffolds.md`.

**Gate**: Polish checks pass. Performance within budget. Debug config removed.

---

## Error Handling

Common errors and fixes: `references/errors.md`.

---

## References

| Reference | When to Load | Content |
|-----------|-------------|---------|
| `references/core-patterns.md` | Always | Scene lifecycle, transitions, input, state machines |
| `references/build-scaffolds.md` | Phase 2 BUILD | Entry point, BootScene, GameScene skeleton |
| `references/animate-scaffolds.md` | Phase 3 ANIMATE | Animations, Player state machine, input |
| `references/polish-scaffolds.md` | Phase 4 POLISH | Camera, particles, tweens, sound, mobile, verification |
| `references/errors.md` | Error Handling | Common Phaser errors and fixes |
| `references/arcade-physics.md` | Arcade physics | Groups, colliders, velocity, tuning, pitfalls |
| `references/tilemaps.md` | Tilemap / Tiled | Layers, collision, animated tiles, object layers |
| `references/spritesheets.md` | Sprites / animation | Frame measurement, loading, atlases, nine-slice |
| `references/performance.md` | Performance concern | Object pooling, GC avoidance, texture atlases, mobile |
| `references/game-feel-patterns.md` | Polish / juice | Screen shake, particles, hit-stop, scale punch, tweens, sound timing |
| `references/tilemaps-and-physics.md` | Complex maps / Matter.js | Tiled pipeline, Matter.js vs Arcade, collision categories, slopes, spawning |
