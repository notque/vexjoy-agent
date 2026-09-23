# UI design recipes

Concrete starting points for common screens. Read `ui-design-judgment.md` first; this file turns it into values and layouts you can copy. Start from the closest recipe, fill in the real content, then run the look-then-fix loop (judgment section 10). Change any value when the product gives you a reason, and say the reason.

## How to use this file

1. Name the surface: tool (used daily, dense) or page (visited once, expressive). If both, the main screen decides.
2. Pick the recipe below that matches the main screen. If none fits, use the app shell or the landing page and adapt.
3. Paste the base tokens, then change only the brand hue and, if the brand calls for it, the font.
4. Build with real content. Build every state listed in the recipe.
5. Render and check (judgment section 10). Fix in order: content, hierarchy, spacing, type, color, polish.

## Base tokens

These work with shadcn/ui and Tailwind v4 (`@theme inline` maps them to utilities). Hue 260 is a placeholder: replace it with the brand hue in every line where it appears, then recheck `--primary` against white text (4.5:1).

```css
:root {
  --radius: 0.5rem;               /* controls 6px, containers 8-12px */
  --background: oklch(1 0 0);
  --foreground: oklch(0.18 0.01 260);
  --card: oklch(1 0 0);
  --card-foreground: var(--foreground);
  --popover: oklch(1 0 0);
  --popover-foreground: var(--foreground);
  --muted: oklch(0.97 0.004 260);           /* subtle fills, table header, hover */
  --muted-foreground: oklch(0.50 0.015 260); /* secondary text, ~5.5:1 on white */
  --border: oklch(0.92 0.005 260);
  --input: oklch(0.90 0.005 260);
  --ring: oklch(0.55 0.18 260);
  --primary: oklch(0.52 0.19 260);          /* brand accent; white text passes */
  --primary-foreground: oklch(0.99 0 0);
  --secondary: oklch(0.96 0.006 260);
  --secondary-foreground: var(--foreground);
  --accent: oklch(0.96 0.006 260);          /* shadcn uses this for hover rows and menu items */
  --accent-foreground: var(--foreground);
  --destructive: oklch(0.55 0.21 27);
  --success: oklch(0.55 0.15 150);
  --warning: oklch(0.75 0.15 75);           /* use dark text on warning fills */
}

.dark {
  --background: oklch(0.16 0.006 260);      /* not pure black */
  --foreground: oklch(0.96 0.004 260);      /* not pure white */
  --card: oklch(0.20 0.006 260);            /* raised = slightly lighter */
  --card-foreground: var(--foreground);
  --popover: oklch(0.22 0.006 260);
  --popover-foreground: var(--foreground);
  --muted: oklch(0.24 0.006 260);
  --muted-foreground: oklch(0.72 0.012 260);
  --border: oklch(1 0 0 / 10%);
  --input: oklch(1 0 0 / 14%);
  --ring: oklch(0.68 0.15 260);
  --primary: oklch(0.68 0.16 260);          /* lighter, less saturated than light mode */
  --primary-foreground: oklch(0.16 0.006 260);
  --secondary: oklch(0.26 0.006 260);
  --secondary-foreground: var(--foreground);
  --accent: oklch(0.26 0.006 260);
  --accent-foreground: var(--foreground);
  --destructive: oklch(0.65 0.19 27);
  --success: oklch(0.70 0.14 150);
  --warning: oklch(0.80 0.14 75);
}
```

**Type scale (px / line height / weight):**

| Token | Size | Line height | Weight | Use |
|---|---|---|---|---|
| `text-xs` | 12 | 16 | 500 | badges, captions, table meta |
| `text-sm` | 14 | 20 | 400/500 | tool body text, table cells, labels, buttons |
| `text-base` | 16 | 24 | 400 | page body text, form inputs on mobile |
| `text-lg` | 18 | 28 | 600 | card and section titles |
| `text-xl`/`2xl` | 20/24 | 28/32 | 600 | page titles in tools |
| `text-4xl`+ | 36–60 | 1.1 | 600–700 | landing headlines only; letter spacing -0.02em |

**Spacing:** 4, 8, 12, 16, 24, 32, 48, 64, 96. Inside a control 8–12. Between fields 16. Between groups 24–32. Between page sections 48–64 in tools, 96+ on landing pages.

**Fonts:** tools use one sans (the platform UI font, Inter, or Geist) plus a mono for code and IDs. Brand pages may add one display face for headlines only. Load at most two families and three weights.

**Controls:** height 36 px (dense tools 32, touch 44). Buttons: one `default` (primary) per region; `outline` or `ghost` for the rest; `destructive` only inside a confirmation.

## Recipe: app shell (most tools)

```
┌──────────┬──────────────────────────────────────────┐
│ Logo     │ Page title            [Secondary] [Primary]│  header 56px, border-bottom
│          ├──────────────────────────────────────────┤
│ Nav      │                                          │
│ items    │  Content (max-width 1200-1400, padding 24)│
│ 240px    │                                          │
│          │                                          │
│ ──────── │                                          │
│ Account  │                                          │
└──────────┴──────────────────────────────────────────┘
```

- Sidebar 240 px (shadcn `sidebar`), collapsible to icons at 64 px; becomes a `sheet` below 768 px.
- Nav items: icon 16 px plus label, 32–36 px tall, active item uses `accent` fill plus `foreground` text, not the brand color.
- Page header: title left, at most one primary action right. Filters and tabs go in a row under the title, not in the header.
- Background `background`; content sits directly on it. Use `card` only to group things that are truly separate.
- States: first-run empty state for the whole app, loading skeletons for the content area, and a 404 page inside the shell.

## Recipe: dashboard

- Top row: 3–4 key metrics, never more than 5. Each is a label (`text-sm muted-foreground`), a value (`text-2xl` or `text-3xl`, weight 600, tabular numbers), and a change indicator (`text-xs`, up or down arrow plus percent, colored only when good or bad is unambiguous).
- Then one primary chart at full width, 280–360 px tall. Then a table of the items that need attention.
- Every metric answers "compared to what?": previous period, target, or trend sparkline.
- Don't: a grid of 8+ identical cards, pie charts with more than 4 slices, charts without axis labels, rainbow series colors. One series in the primary color, comparisons in muted gray.
- States: loading skeletons shaped like numbers and chart; "no data yet" with the action that produces data; partial-data notice when a source failed.

## Recipe: data table

- Toolbar above the table: search input (240–320 px) left, filters next to it, view options and primary action right.
- Row height 40–48 px. Header `text-xs` or `text-sm`, weight 500, `muted-foreground`, `muted` background or just a bottom border.
- Left-align text, right-align numbers (tabular), center nothing except checkboxes and status icons.
- The first column is the thing's name, linked to its detail page, weight 500.
- Row actions: a `…` menu at the end of the row; the most common action can be a visible ghost button.
- Status as a `badge` with a dot or icon plus text; soft background, not saturated fills.
- Long text truncates with an ellipsis and a tooltip. IDs and hashes in mono, truncated in the middle.
- Pagination or "load more" below, with the total count ("1–50 of 1,284").
- States: loading (5–10 skeleton rows), empty (no items yet, with the create action), filtered to zero ("No results for 'acme'", clear-filters button), error with retry.
- Below 768 px: turn rows into stacked cards showing name, status, and one key value, or allow horizontal scroll with the name column pinned.

## Recipe: form and settings

- One column, max width 560–640 px. Labels above inputs. Help text below the input in `text-sm muted-foreground`.
- Group related fields under a section title (`text-lg` weight 600) with a one-line description. 32–48 px between sections, 16–20 px between fields.
- Settings pages: section title and description on the left (1/3), fields on the right (2/3) on wide screens; stacked on narrow screens.
- Mark optional fields "(optional)" instead of marking required ones with asterisks, when most fields are required.
- Validate on blur and on submit, not on every keystroke. Error text replaces help text, in `destructive`, with what to do: "Enter a date after 1 Jan 2024".
- The primary button names the outcome ("Save changes", "Create project") and sits at the end of the form, left-aligned with the fields; a secondary "Cancel" as `ghost` next to it.
- Destructive settings live at the bottom in a separate section with a `destructive` outline button and a confirmation dialog that names the thing being deleted.
- States: saving (button shows a spinner and "Saving…", stays the same width), saved (toast or inline "Saved"), server error at the top of the form with a summary.

## Recipe: detail page

- Header: breadcrumb, then the object's name (`text-2xl` weight 600), key status badge, and actions right (one primary, the rest in a `…` menu).
- Body: main content 2/3 left, metadata panel 1/3 right (label/value pairs, `text-sm`, label in `muted-foreground`). Stack on narrow screens with metadata first only if it is what users look for first.
- Related lists (activity, comments, children) under the main content with section titles, not in tabs, unless there are more than 3 of them.

## Recipe: modal, sheet, and confirmation

- `dialog` for short, blocking decisions (confirm, rename, quick create with 1–4 fields). Width 420–560 px.
- `sheet` from the right for details and editing that should keep the page context. Width 400–640 px.
- A separate page for anything with more than about 6 fields, or anything people link to.
- Confirmation copy: title says the action and the object ("Delete project Atlas?"), body says the consequence ("This removes 14 dashboards. You can't undo this."), buttons are "Cancel" and "Delete project".

## Recipe: auth (sign in, sign up)

- Centered card or bare form, 360–400 px wide, on `background` or a muted panel. Logo above.
- Show only what's needed: email, password, primary button, one alternative (SSO or magic link), and a link to the other flow.
- Password field with show/hide. Errors never reveal whether an account exists.
- No marketing copy, no carousel, no stock photography unless the brand requires a split-screen, and then the image side is decorative only.

## Recipe: checkout

- Mobile first: most buyers are on phones. One column, steps in order: contact, shipping address, shipping method, payment, review.
- The order summary must be visible before the buyer pays. On mobile, put a collapsed summary bar at the top ("Show order summary · $75.78") that expands to the items; repeat the total and item count right above the place-order button. On desktop, put the summary in a right column (about 40%) that stays in view while scrolling.
- The place-order button is the last element of the form, full width on mobile, and shows the total: "Place order · $75.78".
- Shipping options as large radio cards showing name, delivery time, and price; show "Free" when a threshold applies and say why ("Free over $60").
- Use `autocomplete` on every field (`email`, `given-name`, `address-line1`, `postal-code`, `cc-number`, `cc-exp`, `cc-csc`) and `inputmode="numeric"` for card, CVC, and postal code.
- Discount code: a collapsed "Add discount code" link that opens the field, so it doesn't pull buyers away to search for codes.
- Compute money in code and check it: subtotal, shipping rule, tax on the right base, and total must add up exactly.
- No trust-badge clutter. One line near the button ("Payments are encrypted") is enough.

## Recipe: empty state

- Inside the region that would hold the content, not a separate page.
- An icon or small illustration (optional, 40–64 px, muted), a title that names the missing thing ("No invoices yet"), one sentence on why it matters or what to do, and one primary action ("Create invoice"). Optionally a secondary link to docs or import.
- For filtered-to-zero: say what was filtered and offer "Clear filters". No illustration.

## Recipe: landing page

Landing pages are where expression belongs. Choose the style from the brand and audience; don't default to any "look".

1. **Hero:** headline (what it does for whom, under 10 words), subhead (how, one or two sentences, 60 ch max), one primary action plus at most one secondary, and a real product visual (screenshot, demo, or the product itself). Left-aligned text with the visual to the right, or stacked with the visual below, both work; pick by the visual's shape.
2. **Proof:** real customer logos, a real quote, or a real number. If none exists yet, skip this section.
3. **How it works or key features:** 3–4 items, each with a specific benefit and a visual of that feature. Vary the layout (alternate image sides, one large feature then a grid) so every section isn't the same shape.
4. **Details for evaluators:** pricing, integrations, security, FAQ, whatever the audience needs to decide.
5. **Final call to action:** repeat the primary action with a short reason.

- Width: text columns 640–720 px, visuals up to 1200 px. Section spacing 96–128 px on desktop, 64 on mobile.
- Headline type 48–72 px desktop, 36–40 mobile, weight 600–700, letter spacing -0.02em, line height 1.05–1.15.
- One brand color used for the primary action and a few highlights; the rest is neutrals, imagery, and type.
- Motion: subtle entrance on the hero, restrained reveal on scroll if any; nothing that delays reading.
- Check the hero at 375 px: the headline, the primary action, and a glimpse of the product should fit in the first screen.

## Recipe: pricing

- 2–4 plans side by side (stacked on mobile). One highlighted plan with a `primary` border or badge ("Most popular") — only if it's true.
- Each plan: name, one-line who-it's-for, price (large, tabular) with the period, primary action, then features as a checklist. Put features that differ between plans first.
- Annual/monthly toggle above, showing the saving. A comparison table below for detail.

## Recipe: settings for a single HTML artifact, report, or doc page

- One column, 720–800 px, `text-base` body, generous line height (1.6), clear H1/H2/H3 scale (32/24/18).
- Lead with the answer: a short summary box at the top, then detail.
- Tables for comparisons, code blocks for code, callouts only for real warnings.
- Works in print: no dark backgrounds on large areas, no content that only appears on hover.

## Chart defaults

- One series: `primary`. Comparison series: muted gray. Up to 5 categorical series; beyond that, group or use small multiples.
- Axis text `text-xs muted-foreground`, light gridlines on one axis only, no chart borders, no 3D, no shadows.
- Label lines directly at their end instead of a legend when there are 3 or fewer series.
- Start bar charts at zero. Use line charts for time, bars for comparison, and a table when people need exact values.
