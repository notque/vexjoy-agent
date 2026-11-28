# UI design judgment

Read this before any UI work: new screens, restyles, critiques, HTML artifacts, slides, component plans. It is the judgment the other UI references assume. Everything here is a default with a reason. Break a default when you can name the reason it does not apply to this product.

This guide is web-first. On native platforms (iOS, Android, desktop apps), the platform's own guidelines win where they differ: for example 44 pt targets on iOS, 48 dp on Android, and native navigation patterns.

Good UI comes from three things, in order: the right content, a clear hierarchy, and consistent spacing and type. Color, motion, and effects come last and matter least. Most weak designs fail at step one or two and try to fix it at step three.

## 1. Start from the job and the real content

- Name the one job this screen does and the one action that matters most. If you can't, the screen does too much; split it or ask.
- Design with real or realistic content: real names, real lengths, real numbers, the longest label. Lorem ipsum and "Item 1" hide every layout problem.
- Match the surface and opening format. Tools and content formats (dashboards, admin, editors, news, docs, directories, resumes) open directly into live content with zero marketing hero banner. Hero-led brand or launch pages abandon the generic 50/50 left-text / right-media split for full-width or depth compositions, pair the headline with at most 25 words of supporting copy and one primary CTA, and omit 3-column or 4-column KPI/spec footer strips.
- Build what the brief asks for, all of it, and nothing it doesn't. Every field, column, section, and state the brief names must appear. Omit invented features, plans, roles, prices, legal details, or claims; if the design needs one, add a visibly marked placeholder (`[Needs real value]`).
- Use the conventions users already know for the platform and the pattern. Put originality in the parts that carry the brand, not in navigation, forms, or tables.

## 2. Hierarchy: make one thing win

- Each view has one primary element and one primary action. Everything else steps down.
- Build hierarchy with size, weight, and position first, and color last. Test: in grayscale, is the order still obvious?
- De-emphasize to emphasize. Mute secondary text, shrink metadata, and turn secondary buttons into ghost or link styles, instead of making the primary thing louder.
- Keep at most one primary CTA button per region or section. Destructive actions are never the most prominent button unless deleting is the task. For mode, filter, or size selection, use segmented toggles, tabs, radios, switches, `<select>`, or canvas interaction instead of button walls.
- Start sections directly with `<h1>` or `<h2>` (omit `.eyebrow`/`.kicker` labels, decorative `01`/`02`/Roman heading prefixes, and non-interactive chips, badges, or category tags).
- Group by proximity: space inside a group is smaller than space between groups. This does more than borders, boxes, and dividers, which you should remove when spacing already separates the groups.

## 3. Spacing and layout

- Use one spacing scale (4 or 8 px based: 4, 8, 12, 16, 24, 32, 48, 64) and nothing between the steps.
- Align everything to a few edges. Ragged left edges look broken even when each part looks fine.
- Start with more whitespace than feels needed, then tighten. Crowding is the usual failure; emptiness rarely is.
- Keep prose to 60-65 characters per line (`<= 65ch`). Full-width paragraphs on desktop are hard to read.
- Use one level of container; omit nested card-in-card cages. Inside a container, separate groups with spacing and type.
- Design the smallest screen first for anything public. Check at 375 (or 390), 768, and 1280 px wide.
- At 375 px the page must never scroll sideways. Wrap every table and wide element in a container with `overflow-x: auto`, give flex and grid children `min-width: 0`, and let long words break (`overflow-wrap: anywhere` on names, emails, URLs).
- Navigation must stay reachable on phones. When a sidebar hides below 768 px, add a menu button in the header that opens it as a sheet or drawer.

## 4. Typography

- Use at most two font families: one versatile sans for product UI, or a purposeful display-plus-body pair for expressive pages. A well-made system or neutral sans (platform UI font, Inter, Geist) is a good default for tools.
- Lock body copy below the hero to at most 3 font-size tokens (`--text-heading`, `--text-body`, `--text-sm`); add a 4th step only when a dense dashboard or data table requires it. Hero `<h1>` and the navbar wordmark sit outside this ceiling. Ship zero text under `13px` (`0.8125rem`) above the fold.
- Keep body paragraphs and bullet or numbered lists at one uniform scale (no oversized `.lead` paragraph above smaller text, no shrunk lists). Body text 16 px on the web; 14 px is fine for dense tools.
- Line height about 1.5 for body text and 0.95-1.2 for headings. Tighten letter spacing (`-0.02em` to `-0.05em`) on large display headings; never on small text.
- Differentiate `<h3>`, buttons, and labels via weight, family, or color (two or three weights, not five). Set UI labels and table headers in sentence case.
- Use `font-variant-numeric: tabular-nums` in the primary sans for aligned or changing numbers (tables, prices, timers) instead of adding a 3rd monospace font unless building code, docs, or terminal tools. Right-align numeric columns.

## 5. Color

- A pure white background is fine in light mode; off-white is a brand choice, not a rule.
- Start neutral and tint grays slightly toward the brand hue so they stay cohesive. When aesthetic is open, skip both dark slate plus neon purple glow and warm beige/cream plus rust/terracotta overcorrection; derive palette from the subject's real materials and audience.
- Color carries meaning: the primary action, links, selection, and status. If a color means nothing, it is decoration; remove it or make it quieter.
- Pick one brand accent and use it sparingly. Status colors (success, warning, danger) are separate and always pair with an icon or text.
- Contrast: 4.5:1 for body text, 3:1 for large text and UI boundaries. Check the actual pairs, especially muted text, placeholders, and text on colored buttons.
- Define color as tokens (background, foreground, muted, border, primary) and build dark mode from its own values: slightly lighter surfaces for elevation, less saturated accents, no pure black under pure white text. An inverted light theme is not a dark theme.
- In a standalone HTML file, put the dark values in `@media (prefers-color-scheme: dark) { :root { ... } }` so dark mode works with no toggle. In a React or shadcn app, use the `.dark` class and the app's theme switcher. Ship dark mode by default unless the brief rules it out.
- OKLCH makes even steps and matched hues easy when you build a scale.

## 6. Components and states

- Use the component library's existing parts and variants before inventing new ones. Consistency beats local cleverness.
- Every data view needs its states designed: loading (skeletons shaped like the content), empty (says why and what to do next), error (what happened and how to fix it), and overflow (long names, many items, zero items).
- Every interactive element needs hover, focus-visible, active, and disabled states. Focus rings must be visible; never remove them without a replacement. Default: `outline: 2px solid var(--ring); outline-offset: 2px` on `:focus-visible`.
- Exact defaults for tools: table rows 40-48 px (32-36 when density matters most), controls 36 px, icons 16 px inline and 20 px standalone, font stack `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif` when no brand font is given.
- Placeholders show the format, never a realistic value: `name@example.com`, `MM / YY`, not "Jane" or "Portland", which look like filled-in answers. Many fields need no placeholder at all.
- Touch targets at least 44 x 44 px. Forms: labels above fields, errors next to the field, the submit button says what it does ("Create invoice", not "Submit").
- Charts: follow the chart defaults in `ui-design-recipes.md`; for deeper chart work use the data-viz guidance available in your harness.
- Icons support labels; they rarely replace them. Use one icon set at one stroke weight. In a standalone HTML file, draw icons as inline SVG (for example Lucide paths, `stroke="currentColor"`, 16-20 px). Never use emoji or an icon font as icons: they render as empty boxes when the font is missing.

## 7. Depth, motion, and effects

- Prefer borders or small surface-color shifts to shadows in dense UI. Save shadows for things that float: menus, popovers, dialogs.
- Keep one radius family (for example 6 px controls, 8-12 px containers). Nested corners look right when the inner radius equals the outer radius minus the padding.
- Motion explains a change: where something came from, what changed, what is loading. Use brisk transitions (`140-240 ms`, `cubic-bezier(0.22, 1, 0.36, 1)`) on explicit properties (`transform`, `opacity`, `clip-path`). Never write `transition: all`, Tailwind `transition-all`, or `ease-in` on UI transitions. Respect `prefers-reduced-motion`.
- Content must be visible with no JavaScript and no animation. Never ship CSS that starts sections at `opacity: 0` and waits for a scroll observer to reveal them: if the script fails, the observer doesn't fire, or the page is printed or screenshotted, the section is blank. Animate only with a class that JavaScript adds, and only inside `@media (prefers-reduced-motion: no-preference)`.
- Gradients, glass, glow, grain, and 3D are seasoning. Use one, on purpose, where it supports the brand, and never where it lowers text contrast.

## 8. Copy is design

- Write the real words. Benefit-led headlines say what the thing does for this user, in their terms (avoid spec-only labels or `<br><em>` italic splits). Buttons name the outcome.
- Cut words until the meaning breaks, then add one back. Omit em-dashes and spaced en-dashes in generated UI copy (preserve user-supplied text verbatim).
- Never invent metrics, testimonials, logos, or user counts. Use a clearly marked placeholder instead.

## 9. Tells of generated UI

These patterns mark a design as default output. Replace them with deliberate choices:

| Tell | Instead |
|---|---|
| Dark slate + neon purple-blue gradients, or warm beige/cream + rust/terracotta overcorrection | Subject-fit palette derived from real materials and audience |
| 50/50 split hero, 3-4 column KPI strip, three feature cards in a row, repeat | Full-width or depth hero (<= 25 words, 1 CTA) on brand pages; direct live content on tools |
| `.eyebrow`/`.kicker` labels, `01`/`02` prefixes, decorative non-interactive chips/badges/tags | Direct `<h1>`/`<h2>` headings, plain metadata, or real interactive filters |
| Button walls for mode, filter, or size selection | One primary CTA per section; toggles, tabs, radios, switches, or `<select>` for choices |
| Emoji as icons; an icon on every heading and bullet | One inline SVG icon set, used where it aids scanning |
| Nested card-in-card cages with shadow, border, and big radius on everything | One container level; spacing and typography for grouping |
| Mixed micro-sizes (< 13px above fold), oversized `.lead`, shrunk lists, 3rd monospace font | 3-size body scale, uniform paragraph/list size, `tabular-nums` in primary sans |
| `transition: all` / `transition-all`, `ease-in`, scroll-hidden `opacity: 0` sections | Explicit `transform`/`opacity`/`clip-path` at `140-240 ms` `cubic-bezier(0.22, 1, 0.36, 1)` |
| Fake stats, testimonials, logos, or `"Get started"` / `"Learn more"` / `"Submit"` | Real data or marked placeholder; outcome-named button labels |

## 10. Look, then fix

Code that compiles is not a finished design. Render it and look.

1. **Render.** Use whatever the harness has: Playwright, chrome-devtools, a browser screenshot tool, or an HTML preview. If none exists, say so and list what the user should check by eye.
2. **Check at three widths** (375 or 390x844 mobile, 768, 1280 desktop) at true desktop height, and in light and dark mode. Inspect both the opening viewport and scrolled below-the-fold sections so lazy content loads and blank bands are caught.
   Run this in the page (Playwright `evaluate`, DevTools console) at each width; every value should be empty or false:

   ```js
   ({
     sideScroll: document.documentElement.scrollWidth > innerWidth,
     hidden: [...document.querySelectorAll('section, main > *')].filter(e => getComputedStyle(e).opacity === '0').map(e => e.className || e.tagName),
     noLabel: [...document.querySelectorAll('input, select, textarea')].filter(e => e.type !== 'hidden' && !e.labels?.length && !e.getAttribute('aria-label')).map(e => e.name || e.id || e.type),
     tinyTargets: [...document.querySelectorAll('button, a, [role=button]')].filter(e => { const r = e.getBoundingClientRect(); return r.width && r.height < 24; }).length,
   })
   ```
3. **Squint test.** Blur your view or shrink the screenshot. The primary element and action should still stand out. If everything is the same gray mass, fix the hierarchy.
4. **Grayscale test.** The order of importance should hold without color.
5. **Edge test.** Load empty, long, and error content. Tab through the page with the keyboard.
6. **Fix the biggest problem first**, in this order: content and job, hierarchy, spacing and alignment, type, color, polish. Re-render after each round. Stop after about three rounds or when the remaining issues are taste, not problems, and report what you'd try next.

Describe findings concretely: element, problem, effect, fix. "The two buttons in the header compete: both are solid primary. Make Export a ghost button." Not "the header could be cleaner."

## Before you hand it over

Answer each with yes, or fix it first:

1. Does every item the brief names appear (fields, columns, sections, states), with nothing invented?
2. Is there one clear primary action per view, named for its outcome, with non-button selection controls?
3. Do the squint and grayscale tests show the right order of importance, using at most 3 body type sizes and zero `< 13px` text above the fold?
4. At 375/390 px: no sideways scroll, navigation reachable, targets at least 44 px?
5. Does dark mode work, with readable muted text?
6. Is every section visible without scrolling animations or JavaScript, with explicit CSS transitions (zero `transition: all`)?
7. Do empty, loading, error, and long-content states exist where data appears?
8. Are all icons inline SVG, with no emoji, icon-font boxes, decorative chips, or eyebrow clutter?
9. Did you check desktop (opening + scrolled below fold) and mobile renders yourself, not only the code?

## When you're a weaker model or unsure

- Examples in these guides show the shape of a good answer. Never reuse their words, names, or data; write copy from your own brief.
- Copy the structure of a proven pattern (the component library's examples, a well-known product in the same category) and change the content and brand. A solid convention beats a shaky invention.
- Make fewer choices: one font, one accent, one radius, one spacing scale, one container style. Consistency reads as quality.
- When two options seem equal, pick the quieter one.
- Always do section 10. Looking at the render catches more than any checklist.

Visual craft, typography scale, hero composition, and anti-slop rules incorporate patterns adapted from Google DemoLab's `gemini-frontend-design` skill (`https://github.com/google-gemini/demolab`), licensed under Apache-2.0.
