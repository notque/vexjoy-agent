# Animation Patterns Reference
<!-- Loaded by ui-design-engineer when task involves Framer Motion, CSS transitions, micro-interactions, loading states, or prefers-reduced-motion -->

> **Scope**: Framer Motion and CSS animation patterns for accessible, intentional UI motion. Covers reduced-motion, exit animations, and the 2-to-3 motion discipline rule.
> **Version range**: Framer Motion 10+ (React 18+)
> **Generated**: 2026-04-15

The most common animation failures are: ignoring `prefers-reduced-motion` (triggers vestibular disorders), shipping more than 3 animations per page (destroys hierarchy), and missing `AnimatePresence` for exit animations (element vanishes without transition).

---

## Pattern Table

| Pattern | Version | Use When | Avoid When |
|---------|---------|----------|------------|
| `useReducedMotion()` hook | Framer Motion 4+ | Detecting user preference inside a component | Checking media query directly with `window.matchMedia` |
| `AnimatePresence` wrapper | Framer Motion 1+ | Any element that conditionally mounts/unmounts | Element is always visible; adds unnecessary overhead |
| `layout` prop on `motion.div` | Framer Motion 2+ | Animating list reorders, dynamic height changes | Static layouts; triggers expensive layout recalculations |
| CSS `transition` | all | Simple hover/focus state changes (color, opacity, border) | Complex keyframe sequences or coordinated multi-element animations |

---

## Correct Patterns

### Respecting `prefers-reduced-motion` with Framer Motion

Use the `useReducedMotion()` hook to build a variants object that conditionally disables motion. Never skip this — WCAG 2.3.3 Success Criterion (AAA) and best practice for AA.

```tsx
import { motion, useReducedMotion } from 'framer-motion'

function FadeInCard({ children }: { children: React.ReactNode }) {
  const shouldReduceMotion = useReducedMotion()

  const variants = {
    hidden: { opacity: 0, y: shouldReduceMotion ? 0 : 20 },
    visible: { opacity: 1, y: 0 },
  }

  return (
    <motion.div
      variants={variants}
      initial="hidden"
      animate="visible"
      transition={{ duration: shouldReduceMotion ? 0 : 0.3 }}
    >
      {children}
    </motion.div>
  )
}
```

**Why**: `useReducedMotion()` subscribes to `prefers-reduced-motion: reduce` media query reactively. Setting `duration: 0` and `y: 0` means the element appears instantly without jarring users with vestibular disorders.

---

### Exit Animations with `AnimatePresence`

`AnimatePresence` is required for exit animations to run. Without it, the component unmounts before Framer Motion can animate the exit.

```tsx
import { AnimatePresence, motion } from 'framer-motion'

function Toast({ message, visible }: { message: string; visible: boolean }) {
  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          key="toast"
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}  // requires AnimatePresence parent
          transition={{ duration: 0.2 }}
          role="status"
          aria-live="polite"
        >
          {message}
        </motion.div>
      )}
    </AnimatePresence>
  )
}
```

**Why**: When `visible` flips to `false`, React would normally unmount immediately. `AnimatePresence` delays the unmount until the `exit` animation completes.

---

### The 2-to-3 Motion Rule (Three Slots Per Page)

Ship exactly two or three intentional motions per page. Each motion fills one slot:

```tsx
// Slot 1: ENTRANCE — one hero entrance on load
const heroVariants = {
  hidden: { opacity: 0, y: 30 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5 } },
}

// Slot 2: SCROLL — one scroll-linked effect (use Framer Motion's useScroll)
import { useScroll, useTransform } from 'framer-motion'
function ParallaxSection() {
  const { scrollY } = useScroll()
  const y = useTransform(scrollY, [0, 500], [0, -80])
  return <motion.div style={{ y }}>...</motion.div>
}

// Slot 3: INTERACTION — one hover/focus/layout transition
<motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
  Submit
</motion.button>
```

**Why**: More than three motions compete for attention. Each additional animation dilutes the signal value of all others. The page feels "jumpy" rather than intentional.

---

## Pattern Catalog

### ❌ Missing `prefers-reduced-motion` Support

**Detection**:
```bash
# Find motion components without reduced-motion handling
grep -rn "motion\." --include="*.tsx" | grep -v "useReducedMotion\|prefers-reduced"
# Find CSS transitions without reduced-motion media query
grep -rn "transition:" --include="*.css" --include="*.tsx" | grep -v "prefers-reduced"
# Check for CSS @media prefers-reduced-motion
grep -rn "prefers-reduced-motion" --include="*.css"
```

**What it looks like**:
```tsx
// WRONG: No check for user preference
<motion.div
  initial={{ opacity: 0, y: 40 }}
  animate={{ opacity: 1, y: 0 }}
  transition={{ duration: 0.6 }}
>
```
```css
/* WRONG: No reduced-motion override */
.card {
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}
.card:hover {
  transform: translateY(-4px);
}
```

**Why wrong**: Users with vestibular disorders (motion sickness, Meniere's disease) can experience nausea or disorientation from unnecessary motion. `prefers-reduced-motion: reduce` is a system-level accessibility setting.

**Fix**:
```tsx
// Framer Motion: use hook
const shouldReduceMotion = useReducedMotion()
<motion.div
  initial={{ opacity: 0, y: shouldReduceMotion ? 0 : 40 }}
  animate={{ opacity: 1, y: 0 }}
  transition={{ duration: shouldReduceMotion ? 0 : 0.6 }}
>
```
```css
/* CSS: add @media override */
.card {
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}
.card:hover {
  transform: translateY(-4px);
}
@media (prefers-reduced-motion: reduce) {
  .card { transition: none; }
  .card:hover { transform: none; }
}
```

---

### ❌ Exit Animation Not Running (Missing `AnimatePresence`)

**Detection**:
```bash
# Find conditional motion elements without AnimatePresence wrapping
grep -rn "exit={{" --include="*.tsx"
# If exit prop exists but no AnimatePresence in the same file, that's the bug
grep -rn "exit={{" --include="*.tsx" | xargs grep -L "AnimatePresence"
```

**What it looks like**:
```tsx
// WRONG: exit prop present but AnimatePresence is absent — exit never runs
{isOpen && (
  <motion.div
    initial={{ opacity: 0 }}
    animate={{ opacity: 1 }}
    exit={{ opacity: 0 }}  // silently ignored
  >
    Modal content
  </motion.div>
)}
```

**Why wrong**: React unmounts the component synchronously when `isOpen` becomes `false`. By the time Framer Motion would start the exit animation, the element is already gone from the DOM.

**Fix**:
```tsx
import { AnimatePresence, motion } from 'framer-motion'

<AnimatePresence>
  {isOpen && (
    <motion.div
      key="modal"  // key is required for AnimatePresence to track the element
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      Modal content
    </motion.div>
  )}
</AnimatePresence>
```

**Version note**: `AnimatePresence` requires a `key` prop on direct children to track mount/unmount identity correctly. Without `key`, re-renders may not trigger exit animations.

---

### ❌ Animating Everything (Motion Overload)

**Detection**:
```bash
# Count motion. components per file — flag files with more than 6
grep -c "motion\." --include="*.tsx" $(find . -name "*.tsx") 2>/dev/null | awk -F: '$2 > 6 {print $1": "$2" motion components"}'
# Or with rg
rg "motion\." --type tsx -c | awk -F: '$2 > 6'
```

**What it looks like**:
```tsx
// WRONG: Every element has entrance animation — hierarchy collapses into noise
<motion.nav initial={{ y: -20 }} animate={{ y: 0 }}>
  <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
    <motion.ul initial={{ x: -10 }} animate={{ x: 0 }}>
      {items.map(item => (
        <motion.li key={item.id} whileHover={{ scale: 1.05 }}>
          <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            {item.label}
          </motion.span>
        </motion.li>
      ))}
    </motion.ul>
  </motion.div>
</motion.nav>
```

**Why wrong**: When everything animates, nothing communicates. The brain uses motion as a signal for hierarchy and importance. Saturating the page with motion degrades every motion's signal value to zero.

**Fix**: Apply the 2-to-3 rule. Audit existing motion and remove any that aren't filling one of the three slots (entrance, scroll, interaction). Use `variants` with `staggerChildren` to coordinate list animations as a single entrance slot:

```tsx
// CORRECT: One entrance slot using stagger — nav entrance counts as one motion
const containerVariants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.05 } },
}
const itemVariants = {
  hidden: { opacity: 0, y: 8 },
  visible: { opacity: 1, y: 0 },
}

<motion.ul variants={containerVariants} initial="hidden" animate="visible">
  {items.map(item => (
    <motion.li key={item.id} variants={itemVariants}>
      {item.label}
    </motion.li>
  ))}
</motion.ul>
```

---

### ❌ Using `whileHover` on Non-Interactive Elements

**Detection**:
```bash
# Find whileHover on non-interactive elements (div, span, p)
grep -rn "whileHover" --include="*.tsx" | grep "motion\.div\|motion\.span\|motion\.p"
```

**What it looks like**:
```tsx
// WRONG: hover animation on non-interactive element confuses keyboard users
<motion.div whileHover={{ scale: 1.02 }} className="card">
  {content}
</motion.div>
```

**Why wrong**: `whileHover` triggers on CSS `:hover`, not on keyboard focus. A card with hover animation but no `tabIndex` and no focus animation is inaccessible — keyboard users get no feedback and may not know the element is interactive.

**Fix**:
```tsx
// CORRECT: Use interactive element with both hover and focus states
<motion.button
  whileHover={{ scale: 1.02 }}
  whileFocus={{ scale: 1.02 }}   // match hover behavior for keyboard users
  className="card focus:outline-none focus:ring-2 focus:ring-blue-500"
>
  {content}
</motion.button>
```

---

## Error-Fix Mappings

| Symptom | Root Cause | Fix |
|---------|------------|-----|
| Exit animation doesn't run — element disappears instantly | `AnimatePresence` missing as ancestor | Wrap conditional `motion.*` element with `<AnimatePresence>` and add `key` prop |
| Animation runs in dev but skipped for some users | `prefers-reduced-motion: reduce` active | Add `useReducedMotion()` hook and set `duration: 0` / zero offsets when true |
| `staggerChildren` has no effect | Variants not propagated — child elements lack `variants` prop | Add matching `variants` prop to all child `motion.*` elements |
| Layout animation causes "jump" | `layout` prop on element with `position: absolute` children | Wrap absolute children in `motion.div` with `layout` or use `layoutId` instead |
| Animation works once, breaks on re-render | `key` not stable — component remounts every render | Ensure `key` on `AnimatePresence` children is stable (id, not array index) |

---

## Detection Commands Reference

```bash
# Missing prefers-reduced-motion in motion components
grep -rn "motion\." --include="*.tsx" | grep -v "useReducedMotion"

# Exit animations without AnimatePresence
grep -rn "exit={{" --include="*.tsx" | xargs grep -L "AnimatePresence" 2>/dev/null

# Motion overload (>6 motion components per file)
rg "motion\." --type tsx -c | awk -F: '$2 > 6'

# whileHover on non-interactive elements
grep -rn "whileHover" --include="*.tsx" | grep "motion\.div\|motion\.span\|motion\.p"

# CSS animations missing reduced-motion override
grep -rn "transition:" --include="*.css" | xargs grep -L "prefers-reduced-motion" 2>/dev/null
```

---

## See Also

- `accessibility-patterns.md` — WCAG compliance patterns including focus management
- `component-library-interactive.md` — Button/modal interaction patterns with accessible focus handling
