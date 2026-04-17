# Slide Layout Patterns — Frontend Slides Reference

> **Load this file during Phase 4 (BUILD) when building slide HTML structure.**
> The STYLE_PRESETS.md file covers CSS variables and animations; this file covers HTML patterns.

---

## HTML Templates by Slide Type

Use these templates as starting points. All CSS variables (`--bg`, `--accent`, etc.) are
supplied by the chosen preset. Never hard-code colors inside slide HTML.

### Title Slide

```html
<section class="slide slide-title">
  <h1>Presentation Heading</h1>
  <p class="subtitle">Subtitle — max 12 words</p>
</section>
```

```css
.slide-title h1 {
  font-family: var(--heading-font);
  font-size: var(--heading-size);
  letter-spacing: var(--letter-spacing-heading, 0);
  color: var(--text-primary);
  text-align: center;
  max-width: 80%;
}
.slide-title .subtitle {
  font-family: var(--body-font);
  font-size: clamp(1rem, 2vw, 1.5rem);
  color: var(--text-secondary);
  margin-top: 1rem;
  text-align: center;
}
```

---

### Content Slide (4-6 bullets)

```html
<section class="slide slide-content">
  <h2>Section Heading</h2>
  <ul>
    <li>First point — max 10 words</li>
    <li>Second point — max 10 words</li>
    <li>Third point — max 10 words</li>
    <li>Fourth point — max 10 words</li>
  </ul>
</section>
```

```css
.slide-content {
  align-items: flex-start;
}
.slide-content h2 {
  font-family: var(--heading-font);
  font-size: clamp(1.4rem, 3vw, 2.5rem);
  color: var(--accent);
  margin-bottom: clamp(1rem, 3vh, 2rem);
  width: 100%;
}
.slide-content ul {
  list-style: none;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: clamp(0.5rem, 1.5vh, 1rem);
}
.slide-content li {
  font-family: var(--body-font);
  font-size: var(--body-size);
  color: var(--text-primary);
  padding-left: 1.2em;
  position: relative;
}
.slide-content li::before {
  content: '▸';
  position: absolute;
  left: 0;
  color: var(--accent);
}
```

---

### Feature Grid (max 6 cards)

```html
<section class="slide slide-grid">
  <h2>Features</h2>
  <div class="grid">
    <div class="card">
      <span class="icon">⚡</span>
      <strong>Label</strong>
      <span>One-line descriptor</span>
    </div>
    <!-- repeat up to 6 -->
  </div>
</section>
```

```css
.slide-grid .grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(180px, 40%), 1fr));
  gap: clamp(0.75rem, 2vw, 1.5rem);
  width: 100%;
}
.slide-grid .card {
  background: var(--surface);
  border-radius: 0.5rem;
  padding: clamp(0.75rem, 2vw, 1.25rem);
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.slide-grid .icon {
  font-size: clamp(1.5rem, 3vw, 2.5rem);
  line-height: 1;
}
.slide-grid strong {
  font-family: var(--heading-font);
  font-size: clamp(0.9rem, 1.6vw, 1.1rem);
  color: var(--text-primary);
}
.slide-grid span:last-child {
  font-family: var(--body-font);
  font-size: clamp(0.75rem, 1.3vw, 0.95rem);
  color: var(--text-secondary);
}
```

---

### Code Slide (8-10 lines)

```html
<section class="slide slide-code">
  <h2>Code Heading</h2>
  <pre><code class="language-javascript">// 8-10 lines max
function example() {
  return true;
}</code></pre>
</section>
```

```css
.slide-code pre {
  background: var(--surface);
  border-radius: 0.5rem;
  padding: clamp(1rem, 2.5vw, 2rem);
  width: 100%;
  overflow: hidden;          /* never scroll — split slide if needed */
  max-height: min(55vh, 500px);
}
.slide-code code {
  font-family: var(--code-font, 'JetBrains Mono', 'Courier New', monospace);
  font-size: clamp(0.75rem, 1.5vw, 1rem);
  line-height: 1.6;
  color: var(--text-primary);
  white-space: pre;
}
```

---

### Quote Slide

```html
<section class="slide slide-quote">
  <blockquote>
    <p>Quote text — max 30 words.</p>
    <footer>— Name, Title</footer>
  </blockquote>
</section>
```

```css
.slide-quote blockquote {
  max-width: 70%;
  text-align: center;
}
.slide-quote p {
  font-family: var(--heading-font);
  font-size: clamp(1.2rem, 2.5vw, 2rem);
  color: var(--text-primary);
  font-style: italic;
  line-height: 1.5;
}
.slide-quote footer {
  font-family: var(--body-font);
  font-size: clamp(0.85rem, 1.5vw, 1.1rem);
  color: var(--accent);
  margin-top: 1.5rem;
}
```

---

### Image Slide

```html
<section class="slide slide-image">
  <img src="path/to/image.jpg" alt="Descriptive alt text" loading="lazy">
  <p class="caption">Caption — max 10 words</p>
</section>
```

```css
.slide-image img {
  max-width: 100%;
  max-height: min(50vh, 400px);   /* constrained — never fixed height in px alone */
  object-fit: contain;
  border-radius: 0.5rem;
}
.slide-image .caption {
  font-family: var(--body-font);
  font-size: clamp(0.75rem, 1.3vw, 0.95rem);
  color: var(--text-secondary);
  margin-top: 1rem;
  text-align: center;
}
```

---

### Section Break Slide

```html
<section class="slide slide-break">
  <h2>Section Name</h2>
</section>
```

```css
.slide-break {
  background: var(--accent);
}
.slide-break h2 {
  font-family: var(--heading-font);
  font-size: clamp(2rem, 6vw, 5rem);
  color: var(--bg);             /* inverted — accent bg, bg-colored text */
  letter-spacing: var(--letter-spacing-heading, 0);
  text-align: center;
}
```

---

<!-- no-pair-required: section heading — each Anti-Pattern block below has its own Do-instead -->
## Overflow Anti-Pattern Catalog

### Anti-Pattern 1: Fixed inner height

**Detection**:
```bash
grep -n 'height: [0-9]*px' output.html | grep -v 'max-height\|min-height'
rg 'height:\s*\d+px' output.html | grep -v 'max-height'
```

**Wrong**:
```css
.slide img { height: 300px; }
.slide pre  { height: 400px; }
```

**Why wrong**: Fixed pixel heights overflow at viewport heights below their value. A 300px image
on an iPhone landscape (414px tall) leaves barely 100px for heading + caption.

**Fix**: `max-height: min(Xvh, Ypx)` with `overflow: hidden`. For images: `max-height: min(50vh, 400px)`.

**Do instead**

```css
/* Images: viewport-relative cap prevents overflow at any screen height */
.slide img { max-height: min(50vh, 400px); object-fit: contain; }

/* Code blocks: cap at 55vh so heading and padding always fit */
.slide-code pre { max-height: min(55vh, 500px); overflow: hidden; }
```

---

### Anti-Pattern 2: `min-height` on `.slide`

**Detection**:
```bash
grep -n 'min-height' output.html | grep 'slide'
rg 'min-height.*slide|\.slide.*min-height' output.html
```

**Wrong**:
```css
.slide { min-height: 100vh; }
```

**Why wrong**: `min-height` allows the slide to grow taller than the viewport if content is
long, breaking the single-screen constraint. The validation script will report overflow at
small breakpoints.

**Fix**: Use `height: 100vh; height: 100dvh` (exact, not minimum). Split content across
multiple slides if it overflows.

**Do instead**

```css
.slide {
  height: 100vh;
  height: 100dvh;   /* exact viewport height — slide cannot grow beyond one screen */
  overflow: hidden;
}
```

---

### Anti-Pattern 3: Nested bullets

**Detection**:
```bash
grep -n '<ul>.*<ul>\|<li>.*<ul>' output.html
rg '<ul>[^<]*<li>[^<]*<ul>' output.html
```

**Wrong**:
```html
<ul>
  <li>Top level
    <ul><li>Nested bullet</li></ul>
  </li>
</ul>
```

**Why wrong**: Nested lists double the line count and violate the density limit (max 6 bullets).
At small viewports, nested indentation causes overflow. Presentation slides are not documents.

**Fix**: Flatten to a single level. Convert nested items to separate bullet points or a separate
slide. Each bullet is max 10 words.

**Do instead**

```html
<!-- Flat single-level list — each point is self-contained, max 10 words -->
<ul>
  <li>First concept — brief and specific</li>
  <li>Second concept — brief and specific</li>
  <li>Third concept — brief and specific</li>
  <!-- If a sub-point is needed, make it a separate slide -->
</ul>
```

---

### Anti-Pattern 4: Long `<pre>` block without overflow guard

Do instead: add `max-height: min(55vh, 500px); overflow: hidden` to `.slide-code pre`.

**Detection**:
```bash
grep -c '<pre>' output.html
# If count > 0, verify overflow: hidden is present
grep -A5 '<pre>' output.html | grep 'overflow'
```

**Wrong**:
```css
.slide-code pre { max-width: 100%; }  /* no height or overflow constraint */
```

**Why wrong**: A 15-line code block at `font-size: 1rem` is ~300px tall. On a 720px projector,
that leaves 420px for the slide heading, padding, and navigation chrome — it overflows at small
breakpoints.

**Fix**: `max-height: min(55vh, 500px); overflow: hidden`. If the code block overflows even with
the cap, split it across two slides with a continuation heading.

**Do instead**

```css
.slide-code pre {
  max-height: min(55vh, 500px);
  overflow: hidden;   /* content is clipped, not scrolled — split slides if needed */
  width: 100%;
  border-radius: 0.5rem;
}
```

---

### Anti-Pattern 5: Hard-coded colors in slide HTML

**Detection**:
```bash
grep -n 'color: #\|background: #\|background-color: #' output.html | grep -v ':root\|var(--'
rg 'color:\s*#[0-9a-fA-F]' output.html | grep -v ':root'
```

**Wrong**:
```css
.slide-title h1 { color: #F5F0E8; }  /* hard-coded — breaks when preset changes */
```

**Why wrong**: Hard-coded colors survive preset swaps intact, causing mismatched palettes.
If the user changes from `obsidian-gold` to `arctic-minimal`, the heading stays near-white on
a now-white background, making text invisible.

**Fix**: Use only CSS custom properties defined by the preset: `color: var(--text-primary)`.
Never reference a hex value outside of `:root { }`.

**Do instead**

```css
/* All color references use preset CSS variables — swap the preset, colors update automatically */
.slide-title h1    { color: var(--text-primary); }
.slide-title .subtitle { color: var(--text-secondary); }
.slide-content li  { color: var(--text-primary); }
.slide-content li::before { color: var(--accent); }
/* Hex values live only in :root {} inside the chosen preset stylesheet */
```

---

## Density Quick-Check

Before Gate 4, run this check for each slide:

```bash
# Count bullets on each slide
grep -c '<li>' output.html
# Flag any slide section with more than 6
python3 -c "
import re, sys
html = open('output.html').read()
slides = re.findall(r'<section[^>]*class=\"slide[^\"]*\"[^>]*>(.*?)</section>', html, re.DOTALL)
for i, s in enumerate(slides, 1):
    n = len(re.findall(r'<li>', s))
    if n > 6:
        print(f'Slide {i}: {n} bullets (exceeds limit of 6)')
"
```

---

## Error-Fix Mapping

| Symptom | Root Cause | Detection Command | Fix |
|---------|-----------|-------------------|-----|
| Overflow at 375×667 only | Fixed px height on inner element | `rg 'height:\s*\d+px' output.html` | Replace with `max-height: min(Xvh, Ypx)` |
| Slide taller than viewport | `min-height` instead of `height` | `grep 'min-height.*slide' output.html` | Use exact `height: 100vh; height: 100dvh` |
| Text invisible after preset change | Hard-coded hex colors in slide CSS | `rg 'color:\s*#' output.html` | Replace with `var(--text-primary)` etc. |
| Code block pushes heading off-screen | `<pre>` lacks height cap | `grep -A5 '<pre>' output.html \| grep overflow` | Add `max-height: min(55vh, 500px); overflow: hidden` |
| Slide has 8 bullets | Content not split | `grep -c '<li>' output.html` | Split into two slides at bullet 5-6 |
| Nested bullets in DOM | Source content had sub-bullets | `grep '<li>.*<ul>' output.html` | Flatten to single level; new slide for overflow |
