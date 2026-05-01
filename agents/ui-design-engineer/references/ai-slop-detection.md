# AI Slop Detection

<!-- Loaded by ui-design-engineer when task involves AI slop, generic UI, AI-generated look, template look, or default styling -->

Detect and fix the 8 most common patterns that make AI-generated UI look generic. Each pattern below starts with the correct approach, then provides a detection command for auditing existing code.

## Use Purposeful Gradients

Gradients serve a visual purpose: directing attention, creating depth, or establishing atmosphere. Aggressive multi-color gradients with 3+ color stops — the rainbow-adjacent backgrounds AI defaults to — signal that no design decision was made. Use single-hue gradients (e.g., dark blue to slightly lighter blue) or solid backgrounds. A gradient earns its place when it creates a mood, not when it fills a blank.

```css
/* Correct: single-hue gradient creating subtle depth */
background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);

/* Correct: solid background with texture for interest */
background-color: #fafaf9;
```

**Keep if:** The design specification calls for a multi-stop gradient and provides the exact color stops with a visual rationale. Brand gradients with 3+ stops exist (Instagram, Stripe).

**Detection:**
```bash
rg 'linear-gradient|radial-gradient' --include='*.css' --include='*.tsx' --include='*.jsx' --include='*.html' | grep -E '(#[0-9a-fA-F]{3,8}|rgb|hsl|oklch).*,.*,.*,'
```
Flag any gradient with 3 or more color stops for manual review.

---

## Reserve Emoji for Brand Context

Emoji used as decorative section markers — a rocket before "Features", a sparkle before "Benefits" — is an AI tell. It adds visual noise without communicating information. Use SVG icons from a coherent icon set (Lucide, Heroicons, Phosphor) or text-only headings. Emoji belongs in conversational UI (chat, notifications, reactions) where informal tone is the point, not in marketing or product sections where it cheapens the message.

```html
<!-- Correct: icon from a coherent set -->
<h2><LucideIcon name="zap" size={20} /> Performance</h2>

<!-- Correct: text-only heading with typographic hierarchy -->
<h2>Performance</h2>
```

**Keep if:** The brand voice is deliberately casual (Discord, Notion) and emoji is part of the documented brand identity, not a default choice.

**Detection:**
```bash
rg '[\x{1F300}-\x{1F9FF}\x{2600}-\x{26FF}\x{2700}-\x{27BF}]' --include='*.tsx' --include='*.jsx' --include='*.html' -n
```
Flag emoji inside heading elements (`h1`-`h6`), label elements, or button text for review.

---

## Design Cards Without Left-Border Accent

The `border-radius: 12px` card with `border-left: 4px solid {accent}` is the single most common AI card pattern. It appears in virtually every AI-generated dashboard and feature grid. Use full borders, subtle box shadows, or no border at all. If you need to indicate category or status, use a small color dot, a tag, or a tinted background — not a left border accent.

```css
/* Correct: shadow-based card separation */
.card {
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  border: 1px solid #e5e5e5;
}

/* Correct: no border, background differentiation */
.card {
  border-radius: 8px;
  background: #f8f8f8;
}
```

**Keep if:** The left border accent is part of a documented design system with a specific semantic meaning (e.g., VS Code's panel indicators, GitHub's diff markers).

**Detection:**
```bash
rg 'border-left:.*solid' --include='*.css' --include='*.tsx' --include='*.jsx' -n
```
Cross-reference hits with `border-radius` in the same rule or component. The combination is the signal.

---

## Use Professional Illustration or Photography

AI defaults to hand-drawn, sketchy SVG illustrations — wobbly lines, friendly blob shapes, stick-figure-adjacent characters. These look like placeholder art that shipped by accident. Use real photography, professional vector illustration from a licensed set (unDraw with customization, Storyset), or honest placeholders (see `honest-placeholders.md` in `skills/distinctive-frontend-design/references/`). An honest "image needed" placeholder is better than a bad illustration that looks intentional.

```html
<!-- Correct: real photography with proper alt text -->
<img src="/images/team-photo.jpg" alt="Engineering team at the Portland office" />

<!-- Correct: honest placeholder when real assets are not ready -->
<div class="placeholder">product hero (1200x800)</div>
```

**Keep if:** The hand-drawn style is an intentional brand choice (Notion's illustrations, Balsamiq's wireframe aesthetic) and appears in the brand guide.

**Detection:** Look for inline `<svg>` elements with irregular path data (many short arc and curve commands). AI-generated SVG illustrations tend to have dense `d` attributes with numerous `C`, `Q`, and `A` commands in rapid succession.

---

## Select Contextual Fonts

Inter, Roboto, Arial, Helvetica, and system font stacks are invisible from overuse. They are not bad fonts — they are absent fonts. Selecting them means no typographic decision was made. Choose fonts from a curated catalog that match the project's aesthetic direction, audience, and emotional tone. A portfolio site for a photographer and a SaaS billing dashboard should not share a typeface.

```css
/* Correct: font selected for the project's context */
font-family: 'Instrument Serif', Georgia, serif;

/* Correct: distinctive sans for a tech product */
font-family: 'Geist', system-ui, sans-serif;
```

**Keep if:** The brand specification explicitly names Inter, Roboto, or a system font as the brand typeface. A deliberate choice to use Inter is different from defaulting to it.

**Detection:**
```bash
rg -i 'font-family.*\b(Inter|Roboto|Arial|Helvetica|system-ui)\b' --include='*.css' --include='*.tsx' --include='*.jsx' --include='*.html' -n
```

---

## Use Near-Black and Near-White

Pure `#000000` and `#FFFFFF` are harsh on screens and signal default choices — no one picked these colors, the tool did. Use near-black (e.g., `#1a1a2e`, `oklch(15% 0.02 260)`) and near-white (e.g., `#fafaf9`, `oklch(98% 0.005 80)`) to soften the palette without losing contrast. The difference is subtle but immediate: near-variants feel designed, pure values feel default.

```css
/* Correct: near-black and near-white */
:root {
  --text-primary: #1a1a2e;
  --bg-surface: #fafaf9;
}

/* Correct: oklch for perceptually tuned values */
:root {
  --text-primary: oklch(15% 0.02 260);
  --bg-surface: oklch(98% 0.005 80);
}
```

**Keep if:** The design specification explicitly uses `#000` or `#FFF` for a high-contrast brutalist aesthetic, or the context is a code editor / terminal theme where pure black backgrounds are conventional.

**Detection:**
```bash
rg -i '#000000|#ffffff|#000\b|#fff\b' --include='*.css' --include='*.tsx' --include='*.jsx' --include='*.html' -n
```

---

## Derive Colors from Context

Random hex values with no relationship to each other — `#4f46e5` next to `#10b981` next to `#f59e0b` — signal AI generation. Every color in a palette should trace back to a source: the brand guide, a cultural reference, a material inspiration, or a deliberate harmony relationship (analogous, complementary, triadic). Colors derived from context feel inevitable. Random colors feel assembled.

```css
/* Correct: palette derived from Japanese indigo dyeing */
:root {
  --indigo-deep: oklch(25% 0.08 250);   /* ai-iro (indigo) */
  --indigo-mid: oklch(45% 0.12 248);    /* hanada (flower-field blue) */
  --indigo-light: oklch(85% 0.04 250);  /* kamenozoki (peek of the turtle) */
}
```

**Keep if:** The colors come from an established design system (Tailwind's palette, Material Design) where the relationships are already defined.

**Detection:** Check whether color values appear in the project's design specification, brand guide, or a documented palette source. Colors that cannot be traced to a source need justification. See `oklch-color-harmony.md` (in `skills/distinctive-frontend-design/references/`) for the technique to build harmonious palettes from context.

---

## Snap Spacing to a Scale

Values like `padding: 7px`, `margin: 13px`, or `gap: 18px` that do not fit a 4px or 8px grid are AI tells. Designers work on scales. AI generates plausible-looking numbers. All spacing, padding, margin, and gap values should snap to 4px increments (4, 8, 12, 16, 20, 24, 32, 40, 48, 64). Font sizes should snap to a typographic scale.

```css
/* Correct: all values on a 4px grid */
.card {
  padding: 16px;
  margin-bottom: 24px;
  gap: 12px;
  border-radius: 8px;
}
```

**Keep if:** The value is 1px or 2px for borders, outlines, or dividers — these are structural, not spacing. `--allow 1,2` in the design scale checker handles this.

**Detection:**
```bash
python3 scripts/design-scale-check.py path/to/styles.css
```
The script flags any `px` value that is not a multiple of 4 (configurable via `--base`). See `scripts/design-scale-check.py` for full usage.
