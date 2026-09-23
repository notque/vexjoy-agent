# UI design examples

Before-and-after fixes for the problems that show up most in generated UI. Each one names what's wrong, why it hurts, and the exact change. Use these as models for your own critique: element, problem, effect, fix. Read `ui-design-judgment.md` first and `ui-design-recipes.md` for values.

## 1. Two primary buttons compete

**Before:** Page header has "Export" and "New report", both solid `primary`.
**Problem:** Two equally loud actions; users hesitate and the main task loses.
**Fix:** "New report" stays `default` (primary). "Export" becomes `outline` or moves into a `…` menu if it's used rarely.

```tsx
<Button variant="outline">Export</Button>
<Button>New report</Button>
```

## 2. Everything is a card

**Before:** Page background gray; every section is a white card with border, shadow, and 16 px radius; cards inside cards for sub-sections.
**Problem:** Borders everywhere flatten hierarchy; nested boxes waste space and look busy.
**Fix:** Put content directly on `background`. Separate sections with 48 px of space and a `text-lg` weight-600 title. Keep one card level only for things that are truly separate objects (a list of projects, a metric tile).

## 3. Hierarchy by color instead of size and weight

**Before:** Page title 16 px blue, section titles 16 px green, body 16 px gray.
**Problem:** Same size and weight everywhere; color alone can't carry the order, and it fails the grayscale test.
**Fix:** Title `text-2xl` 600 `foreground`; section titles `text-lg` 600 `foreground`; body `text-sm` or `text-base` 400; metadata `text-sm` `muted-foreground`. No colored headings.

## 4. Muted text that fails contrast

**Before:** Secondary text `#9CA3AF` on white (2.5:1).
**Problem:** Hard to read for many users; fails WCAG 1.4.3.
**Fix:** Use `--muted-foreground` at OKLCH lightness 0.50 or darker on white (about 5.5:1). Placeholder text may be lighter only if a visible label also exists.

## 5. Generic hero

**Before:**
> # Unlock Your Potential With AI-Powered Productivity
> The all-in-one platform that transforms the way you work.
> [Get Started] [Learn More]
> Purple-blue gradient background, centered text, no product image.

**Problem:** Says nothing specific, could be any product, shows nothing real; the gradient signals template.
**Fix:**
> # Know which plants need water today
> Sprig learns how fast each pot dries out in your home and reminds you only when it's time.
> [Add your first plant] [See how it works]
> Left-aligned text, real app screenshot on the right, plain background with one brand color on the primary button.

## 6. Feature section in three identical cards

**Before:** Three centered cards, each an emoji, a two-word title, and a vague sentence ("⚡ Lightning Fast — Blazing performance for your workflow").
**Problem:** Emoji icons and vague claims read as filler; identical shapes make every section look the same.
**Fix:** Each feature gets a specific benefit and a real visual: "Reminders per pot — a terracotta pot in a sunny window gets watered sooner than a plastic one in the hall" next to a cropped screenshot of two plant cards with different next-watering dates. Alternate the image side, or lead with one large feature and follow with a compact grid of three smaller ones.

## 7. Invented proof

**Before:** "Trusted by 10,000+ teams", five logos of well-known companies, a quote from "Sarah J., CEO".
**Problem:** Fabricated. Misleads users and damages trust when found out.
**Fix:** Remove the section, or use clearly marked placeholders: `[Customer quote — needs real source]`. Never invent names, numbers, or logos.

## 8. Table with everything centered

**Before:** All columns centered; amounts like `1234.5` and `12.00` in a proportional font; status as colored text only.
**Problem:** Hard to scan and compare; numbers don't line up; color-only status fails for color-blind users.
**Fix:** Left-align text, right-align amounts with `tabular-nums` and fixed decimals (`$1,234.50`), status as a `badge` with a dot and the word ("Overdue").

## 9. Empty state that's a dead end

**Before:** "No data available." in gray, centered in an empty table.
**Problem:** Doesn't say what's missing or what to do.
**Fix:**
> **No invoices yet**
> Invoices you create or import will appear here.
> [Create invoice] Import from CSV

## 10. Form with vague button and late errors

**Before:** Fields with placeholder text as labels, a "Submit" button, errors shown only in a banner after submit ("Invalid input").
**Problem:** Labels vanish when typing; the button doesn't say what happens; the error doesn't say which field or how to fix it.
**Fix:** Visible labels above fields; button "Create account"; per-field errors on blur ("Password needs at least 12 characters"); a summary at the top only when there are several errors.

## 11. Dark mode by inversion

**Before:** `#000` background, `#FFF` text, same saturated brand blue, shadows for elevation.
**Problem:** Harsh contrast causes glare; saturated colors vibrate on black; shadows are invisible.
**Fix:** Background OKLCH 0.16, text 0.96, raised surfaces a bit lighter (0.20–0.22) instead of shadows, brand color lighter and less saturated (see recipes dark tokens).

## 12. Motion that delays

**Before:** Every section fades up 600 ms on scroll with staggered children; buttons scale on hover; page loader for 1 second.
**Problem:** Content waits for animation; repeated motion becomes noise; no reduced-motion handling.
**Fix:** One restrained hero entrance (200–300 ms), no loader for fast pages, hover as a color change, and `@media (prefers-reduced-motion: reduce)` turning off transforms.

## 13. Mobile as a squeezed desktop

**Before:** At 375 px the sidebar overlaps content, the table scrolls sideways with no pinned column, buttons are 28 px tall.
**Problem:** Unusable on phones.
**Fix:** Sidebar becomes a `sheet` behind a menu button; table rows become stacked cards (name, status, one value); controls 44 px tall; primary action reachable at the bottom.

## 14. Overcorrected "not generic"

**Before:** A B2B analytics tool styled with a serif display face, cream paper background, film grain, and magazine-style asymmetric layout.
**Problem:** The style fights the job. Analysts need dense, fast, neutral screens; the editorial look slows scanning and feels off-brand.
**Fix:** Neutral sans, white or near-white background, compact spacing, color reserved for data and state. Put personality in the logo, the empty states, and the copy.

## 15. Sections that never appear

**Before:** `.reveal { opacity: 0; transform: translateY(24px) }`, shown by an IntersectionObserver when scrolled into view.
**Problem:** In print, screenshots, reader mode, or when the script fails, whole sections are blank. A test run showed two empty bands on a landing page.
**Fix:** Keep content visible by default. Add the starting state only from JavaScript, and only when motion is allowed:

```css
@media (prefers-reduced-motion: no-preference) {
  .js .reveal:not(.is-visible) { opacity: 0; transform: translateY(12px); }
  .reveal { transition: opacity .3s ease-out, transform .3s ease-out; }
}
```
```js
document.documentElement.classList.add('js');
```

## 16. Table that widens the phone page

**Before:** At 375 px a 6-column table pushes the whole page to 900 px wide; the header and filters scroll sideways with it, and the sidebar is gone with no menu button.
**Problem:** Users pan the entire page to read one row and can't navigate.
**Fix:** Wrap the table (`<div class="table-wrap">` with `overflow-x: auto`), or switch rows to stacked cards below 640 px. Add a header menu button that opens the navigation as a drawer. Check `document.documentElement.scrollWidth <= innerWidth`.

## 17. Helpful inventions

**Before:** The brief lists Admin and Member roles and two plans; the page adds an "Owner" role, a "Recipe import" feature, and a tax ID in the footer text.
**Problem:** Each invention is a product decision nobody made; it gets built or promised by accident.
**Fix:** Use only what the brief gives. Where the layout needs more, add a marked placeholder: `[Feature 4 — needs product input]`.

## Writing a critique

Use this shape for every finding, most important first:

> **[Element]** — [problem]. [Effect on the user]. **Fix:** [exact change with values or component names].

Example:

> **Metric tiles** — the four values are 16 px, the same size as their labels. Users can't find the numbers at a glance. **Fix:** values `text-3xl` weight 600 with `tabular-nums`, labels `text-sm muted-foreground` above them.

End with what works and why, in one or two lines, so the next round keeps it.
