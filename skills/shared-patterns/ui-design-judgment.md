# UI design judgment

Read this before any UI work: new screens, restyles, critiques, HTML artifacts, slides, component plans. It is the judgment the other UI references assume. Everything here is a default with a reason. Break a default when you can name the reason it does not apply to this product.

This guide is web-first. On native platforms (iOS, Android, desktop apps), the platform's own guidelines win where they differ: for example 44 pt targets on iOS, 48 dp on Android, and native navigation patterns.

Good UI comes from three things, in order: the right content, a clear hierarchy, and consistent spacing and type. Color, motion, and effects come last and matter least. Most weak designs fail at step one or two and try to fix it at step three.

## 1. Start from the job and the real content

- Name the one job this screen does and the one action that matters most. If you can't, the screen does too much; split it or ask.
- Design with real or realistic content: real names, real lengths, real numbers, the longest label. Lorem ipsum and "Item 1" hide every layout problem.
- Match the surface. A tool people use all day (dashboard, admin, editor) should be dense, calm, and fast to scan. A page people visit once (landing, launch, portfolio) can be spacious and expressive. Mixing these up is the most common big miss: marketing heroes on internal tools, cramped tables on landing pages.
- Build what the brief asks for, all of it, and nothing it doesn't. Every field, column, section, and state the brief names must appear. Don't invent features, plans, roles, prices, legal details, or claims the brief doesn't give; if the design needs one, add it as a visibly marked placeholder (`[Needs real value]`).
- Use the conventions users already know for the platform and the pattern. Put originality in the parts that carry the brand, not in navigation, forms, or tables.

## 2. Hierarchy: make one thing win

- Each view has one primary element and one primary action. Everything else steps down.
- Build hierarchy with size, weight, and position first, and color last. Test: in grayscale, is the order still obvious?
- De-emphasize to emphasize. Mute secondary text, shrink metadata, and turn secondary buttons into ghost or link styles, instead of making the primary thing louder.
- One primary button per region. Destructive actions are never the most prominent button unless deleting is the task.
- Group by proximity: space inside a group is smaller than space between groups. This does more than borders, boxes, and dividers, which you should remove when spacing already separates the groups.

## 3. Spacing and layout

- Use one spacing scale (4 or 8 px based: 4, 8, 12, 16, 24, 32, 48, 64) and nothing between the steps.
- Align everything to a few edges. Ragged left edges look broken even when each part looks fine.
- Start with more whitespace than feels needed, then tighten. Crowding is the usual failure; emptiness rarely is.
- Keep prose to 60–75 characters per line. Full-width paragraphs on desktop are hard to read.
- Don't nest cards in cards. Use one level of container; inside it, use spacing and type.
- Design the smallest screen first for anything public. Check at 375, 768, and 1280 px wide.
- At 375 px the page must never scroll sideways. Wrap every table and wide element in a container with `overflow-x: auto`, give flex and grid children `min-width: 0`, and let long words break (`overflow-wrap: anywhere` on names, emails, URLs).
- Navigation must stay reachable on phones. When a sidebar hides below 768 px, add a menu button in the header that opens it as a sheet or drawer.

## 4. Typography

- One family is enough for product UI; two (display plus text) for expressive pages. A well-made system or neutral sans (the platform UI font, Inter, Geist) is a good default for tools. Choose a distinctive face when the brand calls for it, not by reflex.
- Use a small type scale, about five or six sizes (for example 12, 14, 16, 20, 24, 32 or more for display). Body text 16 px on the web; 14 px is fine for dense tools.
- Line height about 1.5 for body text and 1.1–1.25 for headings. Tighten letter spacing slightly on large headings; never on small text.
- Use weight and color for emphasis within a size, and use two or three weights, not five.
- Use tabular numerals for numbers that line up or change (tables, prices, timers). Right-align numeric columns.
- Uppercase letter-spaced labels work as a small accent. On every label they turn to noise.

## 5. Color

- A pure white background is fine in light mode; off-white is a brand choice, not a rule.
- Start neutral. Most of the screen is background, surface, border, and text grays. Tint the grays slightly toward the brand hue so they don't look dead.
- Color carries meaning: the primary action, links, selection, and status. If a color means nothing, it is decoration; remove it or make it quieter.
- Pick one brand accent and use it sparingly. Status colors (success, warning, danger) are separate and always pair with an icon or text.
- Contrast: 4.5:1 for body text, 3:1 for large text and UI boundaries. Check the actual pairs, especially muted text, placeholders, and text on colored buttons.
- Define color as tokens (background, foreground, muted, border, primary, and so on) and build dark mode from its own values: slightly lighter surfaces for elevation, less saturated accents, no pure black under pure white text. An inverted light theme is not a dark theme.
- In a standalone HTML file, put the dark values in `@media (prefers-color-scheme: dark) { :root { ... } }` so dark mode works with no toggle. In a React or shadcn app, use the `.dark` class and the app's theme switcher. Ship dark mode by default unless the brief rules it out.
- OKLCH makes even steps and matched hues easy when you build a scale.

## 6. Components and states

- Use the component library's existing parts and variants before inventing new ones. Consistency beats local cleverness.
- Every data view needs its states designed: loading (skeletons shaped like the content), empty (says why and what to do next), error (what happened and how to fix it), and overflow (long names, many items, zero items).
- Every interactive element needs hover, focus-visible, active, and disabled states. Focus rings must be visible; never remove them without a replacement. Default: `outline: 2px solid var(--ring); outline-offset: 2px` on `:focus-visible`.
- Exact defaults for tools: table rows 40–48 px (32–36 when density matters most), controls 36 px, icons 16 px inline and 20 px standalone, font stack `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif` when no brand font is given.
- Placeholders show the format, never a realistic value: `name@example.com`, `MM / YY`, not "Jane" or "Portland", which look like filled-in answers. Many fields need no placeholder at all.
- Touch targets at least 44 × 44 px. Forms: labels above fields, errors next to the field, the submit button says what it does ("Create invoice", not "Submit").
- Charts: follow the chart defaults in `ui-design-recipes.md`; for deeper chart work use the data-viz guidance available in your harness.
- Icons support labels; they rarely replace them. Use one icon set at one stroke weight. In a standalone HTML file, draw icons as inline SVG (for example Lucide paths, `stroke="currentColor"`, 16–20 px). Never use emoji or an icon font as icons: they render as empty boxes when the font is missing.

## 7. Depth, motion, and effects

- Prefer borders or small surface-color shifts to shadows in dense UI. Save shadows for things that float: menus, popovers, dialogs.
- Keep one radius family (for example 6 px controls, 8–12 px containers). Nested corners look right when the inner radius equals the outer radius minus the padding.
- Motion explains a change: where something came from, what changed, what is loading. 150–250 ms with ease-out for UI; longer only for large, rare moments. Respect `prefers-reduced-motion`.
- Content must be visible with no JavaScript and no animation. Never ship CSS that starts sections at `opacity: 0` and waits for a scroll observer to reveal them: if the script fails, the observer doesn't fire, or the page is printed or screenshotted, the section is blank. Animate only with a class that JavaScript adds, and only inside `@media (prefers-reduced-motion: no-preference)`.
- Gradients, glass, glow, grain, and 3D are seasoning. Use one, on purpose, where it supports the brand, and never where it lowers text contrast.

## 8. Copy is design

- Write the real words. Headlines say what the thing does for this user, in their terms. Buttons name the outcome.
- Cut words until the meaning breaks, then add one back.
- Never invent metrics, testimonials, logos, or user counts. Use a clearly marked placeholder instead.

## 9. Tells of generated UI

These patterns mark a design as default output. Each has legitimate uses; the problem is reaching for them without a reason.

| Tell | Instead |
|---|---|
| Purple-to-blue gradients, gradient headline text | The brand's own color, used flat |
| Centered hero, three feature cards in a row, logo strip, repeat | A layout built around this product's real content and main action |
| Emoji as icons; an icon on every heading and bullet | One icon set, used where it aids scanning |
| Every section the same weight and structure | A clear lead section; vary rhythm and density |
| Cards with shadow, border, and big radius on everything | One container style; spacing for grouping |
| Colored left-border "callout" cards everywhere | Hierarchy through type and spacing |
| Tiny uppercase tracking labels on every block | One accent label style, used sparingly |
| Glassmorphism and glow on a plain product UI | Solid surfaces with clear contrast |
| Fake stats, testimonials, and logos | Real data or a marked placeholder |
| Every button styled as primary | One primary per region; `outline` or `ghost` for the rest |
| "Get started", "Learn more", "Submit" | The specific outcome |
| Overcorrection: serif display, cream background, grain, and editorial layout on every project | Choose the style from the brand and audience, not from a list of "not generic" moves |

## 10. Look, then fix

Code that compiles is not a finished design. Render it and look.

1. **Render.** Use whatever the harness has: Playwright, chrome-devtools, a browser screenshot tool, or an HTML preview. If none exists, say so and list what the user should check by eye.
2. **Check at three widths** (375, 768, 1280) with a normal 800 px tall window, and in light and dark mode. Scroll to the bottom before a full-page screenshot so lazy content loads, then look at every section: a blank band means hidden content.
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
2. Is there one clear primary action per view, named for its outcome?
3. Do the squint and grayscale tests show the right order of importance?
4. At 375 px: no sideways scroll, navigation reachable, targets at least 44 px?
5. Does dark mode work, with readable muted text?
6. Is every section visible without scrolling animations or JavaScript?
7. Do empty, loading, error, and long-content states exist where data appears?
8. Are all icons inline SVG, with no emoji or icon-font boxes?
9. Did you check the render yourself, not only the code?

## When you're a weaker model or unsure

- Examples in these guides show the shape of a good answer. Never reuse their words, names, or data; write copy from your own brief.
- Copy the structure of a proven pattern (the component library's examples, a well-known product in the same category) and change the content and brand. A solid convention beats a shaky invention.
- Make fewer choices: one font, one accent, one radius, one spacing scale, one container style. Consistency reads as quality.
- When two options seem equal, pick the quieter one.
- Always do section 10. Looking at the render catches more than any checklist.
