# STYLE_PRESETS — Frontend Slides Reference

> **Load this file during Phase 3 (DISCOVER STYLE) and Phase 4 (BUILD).**
> Do not load it during Phase 1 or 2 — it is not needed until style selection begins.

---

## Mandatory CSS Base Block

Copy this block verbatim into every output HTML file. Apply theme variables on top of it.
Do not paraphrase, restructure, or omit any rule. Gate 4 verifies this block is present by
string match.

```css
/* === MANDATORY BASE — copy verbatim, theme on top === */
*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html, body {
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.deck {
  width: 100%;
  height: 100vh;
  height: 100dvh;
  overflow: hidden;
  scroll-snap-type: x mandatory;
  display: flex;
}

.slide {
  flex: 0 0 100%;
  width: 100%;
  height: 100vh;
  height: 100dvh;
  overflow: hidden;
  scroll-snap-align: start;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: clamp(1.5rem, 5vw, 4rem);
  padding-top: max(clamp(1.5rem, 5vw, 4rem), env(safe-area-inset-top, 0px));
  padding-bottom: max(clamp(1.5rem, 5vw, 4rem), env(safe-area-inset-bottom, 0px));
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
/* === END MANDATORY BASE === */
```

---

## CSS Gotchas

Apply these rules without exception. They are silent failure modes, not stylistic preferences.

| Gotcha | Wrong | Right | Why |
|--------|-------|-------|-----|
| Negated clamp | `-clamp(2rem, 3vw, 4rem)` | `calc(-1 * clamp(2rem, 3vw, 4rem))` | Unary minus before a CSS function is silently ignored — the value resolves to `0`, causing text collapse or invisible elements |
| Dynamic viewport height | `height: 100vh` only | `height: 100vh; height: 100dvh` | `100vh` includes the browser chrome on mobile; `100dvh` uses the dynamic viewport. Declare both so browsers that support `dvh` use it |
| Font display | `@font-face { src: ... }` | `@font-face { src: ...; font-display: swap; }` | Without `font-display: swap`, text is invisible during font load (FOIT) |
| Fixed inner heights | `height: 300px` on image containers | `max-height: min(50vh, 300px)` | Fixed pixel heights overflow on small viewports |
| Viewport-fit meta | Missing | `<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">` | Required for safe-area-inset on notched devices and for correct `dvh` calculation |
| `display: none` on slides | `display: none` to hide slides | `opacity: 0; pointer-events: none; position: absolute` | `display: none` removes elements from the accessibility tree and prevents Intersection Observer callbacks |

---

## Density Limits by Slide Type

Enforce these limits without exception. When content exceeds a limit, split into a new slide.

| Slide Type | Content Limit | Notes |
|------------|--------------|-------|
| Title | 1 heading + 1 subtitle | No bullets. Subtitle max 12 words. |
| Content | 4–6 bullets | Each bullet max 10 words. No nested bullets. |
| Feature grid | 6 cards max | Card: icon + 1-line label + 1-line descriptor |
| Code | 8–10 lines | Font: monospace. `font-size: clamp(0.75rem, 1.5vw, 1rem)`. Syntax highlight allowed. |
| Quote | 1 quote + 1 attribution | Quote max 30 words. Attribution: name + title only. |
| Image | 1 image, constrained | `max-height: min(50vh, 400px)`. Caption max 10 words. |
| Section break | 1 word or short phrase | Full-bleed background color. No body text. |

---

## Validation Breakpoints

Run `validate-slides.py` at all 9 breakpoints. Zero overflows required to pass Gate 5.

| Breakpoint | Width | Height | Context |
|------------|-------|--------|---------|
| 1920×1080 | 1920 | 1080 | Standard desktop / projector |
| 1440×900 | 1440 | 900 | MacBook 15" |
| 1280×720 | 1280 | 720 | HD projector |
| 1024×768 | 1024 | 768 | Older projector / iPad landscape |
| 768×1024 | 768 | 1024 | iPad portrait |
| 375×667 | 375 | 667 | iPhone SE |
| 414×896 | 414 | 896 | iPhone 11/XR |
| 667×375 | 667 | 375 | iPhone landscape |
| 896×414 | 896 | 414 | iPhone 11 landscape |

---

## 12 Named Style Presets

### Preset 1: obsidian-gold

**Mood**: impressed, authoritative
**Use case**: executive briefings, board presentations, high-stakes pitches
**Palette**: Near-black background (#0D0D0D), warm gold accent (#C9A84C), off-white text (#F5F0E8)
**Font pairing**: heading: "Playfair Display" serif; body: "Inter" sans-serif
**Signature**: Deep contrast, restrained gold accents, wide letter-spacing on headings

```css
:root {
  --bg: #0D0D0D;
  --surface: #1A1A1A;
  --accent: #C9A84C;
  --text-primary: #F5F0E8;
  --text-secondary: #A89880;
  --heading-font: 'Playfair Display', Georgia, serif;
  --body-font: 'Inter', system-ui, sans-serif;
  --heading-size: clamp(2rem, 5vw, 4rem);
  --body-size: clamp(1rem, 2vw, 1.4rem);
  --letter-spacing-heading: 0.05em;
}
```

---

### Preset 2: arctic-minimal

**Mood**: focused, clean, technical
**Use case**: engineering talks, developer conferences, technical deep-dives
**Palette**: Pure white background (#FFFFFF), near-black text (#111111), electric blue accent (#0057FF)
**Font pairing**: heading: "DM Sans" sans-serif; body: "DM Sans" sans-serif; code: "JetBrains Mono"
**Signature**: Maximum whitespace, thin rules, blue for emphasis only

```css
:root {
  --bg: #FFFFFF;
  --surface: #F4F4F5;
  --accent: #0057FF;
  --text-primary: #111111;
  --text-secondary: #555555;
  --heading-font: 'DM Sans', system-ui, sans-serif;
  --body-font: 'DM Sans', system-ui, sans-serif;
  --heading-size: clamp(1.8rem, 4vw, 3.5rem);
  --body-size: clamp(0.95rem, 1.8vw, 1.3rem);
  --letter-spacing-heading: -0.02em;
}
```

---

### Preset 3: carbon-ember

**Mood**: energized, bold, startup
**Use case**: product launches, startup pitches, high-energy keynotes
**Palette**: Charcoal background (#1C1C1E), ember orange accent (#FF5F1F), white text (#FFFFFF)
**Font pairing**: heading: "Space Grotesk" sans-serif; body: "Inter" sans-serif
**Signature**: Bold weight headings, orange used for numbers and key terms, no gradients

```css
:root {
  --bg: #1C1C1E;
  --surface: #2C2C2E;
  --accent: #FF5F1F;
  --text-primary: #FFFFFF;
  --text-secondary: #AEAEB2;
  --heading-font: 'Space Grotesk', system-ui, sans-serif;
  --body-font: 'Inter', system-ui, sans-serif;
  --heading-size: clamp(2rem, 4.5vw, 3.8rem);
  --body-size: clamp(1rem, 2vw, 1.4rem);
  --letter-spacing-heading: -0.03em;
}
```

---

### Preset 4: sage-paper

**Mood**: inspired, thoughtful, editorial
**Use case**: thought leadership talks, creative presentations, narrative-heavy decks
**Palette**: Warm paper (#FAF7F2), sage green accent (#4A7C59), dark brown text (#2C2416)
**Font pairing**: heading: "Lora" serif; body: "Source Sans 3" sans-serif
**Signature**: Organic warmth, editorial line lengths, serif headings for credibility

```css
:root {
  --bg: #FAF7F2;
  --surface: #F0EBE1;
  --accent: #4A7C59;
  --text-primary: #2C2416;
  --text-secondary: #6B5E4A;
  --heading-font: 'Lora', Georgia, serif;
  --body-font: 'Source Sans 3', system-ui, sans-serif;
  --heading-size: clamp(1.8rem, 4vw, 3.2rem);
  --body-size: clamp(1rem, 1.9vw, 1.35rem);
  --letter-spacing-heading: 0em;
}
```

---

### Preset 5: void-neon

**Mood**: energized, futuristic, tech
**Use case**: developer tools demos, AI product launches, late-night hackathon decks
**Palette**: Deep black (#000000), neon cyan accent (#00FFD1), electric purple secondary (#9B59FF), gray text (#CCCCCC)
**Font pairing**: heading: "Orbitron" display; body: "Share Tech Mono" monospace
**Signature**: Terminal aesthetic, monospace body, neon glow on headings via text-shadow

```css
:root {
  --bg: #000000;
  --surface: #0A0A0A;
  --accent: #00FFD1;
  --accent-2: #9B59FF;
  --text-primary: #CCCCCC;
  --text-secondary: #666666;
  --heading-font: 'Orbitron', 'Courier New', monospace;
  --body-font: 'Share Tech Mono', 'Courier New', monospace;
  --heading-size: clamp(1.6rem, 3.5vw, 3rem);
  --body-size: clamp(0.9rem, 1.7vw, 1.2rem);
  --letter-spacing-heading: 0.1em;
  --heading-glow: 0 0 20px var(--accent);
}
```

---

### Preset 6: slate-coral

**Mood**: impressed, contemporary, SaaS
**Use case**: SaaS product reviews, customer-facing demos, sales enablement
**Palette**: Slate blue background (#2D3561), coral accent (#F07057), light text (#EEF2FF)
**Font pairing**: heading: "Nunito Sans" sans-serif; body: "Nunito Sans" sans-serif
**Signature**: Rounded letterforms, approachable but professional, coral for CTAs and data points

```css
:root {
  --bg: #2D3561;
  --surface: #3A4475;
  --accent: #F07057;
  --text-primary: #EEF2FF;
  --text-secondary: #A8B4D8;
  --heading-font: 'Nunito Sans', system-ui, sans-serif;
  --body-font: 'Nunito Sans', system-ui, sans-serif;
  --heading-size: clamp(1.9rem, 4.2vw, 3.5rem);
  --body-size: clamp(1rem, 1.9vw, 1.35rem);
  --letter-spacing-heading: -0.01em;
}
```

---

### Preset 7: chalk-board

**Mood**: focused, educational, approachable
**Use case**: workshops, onboarding sessions, training material, academic talks
**Palette**: Chalkboard green (#2B4A3B), chalk white text (#F0F0E8), amber highlight (#FFB830)
**Font pairing**: heading: "Kalam" handwriting; body: "Open Sans" sans-serif
**Signature**: Soft handwriting heading for warmth, clean body for readability, amber for emphasis

```css
:root {
  --bg: #2B4A3B;
  --surface: #3A5C4A;
  --accent: #FFB830;
  --text-primary: #F0F0E8;
  --text-secondary: #B8CCC0;
  --heading-font: 'Kalam', cursive, sans-serif;
  --body-font: 'Open Sans', system-ui, sans-serif;
  --heading-size: clamp(1.9rem, 4vw, 3.4rem);
  --body-size: clamp(1rem, 1.9vw, 1.35rem);
  --letter-spacing-heading: 0.01em;
}
```

---

### Preset 8: glacier-blue

**Mood**: focused, trusted, corporate
**Use case**: financial presentations, legal briefings, healthcare, compliance decks
**Palette**: White background (#FFFFFF), glacier blue accent (#0077B6), navy text (#03045E), gray surface (#E8F4FD)
**Font pairing**: heading: "Libre Baskerville" serif; body: "Roboto" sans-serif
**Signature**: High-trust serif headings, conservative palette, no decorative elements

```css
:root {
  --bg: #FFFFFF;
  --surface: #E8F4FD;
  --accent: #0077B6;
  --text-primary: #03045E;
  --text-secondary: #48607A;
  --heading-font: 'Libre Baskerville', Georgia, serif;
  --body-font: 'Roboto', system-ui, sans-serif;
  --heading-size: clamp(1.7rem, 3.8vw, 3.2rem);
  --body-size: clamp(0.95rem, 1.8vw, 1.3rem);
  --letter-spacing-heading: 0.01em;
}
```

---

### Preset 9: rose-noir

**Mood**: impressed, artistic, luxury
**Use case**: fashion, design portfolios, luxury brand presentations, creative agency pitches
**Palette**: Off-black background (#0F0F0F), dusty rose accent (#C97B84), warm white text (#FAF0E6)
**Font pairing**: heading: "Cormorant Garamond" display serif; body: "Raleway" sans-serif
**Signature**: High-fashion contrast, delicate serif for elegance, restrained rose for warmth

```css
:root {
  --bg: #0F0F0F;
  --surface: #1A1A1A;
  --accent: #C97B84;
  --text-primary: #FAF0E6;
  --text-secondary: #9E8E88;
  --heading-font: 'Cormorant Garamond', 'Palatino Linotype', serif;
  --body-font: 'Raleway', system-ui, sans-serif;
  --heading-size: clamp(2rem, 4.5vw, 4rem);
  --body-size: clamp(0.95rem, 1.8vw, 1.3rem);
  --letter-spacing-heading: 0.08em;
}
```

---

### Preset 10: solar-sand

**Mood**: inspired, warm, community
**Use case**: non-profit presentations, community talks, cultural events, sustainability reports
**Palette**: Sand background (#F5E6C8), terracotta accent (#C1440E), espresso text (#2C1810)
**Font pairing**: heading: "Merriweather" serif; body: "Lato" sans-serif
**Signature**: Earthy warmth, high readability, terracotta anchors the palette without aggression

```css
:root {
  --bg: #F5E6C8;
  --surface: #EDD9A3;
  --accent: #C1440E;
  --text-primary: #2C1810;
  --text-secondary: #7A5C4A;
  --heading-font: 'Merriweather', Georgia, serif;
  --body-font: 'Lato', system-ui, sans-serif;
  --heading-size: clamp(1.8rem, 4vw, 3.2rem);
  --body-size: clamp(1rem, 1.9vw, 1.35rem);
  --letter-spacing-heading: 0.02em;
}
```

---

### Preset 11: steel-wire

**Mood**: focused, industrial, data-heavy
**Use case**: data science talks, infrastructure reviews, systems architecture, DevOps
**Palette**: Steel gray background (#1E2329), wire yellow accent (#F0E130), cool white text (#E8EAF0)
**Font pairing**: heading: "IBM Plex Sans" sans-serif; body: "IBM Plex Sans" sans-serif; code: "IBM Plex Mono"
**Signature**: Dense information layout, high contrast for readability in dim rooms, yellow for callouts

```css
:root {
  --bg: #1E2329;
  --surface: #2C3340;
  --accent: #F0E130;
  --text-primary: #E8EAF0;
  --text-secondary: #8892A4;
  --heading-font: 'IBM Plex Sans', system-ui, sans-serif;
  --body-font: 'IBM Plex Sans', system-ui, sans-serif;
  --code-font: 'IBM Plex Mono', 'Courier New', monospace;
  --heading-size: clamp(1.7rem, 3.8vw, 3rem);
  --body-size: clamp(0.9rem, 1.7vw, 1.25rem);
  --letter-spacing-heading: 0em;
}
```

---

### Preset 12: lavender-mist

**Mood**: inspired, calm, wellness
**Use case**: mental health talks, wellness brands, meditation apps, gentle product intros
**Palette**: Lavender white background (#F3F0FA), soft violet accent (#7B5EA7), warm gray text (#3A3550)
**Font pairing**: heading: "Quicksand" rounded sans-serif; body: "Nunito" rounded sans-serif
**Signature**: Soft rounded letterforms, muted palette, no sharp edges, gentle transitions

```css
:root {
  --bg: #F3F0FA;
  --surface: #E8E2F5;
  --accent: #7B5EA7;
  --text-primary: #3A3550;
  --text-secondary: #7A7090;
  --heading-font: 'Quicksand', system-ui, sans-serif;
  --body-font: 'Nunito', system-ui, sans-serif;
  --heading-size: clamp(1.8rem, 4vw, 3.2rem);
  --body-size: clamp(1rem, 1.9vw, 1.35rem);
  --letter-spacing-heading: 0.02em;
}
```

---

## Mood-to-Preset Mapping

Use this table when a user gives a mood word rather than a preset name. Offer the top 3
candidates as single-slide preview files. The user selects — do not choose on their behalf.

| Mood Word | Primary Preset | Secondary Preset | Tertiary Preset |
|-----------|---------------|-----------------|----------------|
| impressed | obsidian-gold | rose-noir | glacier-blue |
| authoritative | obsidian-gold | glacier-blue | steel-wire |
| energized | carbon-ember | void-neon | slate-coral |
| bold | carbon-ember | void-neon | steel-wire |
| focused | arctic-minimal | steel-wire | glacier-blue |
| technical | arctic-minimal | void-neon | steel-wire |
| inspired | sage-paper | solar-sand | lavender-mist |
| thoughtful | sage-paper | chalk-board | solar-sand |
| warm | solar-sand | chalk-board | sage-paper |
| clean | arctic-minimal | glacier-blue | slate-coral |
| dramatic | rose-noir | obsidian-gold | void-neon |
| calm | lavender-mist | sage-paper | glacier-blue |
| futuristic | void-neon | steel-wire | carbon-ember |
| professional | glacier-blue | obsidian-gold | slate-coral |
| creative | rose-noir | sage-paper | solar-sand |

---

## Animation Feel Mapping

Apply the appropriate animation approach based on preset character. Do not swap these.
All animations must be suppressed under `prefers-reduced-motion: reduce`.

| Preset | Enter Animation | Duration | Easing |
|--------|----------------|----------|--------|
| obsidian-gold | fade + subtle upward translate | 600ms | cubic-bezier(0.4, 0, 0.2, 1) |
| arctic-minimal | fade only | 300ms | ease |
| carbon-ember | slide from right | 400ms | cubic-bezier(0.25, 0.46, 0.45, 0.94) |
| sage-paper | fade + scale from 0.98 | 500ms | ease-out |
| void-neon | fade + scale from 1.02 with glow | 400ms | cubic-bezier(0, 0, 0.2, 1) |
| slate-coral | slide from bottom | 350ms | cubic-bezier(0.34, 1.56, 0.64, 1) |
| chalk-board | fade + slight rotate from -1deg | 450ms | ease-out |
| glacier-blue | fade only | 250ms | ease |
| rose-noir | fade + upward translate | 550ms | cubic-bezier(0.4, 0, 0.2, 1) |
| solar-sand | fade + scale from 0.97 | 500ms | ease-out |
| steel-wire | slide from left | 300ms | cubic-bezier(0.25, 0.46, 0.45, 0.94) |
| lavender-mist | fade + scale from 0.98 | 600ms | ease |
