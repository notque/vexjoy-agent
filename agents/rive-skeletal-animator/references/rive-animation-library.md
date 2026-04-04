# Rive Animation Library Reference
<!-- Loaded by rive-skeletal-animator when task involves: animation set design, state machine inputs, clip durations, idle/attack/hit/block animations, timing sync with CombatEngine, state transitions -->

The standard wrestling animation set covers the complete combat lifecycle: entering the ring, fighting, reacting, and finishing. Every clip in this library maps to a CombatEngine event. Durations are non-negotiable — they match game logic timing windows.

## Standard Animation Set

| Clip name | Loop | Duration | Trigger type | Purpose |
|-----------|------|----------|-------------|---------|
| `idle` | Loop | 3s | — (default state) | Breathing, weight shift |
| `attack_windup` | One-Shot | 0.3s | Trigger: `attack` | Pull-back before strike |
| `attack_strike` | One-Shot | 0.2s | (auto-chains from windup) | Fast forward impact |
| `attack_recover` | One-Shot | 0.3s | (auto-chains from strike) | Return to guard |
| `hit_react` | One-Shot | 0.4s | Trigger: `hit` | Stagger from damage |
| `block` | One-Shot (hold) | 0.3s | Boolean: `isBlocking` | Guard arms up |
| `block_release` | One-Shot | 0.2s | (auto-chains when isBlocking = false) | Drop guard |
| `signature_windup` | One-Shot | 0.5s | Trigger: `signature` | Dramatic power move setup |
| `finisher_windup` | One-Shot | 0.8s | Trigger: `finisher` | Full-screen worthy build |
| `entrance` | One-Shot | 1.5s | Trigger: `entrance` | Walk in from side |
| `victory` | Loop | 2s | Trigger: `victory` | Celebration loop |
| `defeat` | One-Shot (hold) | 1s | Trigger: `defeat` | Collapse and hold |

**One-Shot (hold)** means the animation plays once and stays on its last frame until the state machine transitions away. Used for block hold and defeat slump.

## State Machine Design

The state machine is named `CombatStateMachine` in the Rive Editor. All character components reference this exact name.

### Inputs

| Input name | Type | Default | Purpose |
|------------|------|---------|---------|
| `attack` | Trigger | — | Fires attack sequence |
| `hit` | Trigger | — | Fires hit_react |
| `signature` | Trigger | — | Fires signature_windup |
| `finisher` | Trigger | — | Fires finisher_windup |
| `entrance` | Trigger | — | Fires entrance animation |
| `victory` | Trigger | — | Fires victory loop |
| `defeat` | Trigger | — | Fires defeat and holds |
| `isBlocking` | Boolean | false | Drives block hold |

Number inputs (optional, for future use):
| Input name | Type | Default | Purpose |
|------------|------|---------|---------|
| `health` | Number | 100 | Drive visual health cues (stagger intensity) |
| `angerMeter` | Number | 0 | Drive visual intensity at high anger |

### State Graph

```
                    ┌─────────────────────────────────────────────────────┐
                    │                                                      │
                    ▼                                                      │
              ┌─────────┐                                                  │
    entry ──► │  idle   │ ◄── (return from all one-shot clips)            │
              └─────────┘                                                  │
                  │ ▲                                                       │
     attack T │   │ (auto after recover)                                  │
                  ▼                                                        │
         ┌──────────────────┐                                             │
         │  attack_windup   │                                             │
         └─────────┬────────┘                                             │
                   │ (auto-chain, 0.3s)                                   │
                   ▼                                                       │
         ┌──────────────────┐                                             │
         │  attack_strike   │                                             │
         └─────────┬────────┘                                             │
                   │ (auto-chain, 0.2s)                                   │
                   ▼                                                       │
         ┌──────────────────┐                                             │
         │ attack_recover   │─────────────────────────────────────────────┘
         └──────────────────┘ (returns to idle)

     hit T ──► hit_react ──► idle (0.4s)
     isBlocking=T ──► block (hold) ──► [isBlocking=F] ──► block_release ──► idle
     signature T ──► signature_windup ──► idle (0.5s)
     finisher T ──► finisher_windup ──► idle (0.8s)
     entrance T ──► entrance ──► idle (1.5s)
     victory T ──► victory (loop)
     defeat T ──► defeat (hold)
```

**Priority**: `hit_react` should interrupt any non-terminal state. In Rive, set `hit_react` transitions as "Any State → hit_react" with the trigger condition. This ensures a hit during windup or strike still plays the hit react.

**Exception**: Block state should not be interrupted by hit_react when `isBlocking = true` — a successful block means no stagger. Use a condition: `hit AND NOT isBlocking → hit_react`.

## Animation Detail Specifications

### idle (3s loop)

| Frame range | Bone | Property | Values | Notes |
|-------------|------|----------|--------|-------|
| 0–90 | Root | Y translate | 0 → -3 → 0 | Matches original y:[0,-3,0] |
| 0–90 | Chest | Y translate | 0 → 2 → 0 | Breathing |
| 0–90 | Root | X translate | 0 → 3 → 0 → -3 → 0 | Weight shift |
| 0–90 | Head | Z rotate | 0 → 1° → 0 → -1° → 0 | Head bob |
| 0–90 | LowerArm_L | Z rotate | 0 → 3° → 0 | Subtle fist tension |

All curves: ease-in-out. No linear interpolation in idle — it looks mechanical.

### attack_windup (0.3s = 18 frames at 60fps)

| Frame | Bone | Property | Value |
|-------|------|----------|-------|
| 0 | All | — | Idle pose |
| 6 | UpperArm_R | Z rotate | +40° (pull back) |
| 6 | LowerArm_R | Z rotate | -20° (cock fist) |
| 6 | Spine1 | Z rotate | -8° (lean into windup) |
| 18 | All | — | Hold pose for strike transition |

### attack_strike (0.2s = 12 frames)

| Frame | Bone | Property | Value |
|-------|------|----------|-------|
| 0 | All | — | Windup end pose |
| 4 | UpperArm_R | Z rotate | -30° (fast forward) |
| 4 | LowerArm_R | Z rotate | +40° (extend punch) |
| 4 | Root | X translate | +20px (lunge forward) |
| 4 | Spine1 | Z rotate | +15° (commit weight) |

Strike frame 4 is the impact frame — this is where hit detection should register in CombatEngine. The animation communicates impact; the engine confirms it.

Curve: very fast ease-in (strike is sudden), ease-out from frame 4 onward.

### attack_recover (0.3s = 18 frames)

Lerp from strike pose back to idle guard pose. Ease-out — the recovery is controlled, not snappy.

### hit_react (0.4s = 24 frames)

| Frame | Bone | Property | Value |
|-------|------|----------|-------|
| 0 | All | — | Current pose |
| 4 | Head | Z rotate | -25° (head snap back) |
| 4 | Spine1 | Z rotate | -15° (body lean back) |
| 4 | Root | X translate | -15px (stagger back) |
| 4 | UpperArm_L/R | Z rotate | +20° (arms fly up) |
| 14 | Root | X translate | -25px (stagger peak) |
| 24 | All | — | Near-idle pose |

The original Framer Motion hit react was `scale: [1, 0.85, 1.05, 1]` over 0.5s. The Rive version replaces scale with body lean — bone-driven motion reads as more impactful than a CSS scale.

**Red flash**: Framer Motion also added a red overlay CSS effect. This is not replicated in Rive — implement it as a separate absolutely-positioned div overlaid on the RiveComponent canvas, triggered by the same `hit` Zustand action.

### block (hold state)

| Frame | Bone | Property | Value |
|-------|------|----------|-------|
| 0 | All | — | Idle pose |
| 12 | UpperArm_L/R | Z rotate | -60° (arms cross in front) |
| 12 | LowerArm_L/R | Z rotate | +45° (forearms up, vertical) |
| 12 | Head | Z rotate | -5° (chin tuck) |
| 12 | Spine1 | Z rotate | +5° (slight forward lean) |

Hold at frame 12 until `isBlocking` becomes false, then chain to `block_release`.

### entrance (1.5s = 90 frames)

Character walks in from the right side (player) or left side (enemy). Root X starts at ±300px off-screen, translates to 0 over 60 frames, then plays a short pose flex for 30 frames.

Walking motion: alternating leg swing on UpperLeg and LowerLeg bones, counter-rotating arms, slight torso rotation.

### victory (2s loop)

Fist pump: UpperArm_R raises, LowerArm_R extends overhead, whole body bounces slightly via Root Y.

### defeat (1s, hold)

Character slumps: Root Y drops -30px, Spine1 bends forward +30°, Head drops -20°, arms hang (UpperArm rotate +60°). Hold on final frame.

## Timing Sync with CombatEngine

The game engine must not dispatch the next action until the current animation is in an interruptible state. Use `onStateChange` to signal readiness:

```ts
// In combatStore.ts
interface CombatStore {
  playerAnimationComplete: boolean;
  setAnimationComplete: (character: 'player' | 'enemy') => void;
}
```

```tsx
// In PlayerCharacter.tsx
const { RiveComponent } = useRive({
  src: playerRiv,
  stateMachines: SM,
  autoplay: true,
  onStateChange: (event) => {
    if (event.data[0] === 'idle') {
      useCombatStore.getState().setAnimationComplete('player');
    }
  },
});
```

```ts
// In CombatEngine.ts
async function executeAttack(attackerId: 'player' | 'enemy') {
  // Fire the attack animation trigger
  store.dispatchAction('attack');

  // Wait for animation to complete (returns to idle)
  await waitForAnimationComplete(attackerId); // polls store flag

  // Now safe to evaluate the next game state
  resolveAttackDamage();
}
```

This eliminates `setTimeout(resolveAttackDamage, 800)` patterns that drift when the game frame rate is inconsistent.

## State Machine Anti-Patterns

**Dead-end states**: Every state must have a transition back to idle. Test this by manually triggering each input in the Rive Editor's preview — if any state doesn't return to idle, add the transition.

**Race condition on rapid inputs**: If `attack` fires twice in 100ms, the second trigger may interrupt mid-windup. Decide policy in CombatEngine: either debounce triggers (reject new inputs while animation is active) or accept interruption (second attack starts from wherever the first was). The `animationComplete` flag above implements the debounce approach.

**Blocking + hit_react**: When `isBlocking = true`, don't trigger `hit_react`. The state machine condition should be `hit AND NOT isBlocking → hit_react`. A successful block has no stagger reaction; consider a separate subtle `block_hit` clip (small shudder, 0.15s) for physical feedback on a blocked strike.
