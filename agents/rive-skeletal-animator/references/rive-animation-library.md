# Rive Animation Library Reference
<!-- Loaded by rive-skeletal-animator when task involves: animation set design, state machine inputs, clip durations, idle/attack/hit/block animations, timing sync with CombatEngine, state transitions -->

Standard wrestling animation set covering the complete combat lifecycle. Every clip maps to a CombatEngine event. Durations match game logic timing windows exactly.

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
| `signature_windup` | One-Shot | 0.5s | Trigger: `signature` | Power move setup |
| `finisher_windup` | One-Shot | 0.8s | Trigger: `finisher` | Full-screen build |
| `entrance` | One-Shot | 1.5s | Trigger: `entrance` | Walk in from side |
| `victory` | Loop | 2s | Trigger: `victory` | Celebration loop |
| `defeat` | One-Shot (hold) | 1s | Trigger: `defeat` | Collapse and hold |

**One-Shot (hold)**: Plays once, stays on last frame until state machine transitions away.

## State Machine Design

State machine name: `CombatStateMachine` (all components reference this exact name).

### Inputs

| Input name | Type | Default | Purpose |
|------------|------|---------|---------|
| `attack` | Trigger | — | Fires attack sequence |
| `hit` | Trigger | — | Fires hit_react |
| `signature` | Trigger | — | Fires signature_windup |
| `finisher` | Trigger | — | Fires finisher_windup |
| `entrance` | Trigger | — | Fires entrance |
| `victory` | Trigger | — | Fires victory loop |
| `defeat` | Trigger | — | Fires defeat and holds |
| `isBlocking` | Boolean | false | Drives block hold |

Optional number inputs:
| Input name | Type | Default | Purpose |
|------------|------|---------|---------|
| `health` | Number | 100 | Visual health cues (stagger intensity) |
| `angerMeter` | Number | 0 | Visual intensity at high anger |

### State Graph

```
              ┌─────────┐
    entry ──► │  idle   │ ◄── (return from all one-shot clips)
              └─────────┘
                  │ ▲
     attack T │   │ (auto after recover)
                  ▼
         ┌──────────────────┐
         │  attack_windup   │
         └─────────┬────────┘
                   │ (auto-chain, 0.3s)
                   ▼
         ┌──────────────────┐
         │  attack_strike   │
         └─────────┬────────┘
                   │ (auto-chain, 0.2s)
                   ▼
         ┌──────────────────┐
         │ attack_recover   │──► idle
         └──────────────────┘

     hit T ──► hit_react ──► idle (0.4s)
     isBlocking=T ──► block (hold) ──► [isBlocking=F] ──► block_release ──► idle
     signature T ──► signature_windup ──► idle (0.5s)
     finisher T ──► finisher_windup ──► idle (0.8s)
     entrance T ──► entrance ──► idle (1.5s)
     victory T ──► victory (loop)
     defeat T ──► defeat (hold)
```

**Priority**: `hit_react` interrupts any non-terminal state. Set as "Any State → hit_react" with trigger condition.

**Exception**: Block not interrupted by hit_react when `isBlocking = true`. Condition: `hit AND NOT isBlocking → hit_react`.

## Animation Detail Specifications

### idle (3s loop)

| Frame range | Bone | Property | Values | Notes |
|-------------|------|----------|--------|-------|
| 0–90 | Root | Y translate | 0 → -3 → 0 | Matches original y:[0,-3,0] |
| 0–90 | Chest | Y translate | 0 → 2 → 0 | Breathing |
| 0–90 | Root | X translate | 0 → 3 → 0 → -3 → 0 | Weight shift |
| 0–90 | Head | Z rotate | 0 → 1° → 0 → -1° → 0 | Head bob |
| 0–90 | LowerArm_L | Z rotate | 0 → 3° → 0 | Fist tension |

All curves: ease-in-out. No linear interpolation in idle.

### attack_windup (0.3s = 18 frames at 60fps)

| Frame | Bone | Property | Value |
|-------|------|----------|-------|
| 0 | All | — | Idle pose |
| 6 | UpperArm_R | Z rotate | +40° (pull back) |
| 6 | LowerArm_R | Z rotate | -20° (cock fist) |
| 6 | Spine1 | Z rotate | -8° (lean into windup) |
| 18 | All | — | Hold for strike transition |

### attack_strike (0.2s = 12 frames)

| Frame | Bone | Property | Value |
|-------|------|----------|-------|
| 0 | All | — | Windup end pose |
| 4 | UpperArm_R | Z rotate | -30° (fast forward) |
| 4 | LowerArm_R | Z rotate | +40° (extend punch) |
| 4 | Root | X translate | +20px (lunge) |
| 4 | Spine1 | Z rotate | +15° (commit weight) |

Frame 4 = impact frame for CombatEngine hit detection. Curve: fast ease-in (sudden strike), ease-out from frame 4.

### attack_recover (0.3s = 18 frames)

Lerp from strike to idle guard pose. Ease-out.

### hit_react (0.4s = 24 frames)

| Frame | Bone | Property | Value |
|-------|------|----------|-------|
| 0 | All | — | Current pose |
| 4 | Head | Z rotate | -25° (snap back) |
| 4 | Spine1 | Z rotate | -15° (body lean) |
| 4 | Root | X translate | -15px (stagger) |
| 4 | UpperArm_L/R | Z rotate | +20° (arms fly up) |
| 14 | Root | X translate | -25px (stagger peak) |
| 24 | All | — | Near-idle pose |

Replaces original Framer Motion `scale: [1, 0.85, 1.05, 1]` with bone-driven body lean.

**Red flash**: Not in Rive — implement as separate absolutely-positioned div overlaid on canvas, triggered by same `hit` Zustand action.

### block (hold state)

| Frame | Bone | Property | Value |
|-------|------|----------|-------|
| 0 | All | — | Idle pose |
| 12 | UpperArm_L/R | Z rotate | -60° (arms cross) |
| 12 | LowerArm_L/R | Z rotate | +45° (forearms up) |
| 12 | Head | Z rotate | -5° (chin tuck) |
| 12 | Spine1 | Z rotate | +5° (forward lean) |

Hold at frame 12 until `isBlocking = false`, then chain to `block_release`.

### entrance (1.5s = 90 frames)

Root X starts ±300px off-screen, translates to 0 over 60 frames, then 30-frame pose flex. Walking: alternating leg swing, counter-rotating arms, slight torso rotation.

### victory (2s loop)

Fist pump: UpperArm_R raises, LowerArm_R extends overhead, body bounces via Root Y.

### defeat (1s, hold)

Slump: Root Y -30px, Spine1 +30°, Head -20°, arms hang. Hold final frame.

## Timing Sync with CombatEngine

Use `onStateChange` to signal animation readiness — eliminates `setTimeout` drift:

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
  store.dispatchAction('attack');
  await waitForAnimationComplete(attackerId);
  resolveAttackDamage();
}
```

## State Machine Patterns to Watch

**Dead-end states**: Every state must transition back to idle. Test each input in Rive Editor preview.

**Rapid input race condition**: If `attack` fires twice in 100ms, second trigger may interrupt mid-windup. Policy: debounce via `animationComplete` flag (reject inputs while active) or accept interruption.

**Blocking + hit_react**: When `isBlocking = true`, don't trigger `hit_react`. Consider separate `block_hit` clip (0.15s shudder) for feedback on blocked strikes.
