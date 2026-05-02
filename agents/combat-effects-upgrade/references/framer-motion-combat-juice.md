# Framer Motion Combat Juice Reference
<!-- Loaded by combat-effects-upgrade when task involves card trajectories, hit-react animations, multi-hit stagger, or layout animations in combat components -->

Framer Motion renamed to **Motion** in 2025. Package: `framer-motion` → `motion`, imports: `framer-motion` → `motion/react`. API identical. Check package.json.

```typescript
import { motion, AnimatePresence, useMotionValue, useSpring } from 'motion/react';
// Legacy: import from 'framer-motion' (same API)
```

Patterns below use `motion/react`. Replace with `framer-motion` if needed.

---

## Current Animation Inventory and Upgrades

| # | Component | Current Pattern | Upgraded To |
|---|-----------|----------------|-------------|
| 1 | FramedCard — hover | scale(1.03) | scale(1.06) + 3D tilt toward cursor |
| 2 | FramedCard — play exit | scale(1.3) + slide up | trajectory arc toward target slot |
| 3 | PlayerCharacter — hit react | scale(0.85→1) | scale(0.85→1) + rotation wobble + spring overshoot |
| 4 | CombatPopups — damage | float up, instant | cascading stagger 100ms per hit |
| 5 | EnemyCharacter — idle | 4s breathing scale | add subtle sway (±2deg rotate) |
| 6 | CombatArena — screen shake | CSS class toggle | add motion blur via filter |
| 7 | CardHand — draw | fade in | slide from draw pile position via layoutId |
| 8 | PlayerCharacter — status badge | spring scale pop | add jiggle on value change |
| 9 | CardHand — reflow | spring layout | smooth reflow using layout prop |

---

## Pattern 1: Card Play Trajectory

Card flies from hand to target slot. `layoutId` measures start/end positions automatically.

```tsx
// src/components/FramedCard.tsx
import { motion, AnimatePresence } from 'motion/react';

interface FramedCardProps {
  card: Card;
  isPlaying: boolean;
  targetRef: React.RefObject<HTMLDivElement>;
}

export function FramedCard({ card, isPlaying, targetRef }: FramedCardProps) {
  return (
    <AnimatePresence mode="popLayout">
      {!isPlaying && (
        <motion.div
          key={card.id}
          layoutId={`card-${card.id}`}
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{
            // Arc trajectory: scale up briefly, fly toward target
            scale: [1, 1.15, 0.9],
            y: -120,
            opacity: 0,
            transition: {
              duration: 0.35,
              ease: [0.25, 0.46, 0.45, 0.94],
            },
          }}
          transition={{
            type: 'spring',
            stiffness: 400,
            damping: 28,
          }}
          className="framed-card"
        >
          <CardContent card={card} />
        </motion.div>
      )}
    </AnimatePresence>
  );
}
```

---

## Pattern 2: Hand Reflow with Layout Animation

Remaining cards auto-animate into new positions. No manual position calculation.

```tsx
// src/components/CardHand.tsx
import { motion, AnimatePresence } from 'motion/react';

interface CardHandProps {
  cards: Card[];
  onPlay: (card: Card) => void;
}

export function CardHand({ cards, onPlay }: CardHandProps) {
  return (
    // layout on the container propagates to children
    <motion.div layout className="card-hand">
      <AnimatePresence mode="popLayout">
        {cards.map((card, index) => (
          <motion.div
            key={card.id}
            layout  // automatically animates position changes
            initial={{ opacity: 0, scale: 0.8, y: 30 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.7, y: -20 }}
            transition={{
              type: 'spring',
              stiffness: 350,
              damping: 30,
              // Stagger cards as they enter
              delay: index * 0.05,
            }}
            onClick={() => onPlay(card)}
            style={{
              // Fan layout uses CSS custom property driven by index
              '--card-index': index,
              '--card-count': cards.length,
            } as React.CSSProperties}
          >
            <FramedCard card={card} />
          </motion.div>
        ))}
      </AnimatePresence>
    </motion.div>
  );
}
```

---

## Pattern 3: Hit React with Spring Overshoot

Character squishes, overshoots past normal, settles. Spring physics handle interruption automatically.

```tsx
// src/components/PlayerCharacter.tsx
import { motion, useAnimation } from 'motion/react';

export function PlayerCharacter({ isHit, hitType }: PlayerCharacterProps) {
  const controls = useAnimation();

  useEffect(() => {
    if (!isHit) return;

    // Fire-and-forget: squish + wobble sequence
    void controls.start({
      scale: [1, 0.82, 1.08, 0.96, 1],
      rotate: [0, hitType === 'left' ? -5 : 5, hitType === 'left' ? 3 : -3, 0],
      transition: {
        duration: 0.5,
        times: [0, 0.15, 0.35, 0.6, 1],
        ease: 'easeInOut',
      },
    });
  }, [isHit, hitType, controls]);

  return (
    <motion.div
      animate={controls}
      style={{ originX: 0.5, originY: 0.8 }} // pivot from feet
    >
      <CharacterSprite />
    </motion.div>
  );
}
```

---

## Pattern 4: Multi-Hit Damage Stagger

Each damage number 100ms after previous, so players track individual values.

```tsx
// src/components/CombatPopups.tsx
import { motion, AnimatePresence } from 'motion/react';

interface DamageEvent {
  id: string;
  value: number;
  x: number;
  y: number;
  timestamp: number;
}

interface CombatPopupsProps {
  damageEvents: DamageEvent[];
}

export function CombatPopups({ damageEvents }: CombatPopupsProps) {
  return (
    <AnimatePresence>
      {damageEvents.map((event, index) => (
        <motion.div
          key={event.id}
          className="damage-popup"
          initial={{ opacity: 0, scale: 0.6, y: 0 }}
          animate={{ opacity: 1, scale: 1.2, y: -20 }}
          exit={{ opacity: 0, scale: 0.8, y: -60 }}
          transition={{
            // Stagger each hit 100ms from the previous
            delay: index * 0.1,
            duration: 0.25,
            exit: { duration: 0.4, delay: 0.3 + index * 0.1 },
          }}
          style={{
            position: 'fixed',
            left: event.x,
            top: event.y,
          }}
        >
          -{event.value}
        </motion.div>
      ))}
    </AnimatePresence>
  );
}
```

---

## Pattern 5: Finisher Move — Dramatic Scale Sequence

Three-stage: anticipation pause → explosive scale → settle.

```tsx
// src/components/CombatArena.tsx
import { motion, AnimatePresence } from 'motion/react';

interface FinisherOverlayProps {
  isActive: boolean;
  finisherName: string;
}

export function FinisherOverlay({ isActive, finisherName }: FinisherOverlayProps) {
  return (
    <AnimatePresence>
      {isActive && (
        <motion.div
          className="finisher-overlay"
          initial={{ opacity: 0, scale: 3 }}
          animate={{
            opacity: [0, 1, 1, 0],
            scale: [3, 1, 1.05, 0.95],
            transition: {
              duration: 1.2,
              times: [0, 0.15, 0.7, 1],
              ease: ['easeOut', 'easeInOut', 'easeIn'],
            },
          }}
          exit={{ opacity: 0 }}
        >
          <motion.span
            initial={{ letterSpacing: '0.5em', opacity: 0 }}
            animate={{ letterSpacing: '0.05em', opacity: 1 }}
            transition={{ delay: 0.15, duration: 0.4 }}
          >
            {finisherName}
          </motion.span>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
```

---

## Pattern 6: Status Badge Jiggle on Value Change

```tsx
// src/components/PlayerCharacter.tsx
import { motion } from 'motion/react';
import { useRef } from 'react';

interface StatusBadgeProps {
  label: string;
  value: number;
  type: 'buff' | 'debuff';
}

export function StatusBadge({ label, value, type }: StatusBadgeProps) {
  const prevValue = useRef(value);

  // Detect value change for jiggle trigger
  const hasChanged = prevValue.current !== value;
  if (hasChanged) prevValue.current = value;

  return (
    <motion.div
      className={`status-badge status-badge--${type}`}
      // Pop in on mount
      initial={{ scale: 0, opacity: 0 }}
      animate={{
        scale: 1,
        opacity: 1,
        // Jiggle on value change
        rotate: hasChanged ? [0, -8, 8, -4, 4, 0] : 0,
      }}
      transition={{
        scale: { type: 'spring', stiffness: 500, damping: 20 },
        rotate: { duration: 0.4, ease: 'easeOut' },
      }}
      exit={{ scale: 0, opacity: 0 }}
    >
      <span className="badge-label">{label}</span>
      <span className="badge-value">{value}</span>
    </motion.div>
  );
}
```

---

## Pattern 7: Card Draw from Pile Position

Animates from draw pile position to hand slot via `useRef`.

```tsx
// src/components/CardHand.tsx
import { motion } from 'motion/react';
import { useRef } from 'react';

interface DrawPileProps {
  count: number;
  pileRef: React.RefObject<HTMLDivElement>;
}

export function DrawPile({ count, pileRef }: DrawPileProps) {
  return (
    <div ref={pileRef} className="draw-pile">
      {count}
    </div>
  );
}

// In CardHand — new cards animate from pile position
function DrawnCard({ card, pileRef }: { card: Card; pileRef: React.RefObject<HTMLDivElement> }) {
  const pileRect = pileRef.current?.getBoundingClientRect();

  return (
    <motion.div
      layoutId={`card-${card.id}`}
      initial={
        pileRect
          ? { x: pileRect.x, y: pileRect.y, scale: 0.4, opacity: 0 }
          : { opacity: 0, y: 40 }
      }
      animate={{ x: 0, y: 0, scale: 1, opacity: 1 }}
      transition={{
        type: 'spring',
        stiffness: 260,
        damping: 24,
        duration: 0.45,
      }}
    >
      <FramedCard card={card} />
    </motion.div>
  );
}
```

---

## Pattern 8: Enemy Idle Sway

Subtle rotation sway added to existing scale breathing.

```tsx
// src/components/EnemyCharacter.tsx
import { motion } from 'motion/react';

export function EnemyCharacter({ enemy }: EnemyCharacterProps) {
  return (
    <motion.div
      // Existing: breathing scale
      animate={{
        scale: [1, 1.015, 1],
        // Added: subtle rotation sway
        rotate: [0, 1.5, -1, 1, 0],
      }}
      transition={{
        duration: 4,
        repeat: Infinity,
        ease: 'easeInOut',
        // Slightly offset so scale and rotate don't peak simultaneously
        times: [0, 0.3, 0.5, 0.75, 1],
      }}
    >
      <EnemySprite src={enemy.sprite} />
    </motion.div>
  );
}
```

---

## Pattern 9: Screen Shake with Motion Blur

Adds filter blur to existing CSS screen shake for camera-shake effect.

```tsx
// src/components/CombatArena.tsx
import { motion } from 'motion/react';

interface CombatArenaProps {
  isShaking: boolean;
  children: React.ReactNode;
}

export function CombatArena({ isShaking, children }: CombatArenaProps) {
  return (
    <motion.div
      className={isShaking ? 'screen-shake' : undefined}
      animate={{
        filter: isShaking
          ? ['blur(0px)', 'blur(2px)', 'blur(1px)', 'blur(3px)', 'blur(0px)']
          : 'blur(0px)',
      }}
      transition={{
        duration: 0.3,
        ease: 'easeInOut',
      }}
    >
      {children}
    </motion.div>
  );
}
```

---

## Spring Physics Tuning Reference

| Feel | stiffness | damping | mass | Use For |
|------|-----------|---------|------|---------|
| Snappy, responsive | 500 | 30 | 1 | Status badge pop, small UI elements |
| Card-like, physical | 350 | 28 | 1 | Card play, hand layout |
| Weighty, powerful | 200 | 22 | 1.2 | Hit react, finisher |
| Floaty, playful | 150 | 18 | 0.8 | Heal float, buff text |
| Stiff, precise | 600 | 40 | 1 | Tilt follow (fast cursor tracking) |

Springs auto-handle interruption by carrying current velocity. No special code needed.

## Common Mistakes

- **`useAnimation` instead of `animate` prop**: `useAnimation` for imperative triggers only. State-driven combat animations use `animate` prop.
- **`AnimatePresence` without `key`**: Exit animations misfire without stable unique keys.
- **Nested `motion.div` with `layout`**: Layout propagates down. Both parent and child animate on every change. Check flame chart.
