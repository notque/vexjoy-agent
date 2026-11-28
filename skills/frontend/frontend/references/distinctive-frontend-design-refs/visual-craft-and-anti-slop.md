# Visual craft and anti-slop discipline

Execution rules for distinctive frontend builds. Read alongside `skills/shared-patterns/ui-design-judgment.md`; where defaults conflict, the core doc wins unless you state a product reason.

## Palette beyond beige and neon

When the aesthetic direction is open, derive palette, contrast, and rhythm from the subject's real materials, lighting, and audience.

- Skip defaulting to warm beige or cream paired with rust/terracotta, and skip dark slate paired with neon purple glow.
- Draw from wider color registers suited to the subject:
  - **Bold chromatic color-blocking:** Saturated editorial bands anchored by crisp neutral ink.
  - **Deep organic darks:** Deep roast, forest, ink, or marine darks with warm or cool off-white text.
  - **Cool architectural neutrals:** Stone, brushed silver, graphite, and sharp hairline contrast.
  - **Sunlit pastels or crisp gallery light:** High-key surfaces where photography or typography carries focal weight.
- Keep desktop navigation on a single compact line. Make the brand wordmark visually stronger than the menu links through weight, scale, or contrast.
- Bleed hero surfaces to `y = 0` behind a borderless header. If the header stays fixed while scrolling, add clean surface separation (solid fill, hairline border, or subtle elevation) only once scrolled.

## Strict 3-size body typography discipline

Constrain type choices so hierarchy stays legible and calm across every viewport.

1. **Font families (max 2):** Load 1 versatile sans or 1 purposeful display-plus-body pairing via `<link rel="preconnect">`, `@font-face`, or `next/font`.
2. **Tabular numerals over a 3rd monospace font:** Omit a 3rd monospace family for prices, timers, or counts. Keep aligned numbers in the primary sans with `font-variant-numeric: tabular-nums` unless building code editors, technical docs, or terminal tools.
3. **3-size body scale:** Below the hero, lock body and UI copy to at most 3 font-size tokens. Add a 4th step only when a dense dashboard or data table is explicitly requested:

```css
:root {
  --text-heading: clamp(1.5rem, 2.5vw, 2.25rem);
  --text-body: 1rem;       /* 16px uniform body paragraphs and lists */
  --text-sm: 0.875rem;     /* 14px secondary metadata and captions */
}
```

4. **Weight, family, and color over extra sizes:** Differentiate `<h3>`, buttons, captions, and form labels with font weight, family, or color rather than adding intermediate pixel steps.
5. **Exemptions:** The hero `<h1>` and navbar brand wordmark sit outside the 3-size body ceiling.
6. **Above-the-fold floor:** Ship zero text smaller than `13px` (`0.8125rem`) anywhere above the fold.
7. **Uniform paragraph and list scale:** Keep body paragraphs and bulleted or numbered lists at one uniform font size (`--text-body`). Omit oversized `.lead` paragraphs above smaller body copy and omit shrunk list items.
8. **Micro-typography:** Set UI labels and table headers in sentence case. Constrain prose measure to `<= 65ch`. Apply `-0.02em` to `-0.05em` letter-spacing on large display headlines.

## Opening format fit and hero composition

Match the opening viewport to the format before building a hero banner.

### Direct-to-content formats

News sites, blogs, dashboards, analytics consoles, documentation, directories, utility tools, and resumes open directly into live functional content with zero marketing hero banner.

### Hero-led brand and launch pages

Abandon the `50/50` left-text / right-media split template. Choose a full-width or depth composition instead:

| Composition | Structure |
|-------------|-----------|
| **Monumental headline + wide stage** | Centered display `<h1>` over a full-width interactive product preview or visual stage |
| **Full-bleed takeover** | Edge-to-edge photography or art bleeding to `y = 0` with type anchored in clean negative space |
| **Layered `z-index` occlusion** | Display headline set partially behind a transparent cutout foreground subject |
| **Wall-to-wall poster / corner choreography** | Edge-anchored typography and focal subject arranged across diagonal corners of the viewport |

Hero proportion and pacing rules:
- Set `<h1>` at `clamp(3.5rem, 7.5vw, 8rem)` with `line-height` between `0.9` and `1.0`.
- Pair the hero headline with at most **25 words** of supporting copy and **one** primary action.
- Omit the 3-column or 4-column KPI/spec footer strip at the bottom of the hero viewport.
- Keep kinetic hero typography visible and readable at rest without waiting on scroll triggers.
- Sustain compositional ambition below the fold by varying band layouts instead of collapsing into repeated 3-column card rows.

## Art-directed custom imagery and calibrated motion

### Custom imagery

1. Generate unique project-relative visuals (`generate_image` or the `image-gen` skill) matched to each container's exact aspect ratio (`16:9`, `4:5`, `3:2`, `1:1`).
2. Keep lighting direction, color temperature, and palette consistent across all visuals on the page.
3. Write 1 to 3 plain-sentence prompts naming the subject, framing, lighting, and clean negative space so overlay text passes WCAG AA contrast without muddy dark scrims.
4. If image generation is unavailable, fall back to bespoke inline SVG, CSS compositions, or Canvas. Never guess external image URLs or embed machine-local filesystem paths.

### Calibrated motion

1. Keep interactive transitions brisk at `140ms` to `240ms` using `cubic-bezier(0.22, 1, 0.36, 1)`.
2. Declare explicit transitioned properties (`transform`, `opacity`, `clip-path`). Omit `transition: all`, Tailwind `transition-all`, and `ease-in` curves:

```css
.action {
  transition: transform 180ms cubic-bezier(0.22, 1, 0.36, 1),
              opacity 180ms cubic-bezier(0.22, 1, 0.36, 1);
}
```

3. Honor `@media (prefers-reduced-motion: reduce)` across every transition and animation.
4. Keep scrolling native on utility tools, news layouts, and data views; skip scroll-jacking and smooth-scroll overrides.

## UI and copy patterns to replace

Replace generated UI habits with direct structural elements:

| Pattern to remove | Use instead |
|-------------------|-------------|
| `.eyebrow` / `.kicker` labels or `"Location · Batch · Status"` lines above headings | Start sections directly with `<h1>` or `<h2>` |
| Decorative non-interactive chips, badges, or category tags (rounded or square/bordered) | Plain text metadata, spacing, or real interactive filters |
| Button walls for mode, filter, or size selection | At most one primary CTA button per section; use segmented toggles, tabs, radios, switches, `<select>`, or canvas interaction |
| Nested card-in-card cages | One container level; separate inner groups with spacing and typography |
| Decorative `01` / `02` / Roman heading prefixes and fake `"LIVE"` or `"SCROLL"` cues | Direct section headings and real live state |
| Spec-first headings (`"2.6 kg Cabin Mass"`) | Benefit-led headings (`"Lightweight shell"`) |
| Forced `<br><em>` italic headline splits | Whole, unified headlines set in one consistent style |
| Em-dashes or spaced en-dashes in generated UI copy | Commas, colons, periods, or shorter sentences (preserve user-supplied text verbatim) |

## Pre-delivery checklist and visual pass

Audit every build across four buckets before handoff:

### 1. Composition and navigation
- [ ] Content and workspace formats open straight into live content; hero-led pages use full-width or depth compositions instead of a 50/50 split.
- [ ] Desktop nav fits on one compact line with a stronger wordmark than menu links; hero bleeds to `y = 0`, separating cleanly when scrolled if fixed.
- [ ] Hero carries `<= 25` words of supporting copy, one primary CTA, and zero 3-4 column KPI/spec footer strip.
- [ ] Below-the-fold sections sustain varied layouts instead of collapsing into 3-column card rows, with zero nested card-in-card cages.

### 2. Typography and copy
- [ ] At most 2 font families loaded cleanly; `tabular-nums` handles aligned numbers without adding a 3rd monospace font.
- [ ] Body copy uses at most 3 font-size tokens (`--text-heading`, `--text-body`, `--text-sm`); zero `< 13px` text above the fold.
- [ ] Paragraphs and lists share one uniform scale; UI labels and table headers use sentence case; prose stays `<= 65ch`.
- [ ] Zero eyebrows/kickers, zero `01`/`02`/Roman prefixes, zero `<br><em>` splits, benefit-led headings, and zero em-dashes in generated copy.

### 3. Visual craft and motion
- [ ] Palette fits the subject beyond warm beige/terracotta or dark slate/neon purple; imagery is project-relative, aspect-ratio matched, and WCAG AA legible without muddy scrims.
- [ ] Transitions run `140ms-240ms` with `cubic-bezier(0.22, 1, 0.36, 1)` on explicit properties (`transform`, `opacity`, `clip-path`); zero `transition: all` / `transition-all` or `ease-in`.
- [ ] `prefers-reduced-motion` is honored; kinetic hero type is visible at rest; native scroll stays intact on tools, news, and data views.

### 4. Controls and visual verification
- [ ] Zero decorative non-interactive chips/badges/tags; mode/filter/size selection uses segmented toggles, tabs, radios, switches, `<select>`, or canvas controls; max one primary CTA per section.
- [ ] Capture and inspect desktop screenshots of both the opening viewport and scrolled below-the-fold sections at true desktop height.
- [ ] Capture and inspect a `390x844` mobile screenshot verifying zero horizontal scroll, readable scale, and reachable navigation.

## Attribution

Adapted from Google DemoLab's `gemini-frontend-design` skill (`https://github.com/google-gemini/demolab`), licensed under Apache-2.0.
