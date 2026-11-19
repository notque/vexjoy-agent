# UI Design Implementation

Visual UI/UX implementation: accessible UI with design tokens, Tailwind themes, reusable components, and clear visual hierarchy. Mobile-first layouts, responsive images, touch targets, reduced-motion support. Provide loading, error, and success states. Lazy-load images and minimize layout shifts.

Not for: API, schema, or system design; design docs (a workflow skill); design methodology, user-research analysis, or accessibility audit documentation (DESIGN mode in this skill); combat visual effects and animation juice (`skills/game/game-dev/references/combat-effects-upgrade.md`).

## Hard rules (always apply)

- **Read before editing.** Never edit a file you have not read in this session.
- **Look, then fix, before reporting done.** Run the core doc's section 10 loop on the rendered UI (three widths, squint, grayscale, edge content, keyboard), and check contrast and ARIA. Do not declare done without that evidence.
- **Feature branch, never main.** If on main, create a branch before committing.
- **Verify dependencies before importing.** Check `package.json` for Framer Motion, Tailwind, and others before adding imports.
- **WCAG 2.2 AA:** contrast 4.5:1 normal text, 3:1 large text; keyboard navigation with a focus indicator that sticky content does not hide; pointer targets at least 24x24 CSS px; screen reader support.
- **Semantic HTML:** `button`, `nav`, `main`, `article`, not divs with event handlers.
- **Focus indicators:** visible focus on every interactive element.
- **Responsive by default:** mobile-first with breakpoints sm 640px, md 768px, lg 1024px, xl 1280px.
- **Reduced motion:** respect `prefers-reduced-motion`.

## Design defaults (override with a stated reason)

Read `skills/shared-patterns/ui-design-judgment.md` before any design work; it holds the defaults for hierarchy, spacing, type, color, states, and the look-then-fix loop. Take starting values from `ui-design-recipes.md` in the same folder. For deeper aesthetic work on brand pages, use DISTINCTIVE mode in this skill.

- **Classify the surface first:** tool (dashboard, admin, editor) or brand page (landing, launch, portfolio). Every later choice depends on it.
- **Write the brief from the request:** visual thesis, content plan (sections in order, one job each), and the few motions that matter. Ask only when real content (product name, headline, main action) is missing.
- **Real content over placeholders.** Mark missing content as a visible placeholder.
- **Type:** one neutral family for tools; display plus text face for brand pages. A third family needs a reason.
- **Color:** tinted neutrals plus one brand accent; status colors are separate and always paired with an icon or text.

**Brand pages:**
- The first viewport reads as one composition: product name at hero scale, one promise, one primary action.
- Full-bleed hero by default. A hero in a shadowed card reads as a dashboard tile; use a card only when the card is the product.
- Common sequence: hero, supporting imagery, product detail, proof, final action. Change it when the content calls for it.
- Motion: 2-3 intentional motions (entrance, scroll, interaction) is a good budget.

**Tools:**
- Calm surfaces, strong type, tight spacing, few colors. Dense but readable: users scan headings, labels, and numbers.
- Cards only when the card is the interaction (selectable item, sortable row, drag target); group with spacing otherwise.
- Motion only for state changes: focus, row expand, drawer slide.

## Defaults (on unless disabled)

- **Design tokens:** Tailwind config or CSS variables for colors and spacing.
- **Loading states** for async operations.
- **Error states:** user-friendly messages with recovery actions.
- **Hover states** on interactive elements.

## Optional (off unless enabled)

- Complex animations: only when micro-interactions clearly help UX.
- Custom themes: only when brand customization is required.
- Dark mode: only when requested.
- WCAG AAA: only when specified.

## Implementation details

Use Tailwind themes or CSS variables for colors, fonts, and spacing. Build reusable components with size, color, and state variants. Support composition and extraction with `@apply`. Document the design system.

Use `clamp()` for fluid type, `srcset` for responsive images, and touch targets of at least 44x44px. Test ARIA labels and roles with a screen reader. Use loading skeletons where they fit.

Out of scope: logos and brand identity, usability testing and interviews, custom illustrations or icons, marketing copy. Hand these to the right specialist.

For type-safe component architecture, state, and build config, load `typescript-frontend.md`.

## Output format

Implementation schema: ANALYZE (surface type, brief, content, requirements), DESIGN (Tailwind theme, component architecture, motion), IMPLEMENT (tokens, accessible components, responsive layout), LOOK AND FIX (core doc section 10, plus screen reader). Brief and token, Tailwind, and accessibility conventions: `ui-design/design-conventions.md`.

## Reference loading table

| Signal | Load | Why |
|---|---|---|
| Any design work: new screen, restyle, layout, critique (load first) | `skills/shared-patterns/ui-design-judgment.md`, then `ui-design-recipes.md` and `ui-design-examples.md` in the same folder | Defaults with reasons, starting values, before/after fixes, look-then-fix loop |
| design tokens, theme, CSS variables, color palette, font scale, Tailwind config, arbitrary values, spacing scale, accessibility floor, starting a surface | `ui-design/design-conventions.md` | Token and font house rules, 4px grid, Tailwind dynamic-class trap, WCAG floor, Phase 1 ANALYZE |
| animation, Framer Motion, transition, reduced motion, AnimatePresence, interaction states, hover, focus, disabled, loading, active, pressed | `ui-design/motion-and-interaction.md` | Motion budget, 6-state matrix, timing bounds, 5-second test, error-fix mappings |
| AI slop, generic UI, AI-generated look, template look, default styling | `ui-design/ai-slop-detection.md` | Purposeful gradients, contextual fonts and colors, spacing scale rules, detection commands |
| text/headline/label/microcopy animation | `distinctive-frontend-design-refs/roll-text.md` | Zero-npm roll/slot text pattern: standalone demo, extraction guide, knobs |

## Common errors

| Error | Cause | Fix |
|---|---|---|
| Low color contrast | Text misses WCAG 4.5:1 | Check with a contrast checker; adjust to meet AA |
| Missing focus indicators | `outline: none` with no custom focus style | Always provide a visible ring, border, or background change |
| Non-semantic HTML | Divs with `onClick` instead of buttons | Use `button`, `nav`, `main`, `article` |

## Preferred patterns

| Instead of | Why wrong | Do |
|---|---|---|
| `button:focus { outline: none; }` | Hides keyboard position | Custom focus style with ring or border |
| `<div onClick={handleClick}>Click me</div>` | No keyboard or screen-reader support | `<button onClick={handleClick}>Click me</button>` |
| `font-size: 16px;` | Ignores user font-size preference | `rem` units or Tailwind text classes |

## Anti-rationalization

| Rationalization | Why it's wrong | Required action |
|---|---|---|
| "Divs with onClick work fine" | Not keyboard accessible | Use semantic button elements |
| "Focus outlines are ugly" | Required for keyboard navigation | Provide custom focus styles |
| "Animations enhance every interaction" | Can trigger vestibular disorders | Respect `prefers-reduced-motion` |
| "Placeholder text is fine for now" | Placeholder text produces placeholder thinking | Get real content before building |
| "A card in the hero gives it structure" | A card demotes the hero to a dashboard tile | Remove the card; let the product speak |
| "Three typefaces gives hierarchy" | Three families fight each other | Cut to two families or use weight variation on one |
| "Two accent colors create visual interest" | Competing accents dilute hierarchy | Pick one accent; keep functional colors separate |
| "Animating everything feels alive" | Decorative motion is noise; hierarchy is lost | Keep motion that explains a change; 2-3 on brand pages |
| "It compiles, so the design is done" | Layout, hierarchy, and contrast problems show only in the render | Run the look-then-fix loop before reporting |
| "This dashboard needs more gradients" | Decorative gradients belong on landing pages, not apps | Apply Linear-style restraint in apps |
| "Cards everywhere in the dashboard" | In apps, cards are valid only when the card is the interaction; decorative cards make card mosaics | Strip cards in apps unless users interact with the card. On landing pages the no-cards-in-hero rule applies separately to the first viewport |
| "Client brand guide says two accents, but the rule is one" | Defaults bend to an explicit brand guide | Follow the guide and note the override in the spec |

## Blocker criteria

Resolve routine issues from repository evidence. When you are sure, decide, record the assumption, and continue; ask Jev when genuinely unsure. Ask the user only when these leave a material decision open.

Skip-if-answered: if the request already answers a question, do not re-ask. Example: "build a landing page for Acme with hero headline X" already answers surface type and product name.

| Situation | Why stop | Ask |
|---|---|---|
| Surface type unclear | Landing page vs app decides every later rule | "Is this a landing page or an app/dashboard?" |
| Real content missing | Placeholder text produces placeholder thinking | "Can you share the real copy, product name, and hero imagery? At minimum the hero headline, product name, and the single promise." |
| Brand colors unclear | Color affects the whole design | "Do you have brand colors or should I suggest a palette?" |
| Dark mode requested, no preference | Different strategies | "System-based dark mode or toggle switch?" |
| Animation level unclear | Simple vs complex | "Subtle micro-interactions or prominent animations?" |
| Accessibility level unclear | AA and AAA differ | "WCAG 2.2 AA (standard) or AAA (stricter)?" |

Verify before assuming: surface type, real hero content, brand palette, dark mode strategy, animation intensity, WCAG level.

Shared patterns: [anti-rationalization-core.md](../../../shared-patterns/anti-rationalization-core.md), [verification-checklist.md](../../../shared-patterns/verification-checklist.md).
