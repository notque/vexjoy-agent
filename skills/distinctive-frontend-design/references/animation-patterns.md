# Animation Patterns for High-Impact Moments

## Philosophy

One well-orchestrated sequence > scattered micro-interactions

Focus animation effort on moments that matter:
- Initial page load (first impression)
- Major state transitions (empty → filled, loading → success)
- Feature showcases (pricing reveal, testimonial carousel)
- User achievements (form submission, milestone reached)

Reserve motion for moments that carry meaning. Not every hover state needs motion.

---

## Pattern 1: Orchestrated Page Load

### Hero Section Staggered Reveal

**Use case**: Landing pages, portfolio homepages, product launches

**Strategy**: Stagger element entrances with consistent timing intervals

```css
/* CSS Implementation */
.hero-title {
  animation: slide-up 0.8s cubic-bezier(0.22, 1, 0.36, 1);
  animation-delay: 0.2s;
  animation-fill-mode: both;
}

.hero-subtitle {
  animation: slide-up 0.8s cubic-bezier(0.22, 1, 0.36, 1);
  animation-delay: 0.4s;
  animation-fill-mode: both;
}

.hero-cta {
  animation: slide-up 0.8s cubic-bezier(0.22, 1, 0.36, 1);
  animation-delay: 0.6s;
  animation-fill-mode: both;
}

.hero-visual {
  animation: fade-in 1s cubic-bezier(0.22, 1, 0.36, 1);
  animation-delay: 0.8s;
  animation-fill-mode: both;
}

@keyframes slide-up {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes fade-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}
```

**React with Framer Motion**:

```jsx
import { motion } from "framer-motion";

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.2,
      delayChildren: 0.2
    }
  }
};

const itemVariants = {
  hidden: { opacity: 0, y: 30 },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      type: "spring",
      damping: 25,
      stiffness: 120
    }
  }
};

export function Hero() {
  return (
    <motion.section
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      className="hero"
    >
      <motion.h1 variants={itemVariants}>Your Title</motion.h1>
      <motion.p variants={itemVariants}>Your subtitle</motion.p>
      <motion.button variants={itemVariants}>CTA</motion.button>
      <motion.div variants={itemVariants}>Visual element</motion.div>
    </motion.section>
  );
}
```

**Timing**:
- Total sequence: 1.4s (0.2s start delay + 0.6s stagger + 0.8s animation)
- Stagger interval: 200ms between elements
- Animation duration: 800ms per element

---

## Pattern 2: State Transition Choreography

### Empty State → Filled Content

**Use case**: Dashboards, data tables, search results

**Strategy**: Smooth transition from empty state to populated content

```jsx
import { motion, AnimatePresence } from "framer-motion";

const listVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1
    }
  }
};

const itemVariants = {
  hidden: { opacity: 0, x: -20 },
  visible: {
    opacity: 1,
    x: 0,
    transition: {
      type: "spring",
      stiffness: 300,
      damping: 24
    }
  },
  exit: {
    opacity: 0,
    x: 20,
    transition: { duration: 0.2 }
  }
};

export function DataList({ items, isEmpty }) {
  if (isEmpty) {
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="empty-state"
      >
        <p>No items yet. Add your first item!</p>
      </motion.div>
    );
  }

  return (
    <motion.ul
      variants={listVariants}
      initial="hidden"
      animate="visible"
      className="data-list"
    >
      <AnimatePresence>
        {items.map((item) => (
          <motion.li
            key={item.id}
            variants={itemVariants}
            layout
          >
            {item.content}
          </motion.li>
        ))}
      </AnimatePresence>
    </motion.ul>
  );
}
```

---

## Pattern 3: Loading → Success Celebration

**Use case**: Form submissions, file uploads, payment processing

**Strategy**: Build anticipation with loading, release with success animation

```jsx
import { motion } from "framer-motion";

const loadingVariants = {
  initial: { rotate: 0 },
  animate: {
    rotate: 360,
    transition: {
      duration: 1,
      repeat: Infinity,
      ease: "linear"
    }
  }
};

const successVariants = {
  hidden: { scale: 0, opacity: 0 },
  visible: {
    scale: 1,
    opacity: 1,
    transition: {
      type: "spring",
      stiffness: 200,
      damping: 15
    }
  }
};

export function SubmissionState({ status }) {
  if (status === "loading") {
    return (
      <motion.div
        variants={loadingVariants}
        initial="initial"
        animate="animate"
        className="loading-spinner"
      >
        ⟳
      </motion.div>
    );
  }

  if (status === "success") {
    return (
      <motion.div
        variants={successVariants}
        initial="hidden"
        animate="visible"
        className="success-checkmark"
      >
        ✓
      </motion.div>
    );
  }

  return null;
}
```

**CSS-only alternative**:

```css
/* Loading state */
.loading-spinner {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* Success state */
.success-checkmark {
  animation: success-pop 0.6s cubic-bezier(0.68, -0.55, 0.265, 1.55);
}

@keyframes success-pop {
  0% {
    transform: scale(0);
    opacity: 0;
  }
  50% {
    transform: scale(1.2);
  }
  100% {
    transform: scale(1);
    opacity: 1;
  }
}
```

---

## Pattern 4: Scroll-Triggered Reveals

**Use case**: Long-form content, storytelling pages, feature showcases

**Strategy**: Elements animate into view as user scrolls

```jsx
import { motion } from "framer-motion";
import { useInView } from "framer-motion";
import { useRef } from "react";

export function ScrollReveal({ children }) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-100px" });

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 50 }}
      animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 50 }}
      transition={{
        duration: 0.8,
        ease: [0.22, 1, 0.36, 1]
      }}
    >
      {children}
    </motion.div>
  );
}
```

**CSS-only with Intersection Observer**:

```javascript
// JavaScript to add class when in view
const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("revealed");
      }
    });
  },
  { threshold: 0.1, rootMargin: "-100px" }
);

document.querySelectorAll(".reveal-on-scroll").forEach((el) => {
  observer.observe(el);
});
```

```css
.reveal-on-scroll {
  opacity: 0;
  transform: translateY(50px);
  transition: opacity 0.8s cubic-bezier(0.22, 1, 0.36, 1),
              transform 0.8s cubic-bezier(0.22, 1, 0.36, 1);
}

.reveal-on-scroll.revealed {
  opacity: 1;
  transform: translateY(0);
}
```

---

## Pattern 5: Interactive Hover Effects

**Use case**: Buttons, cards, navigation items (use sparingly!)

**Strategy**: Subtle, purposeful motion that enhances without distracting

```css
/* Lift effect for cards */
.card {
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1),
              box-shadow 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.15);
}

/* Scale effect for buttons */
.button {
  transition: transform 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.button:hover {
  transform: scale(1.05);
}

.button:active {
  transform: scale(0.98);
}

/* Underline animation for links */
.nav-link {
  position: relative;
}

.nav-link::after {
  content: '';
  position: absolute;
  bottom: -2px;
  left: 0;
  width: 0;
  height: 2px;
  background: var(--accent);
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.nav-link:hover::after {
  width: 100%;
}
```

---

## Easing Curves Reference

Choose easing based on animation purpose:

```css
/* Smooth deceleration (entrances) */
--ease-out: cubic-bezier(0.22, 1, 0.36, 1);

/* Smooth acceleration (exits) */
--ease-in: cubic-bezier(0.4, 0, 1, 1);

/* Standard easing (general purpose) */
--ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);

/* Elastic bounce (playful) */
--ease-elastic: cubic-bezier(0.68, -0.55, 0.265, 1.55);

/* Sharp snap (instant feedback) */
--ease-sharp: cubic-bezier(0.4, 0, 0.6, 1);
```

**When to use**:
- **Ease-out**: Element entering screen (slide-in, fade-in)
- **Ease-in**: Element exiting screen (slide-out, fade-out)
- **Ease-in-out**: Element moving within screen (position change)
- **Ease-elastic**: Success states, playful interactions
- **Ease-sharp**: Quick feedback (button press, toggle)

---

## Duration Guidelines

```css
/* Micro-interactions (hover, focus) */
--duration-fast: 150ms;

/* Standard transitions (most UI changes) */
--duration-normal: 300ms;

/* Slower transitions (page sections, major changes) */
--duration-slow: 500ms;

/* Orchestrated sequences (staggered reveals) */
--duration-sequence: 800ms;
```

**Rules of thumb**:
- Faster for frequent interactions (hover: 150-250ms)
- Medium for important feedback (button click: 300ms)
- Slower for high-impact moments (hero load: 500-800ms)
- Never exceed 1000ms for UI animations

---

## Performance Considerations

**Prefer animating these properties** (GPU-accelerated):
- `transform` (translate, scale, rotate)
- `opacity`
- `filter` (use sparingly)

**Prefer animating**:
- `width`, `height` (causes reflow)
- `top`, `left`, `right`, `bottom` (use `transform` instead)
- `margin`, `padding` (causes reflow)

**Best practices**:
```css
/* Good: GPU-accelerated */
.element {
  transform: translateY(20px);
  opacity: 0;
}

/* Bad: Causes layout thrashing */
.element {
  top: 20px;
  display: block;
}
```

**Reduce motion for accessibility**:
```css
@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## Animation Patterns to Detect and Fix

**Signals to avoid**:
- Animate every element on every page
- Use slow animations (>1000ms) for UI
- Ignore `prefers-reduced-motion`
- Animate layout properties (width, height, top, left)
- Add hover animations to touch devices
- Use animations that block user interaction

**Preferred action**:
- Focus on 1-2 high-impact moments per page
- Keep UI animations quick (150-500ms)
- Respect accessibility preferences
- Use `transform` and `opacity` only
- Disable hover effects on touch with `@media (hover: hover)`
- Allow users to interrupt/skip animations
