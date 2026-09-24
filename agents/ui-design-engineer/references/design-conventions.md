# Design Conventions

<!-- Loaded by ui-design-engineer when task involves Tailwind, frontend tokens, theme config, spacing scales, or starting a new surface -->

House conventions for tokens, Tailwind, and how to open a design task. Tailwind utility syntax and CSS custom property syntax are assumed known.

---

## Opening a Surface (Phase 1: ANALYZE)

Before writing any markup:

- Classify surface type: landing page or app/dashboard
- Write the narrative brief: visual thesis, content plan, interaction thesis
- Confirm real content is available (hero headline, product name, single promise)

A surface designed against lorem ipsum gets lorem ipsum hierarchy. If the real content does not exist yet, that is a blocker worth naming, not a gap to fill with placeholder text.

## Tokens

- When a color, spacing value, or font appears more than once, add it to `tailwind.config.js` as a named token. Use arbitrary values (`[#1a237e]`) only for one-off layout values that appear exactly once.
- **Choose the font token for the surface.** Tools: a neutral sans (`system-ui` stack, Inter, Geist) is the right default. Brand pages: a face chosen for the brand. See the font section of `ai-slop-detection.md`.
- Colors in a token set trace to a source: brand guide, an existing design system, or a deliberate harmony relationship. Start with tinted neutrals plus one accent (`skills/shared-patterns/ui-design-judgment.md` section 5).
- Spacing snaps to a 4px grid (4, 8, 12, 16, 20, 24, 32, 40, 48, 64). `1px` and `2px` are structural (borders, dividers, outlines), not spacing.

```bash
python3 scripts/design-scale-check.py path/to/styles.css   # flags px values off the 4px grid
```

## Tailwind: The Dynamic Class Trap

> **Version range**: Tailwind CSS v3.0+ — verify against current v3/v4 release notes.

Never build class names by interpolation:

```jsx
// Broken — renders unstyled
<div className={`text-${color}-500`} />
```

**Why this matters**: Tailwind's content scanner extracts class names at build time by looking for complete strings. Partial strings like `` `text-${'red'}-500` `` are never seen as `text-red-500` — the final class does not exist in the generated CSS and renders as unstyled. This affects both v3 (`content` config) and v4 (Vite plugin).

Map variants to complete class strings instead, so the scanner sees each one literally.

## Accessibility Floor

These are non-negotiable and are checked before a surface is considered done:

- Contrast meets WCAG 2.1 AA (4.5:1 body text, 3:1 large text and UI boundaries)
- Every interactive element is reachable and operable by keyboard, with a visible `:focus-visible` ring
- Meaning is never carried by color alone
- Modals trap focus and restore it to the trigger on close
- `prefers-reduced-motion` is honored
- A skip link precedes the main landmark
