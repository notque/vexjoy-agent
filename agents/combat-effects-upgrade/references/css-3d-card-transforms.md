# CSS 3D Card Transforms Reference
<!-- Loaded by combat-effects-upgrade when task involves card tilt, backface-visibility, CSS perspective, or Framer Motion + CSS 3D integration -->

## Overview

CSS 3D transforms give cards a physical feel: they tilt toward the cursor on hover, revealing a subtle depth effect. For card flip reveals (e.g. drawing a card face-down), `backface-visibility: hidden` hides the back face during the 180deg rotation. All transforms use GPU-composited properties (`transform`, `opacity`) — no layout or paint triggered.

**Browser support**: `perspective`, `transform-style: preserve-3d`, `backface-visibility` — universal modern browser support (Chrome 36+, Firefox 16+, Safari 9+).

---

## Tilt Formula

Mouse position within the card → rotation angles:

```
rotateY = (mouseX - cardCenterX) / cardWidth  * MAX_TILT_DEG
rotateX = -(mouseY - cardCenterY) / cardHeight * MAX_TILT_DEG
```

- `MAX_TILT_DEG` = 15 (degrees) — beyond 20deg starts looking exaggerated
- Negate `rotateX` because positive mouseY (mouse below center) should tilt the top toward viewer (negative rotateX in CSS convention)
- `cardCenter` is measured once from `getBoundingClientRect()` on `mouseenter`, not recalculated on every `mousemove`

---

## Complete Component: TiltCard

```tsx
// src/components/FramedCard.tsx
import { motion, useMotionValue, useSpring, useTransform } from 'motion/react';
import { useRef, useCallback, useState } from 'react';

const MAX_TILT_DEG = 15;
const SPRING_CONFIG = { stiffness: 300, damping: 30 } as const;

interface FramedCardProps {
  card: Card;
  onClick?: () => void;
}

export function FramedCard({ card, onClick }: FramedCardProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  const [isTouchDevice] = useState(
    () => window.matchMedia('(hover: none)').matches
  );

  // Raw motion values — these update on every mousemove WITHOUT triggering re-render
  const rawRotateX = useMotionValue(0);
  const rawRotateY = useMotionValue(0);

  // Springs smooth the raw values — tilt follows cursor with a slight lag
  const rotateX = useSpring(rawRotateX, SPRING_CONFIG);
  const rotateY = useSpring(rawRotateY, SPRING_CONFIG);

  // Subtle glare effect: opacity follows rotateY
  const glareOpacity = useTransform(rotateY, [-MAX_TILT_DEG, 0, MAX_TILT_DEG], [0.15, 0, 0.15]);

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (isTouchDevice || !cardRef.current) return;

    const rect = cardRef.current.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;

    rawRotateY.set((e.clientX - centerX) / (rect.width / 2) * MAX_TILT_DEG);
    rawRotateX.set(-((e.clientY - centerY) / (rect.height / 2)) * MAX_TILT_DEG);
  }, [isTouchDevice, rawRotateX, rawRotateY]);

  const handleMouseLeave = useCallback(() => {
    // Spring back to flat — spring physics handles the animation
    rawRotateX.set(0);
    rawRotateY.set(0);
  }, [rawRotateX, rawRotateY]);

  return (
    // Perspective on the container — children share one vanishing point
    <div className="card-perspective-container" ref={cardRef}>
      <motion.div
        className="framed-card"
        style={{
          rotateX,       // MotionValue — no re-renders, compositor-only updates
          rotateY,
          transformStyle: 'preserve-3d',
        }}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        onClick={onClick}
        // Existing hover scale
        whileHover={isTouchDevice ? undefined : { scale: 1.06 }}
        whileTap={{ scale: 0.97 }}
        transition={{ type: 'spring', stiffness: 400, damping: 28 }}
      >
        {/* Card face */}
        <div className="card-face card-face--front">
          <CardArtwork card={card} />
          <CardStats card={card} />
        </div>

        {/* Glare overlay — follows tilt direction */}
        <motion.div
          className="card-glare"
          style={{ opacity: glareOpacity }}
          aria-hidden="true"
        />
      </motion.div>
    </div>
  );
}
```

---

## Required CSS

```css
/* ─────────────────────────────────────────────
   Card perspective container
   perspective goes on the PARENT — gives children
   a shared vanishing point
   ───────────────────────────────────────────── */
.card-perspective-container {
  perspective: 1000px;
  perspective-origin: center center;
  /* Contain so tilt doesn't affect sibling layout */
  isolation: isolate;
}

/* ─────────────────────────────────────────────
   Card body
   ───────────────────────────────────────────── */
.framed-card {
  position: relative;
  width: 160px;
  height: 240px;
  border-radius: 12px;
  transform-style: preserve-3d;
  cursor: pointer;

  /* GPU layer hint — apply dynamically via JS, or only in hover state */
}

.framed-card:hover {
  will-change: transform;
}

/* Remove will-change when not hovering */
.framed-card:not(:hover) {
  will-change: auto;
}

/* ─────────────────────────────────────────────
   Card faces — used for flip reveal
   ───────────────────────────────────────────── */
.card-face {
  position: absolute;
  inset: 0;
  border-radius: 12px;
  backface-visibility: hidden;          /* Hide when rotated 180deg */
  -webkit-backface-visibility: hidden;  /* Safari */
}

.card-face--front {
  /* Front is naturally visible (0deg rotation) */
}

.card-face--back {
  /* Back starts flipped — visible when card rotates 180deg */
  transform: rotateY(180deg);
  background: url('/card-back.png') center/cover;
}

/* ─────────────────────────────────────────────
   Glare overlay
   ───────────────────────────────────────────── */
.card-glare {
  position: absolute;
  inset: 0;
  border-radius: 12px;
  background: linear-gradient(
    105deg,
    transparent 40%,
    rgba(255, 255, 255, 0.15) 50%,
    transparent 60%
  );
  pointer-events: none;
  /* translateZ pushes it above the card face in 3D space */
  transform: translateZ(1px);
}
```

---

## Card Flip Animation

Used when a face-down card is revealed (e.g. drawing from deck, enemy showing intent).

```tsx
// src/components/FramedCard.tsx — flip variant
import { motion, AnimatePresence } from 'motion/react';
import { useState } from 'react';

interface FlippableCardProps {
  card: Card;
  isRevealed: boolean;
}

export function FlippableCard({ card, isRevealed }: FlippableCardProps) {
  return (
    <div className="card-perspective-container">
      <motion.div
        className="framed-card"
        style={{ transformStyle: 'preserve-3d' }}
        animate={{ rotateY: isRevealed ? 0 : 180 }}
        transition={{
          type: 'spring',
          stiffness: 200,
          damping: 25,
          // Slightly slower than hover tilt — flip feels more deliberate
        }}
      >
        <div className="card-face card-face--front">
          <CardArtwork card={card} />
        </div>
        <div className="card-face card-face--back" />
      </motion.div>
    </div>
  );
}
```

---

## Performance on Mobile

### What to do

```typescript
// Detect touch/no-hover devices and disable tilt
const [isTouchDevice] = useState(
  () => window.matchMedia('(hover: none)').matches
);

// Also listen for changes (e.g. user connecting a mouse)
useEffect(() => {
  const mq = window.matchMedia('(hover: none)');
  const handler = (e: MediaQueryListEvent) => setIsTouchDevice(e.matches);
  mq.addEventListener('change', handler);
  return () => mq.removeEventListener('change', handler);
}, []);
```

### GPU property audit

| Property | Composited? | Notes |
|----------|-------------|-------|
| `transform: rotateX/Y/Z` | Yes | Core tilt — safe |
| `opacity` | Yes | Glare fade — safe |
| `transform: translateZ` | Yes | Glare z-offset — safe |
| `width`, `height` | No | Never animate these |
| `top`, `left`, `margin` | No | Never animate these |
| `border-radius` | No (triggers paint) | Set statically, don't animate |
| `filter: blur()` | Yes (separate layer) | Use sparingly — creates compositor layer |
| `will-change: transform` | — | Creates GPU layer; apply only during animation |

### Mobile-specific limits

- 3D transforms with `preserve-3d` create a stacking context and compositor layer for every card in the hand. On low-end mobile (< 2GB RAM), this can cause VRAM pressure if 7+ cards are all tilting simultaneously.
- `will-change: transform` on all hand cards at once is the most common cause of mobile jank. Apply it only on the card being hovered, remove it on `mouseleave`.
- For the game context: the hand typically has 3-7 cards. 3D tilt on all simultaneously is fine on mid-range mobile; on low-end, disable entirely via `(hover: none)`.

---

## Dynamic `will-change` via JavaScript

```typescript
// Apply will-change only while actively animating
const handleMouseEnter = useCallback(() => {
  if (!cardRef.current || isTouchDevice) return;
  cardRef.current.style.willChange = 'transform';
}, [isTouchDevice]);

const handleMouseLeave = useCallback(() => {
  if (!cardRef.current) return;
  // Remove after spring settles (~300ms at stiffness 300/damping 30)
  setTimeout(() => {
    if (cardRef.current) cardRef.current.style.willChange = 'auto';
  }, 400);
  rawRotateX.set(0);
  rawRotateY.set(0);
}, [rawRotateX, rawRotateY]);
```

---

## Framer Motion `useTransform` for Rarity Glow Intensity

The card's rarity glow can intensify as the card tilts, making rare cards feel more alive.

```tsx
import { useTransform, useSpring, useMotionValue } from 'motion/react';

const absRotate = useTransform(
  [rotateX, rotateY],
  ([rx, ry]: number[]) => Math.sqrt(rx * rx + ry * ry)
);

const glowIntensity = useTransform(absRotate, [0, MAX_TILT_DEG], [0.4, 1.0]);

// Apply to rarity glow filter
<motion.div
  className="rarity-glow"
  style={{ opacity: glowIntensity }}
/>
```

---

## Common Mistakes

### `perspective` on the card instead of the container
Each card with its own `perspective` has its own vanishing point, so cards in a fan layout will each tilt toward different horizons — looks wrong. Always set `perspective` on the parent container.

### Setting `rotateX`/`rotateY` inside `useState`/`useReducer`
Motion values update at 60fps during mousemove. Storing them in React state triggers 60fps re-renders, which kills performance. Always use `useMotionValue` — it updates the DOM directly without React reconciliation.

### Forgetting `backface-visibility: hidden` on both faces
Without `backface-visibility: hidden`, both front and back faces are visible simultaneously during the flip rotation. The back face bleeds through the front at 90deg.

### `transform-style: preserve-3d` missing on intermediate wrappers
If a parent element between the `perspective` container and the rotating card doesn't have `transform-style: preserve-3d`, 3D transforms flatten at that layer and the tilt stops working. Every element in the chain needs `preserve-3d`.
