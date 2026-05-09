# Shape: Slide Deck

Loaded when `detect-shape.py` returns `deck`. For artifacts that present information as navigable slides: talk slides, pitch decks, training presentations, lightning talks.

**Theme:** Dark Focus (default). Slides use a dark background with high-contrast text. Light theme available via the standard toggle.

**Core principle:** Slides are FOCUSED. One idea per slide. Large text, minimal detail, strong visual hierarchy. The deck is a narrative arc, not a document reformatted as slides.

---

## Layout Patterns

| Layout | Use When | Structure |
|---|---|---|
| Standard deck | General presentations | 16:9 container, arrow-key nav, progress bar |
| Code-heavy deck | Technical talks, tutorials | Standard deck + code slides with syntax highlighting |
| Pitch deck | Product pitches, proposals | Standard deck + metric slides, split layouts |

### Slide Container

Every deck uses this outer structure. Fixed 16:9 aspect ratio, centered on page.

```html
<div class="deck-wrapper">
  <div class="slide-deck" id="slide-deck" role="region" aria-label="Slide presentation"
       aria-roledescription="carousel">

    <!-- Slide 1: Title -->
    <div class="slide active" role="group" aria-roledescription="slide"
         aria-label="Slide 1 of 8: Title">
      <!-- Slide content -->
    </div>

    <!-- Slide 2 -->
    <div class="slide" role="group" aria-roledescription="slide"
         aria-label="Slide 2 of 8: Overview">
      <!-- Slide content -->
    </div>

    <!-- More slides... -->
  </div>

  <!-- Navigation -->
  <div class="deck-controls">
    <button class="deck-btn" id="btn-prev" aria-label="Previous slide"
            onclick="prevSlide()">&#8592;</button>
    <span class="slide-counter" id="slide-counter" aria-live="polite">1 / 8</span>
    <button class="deck-btn" id="btn-next" aria-label="Next slide"
            onclick="nextSlide()">&#8594;</button>
  </div>

  <!-- Progress bar -->
  <div class="progress-bar" role="progressbar" aria-label="Slide progress"
       aria-valuenow="1" aria-valuemin="1" aria-valuemax="8">
    <div class="progress-fill" id="progress-fill"></div>
  </div>

  <!-- Presenter notes panel (hidden by default) -->
  <div class="notes-panel" id="notes-panel" hidden aria-label="Presenter notes">
    <h3>Notes</h3>
    <div id="notes-content"></div>
  </div>
</div>
```

```css
/* --- Deck Wrapper --- */
.deck-wrapper {
  max-width: 960px;
  margin: var(--sp-6) auto;
  position: relative;
}

/* --- Slide Container --- */
.slide-deck {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  background: var(--color-bg, #1a1a19);
  border: 1px solid var(--color-border, var(--border-subtle));
  border-radius: var(--radius-md);
  overflow: hidden;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.2);
}

/* --- Individual Slide --- */
.slide {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: var(--sp-8) var(--sp-10);
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.3s ease;
}

.slide.active {
  opacity: 1;
  pointer-events: auto;
}

@media (prefers-reduced-motion: reduce) {
  .slide {
    transition: none;
  }
}

/* --- Navigation Controls --- */
.deck-controls {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--sp-4);
  margin-top: var(--sp-4);
}

.deck-btn {
  all: unset;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--color-surface, var(--bg-muted));
  color: var(--color-text, var(--text-primary));
  font-size: 18px;
  cursor: pointer;
  border: 1px solid var(--color-border, var(--border-subtle));
  transition: background 0.15s ease;
}

.deck-btn:hover {
  background: color-mix(in srgb, var(--color-primary) 15%, var(--color-surface, var(--bg-muted)));
}

.deck-btn:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.deck-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.slide-counter {
  font-family: var(--font-mono);
  font-size: var(--type-small);
  color: var(--color-text-secondary, var(--text-muted));
  min-width: 60px;
  text-align: center;
}

/* --- Progress Bar --- */
.progress-bar {
  height: 3px;
  background: var(--color-border, var(--border-subtle));
  border-radius: 2px;
  margin-top: var(--sp-3);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--color-primary);
  border-radius: 2px;
  transition: width 0.3s ease;
  width: 12.5%; /* 1/total slides */
}

@media (prefers-reduced-motion: reduce) {
  .progress-fill {
    transition: none;
  }
}

/* --- Responsive: smaller screens get smaller padding --- */
@media (max-width: 768px) {
  .slide {
    padding: var(--sp-5) var(--sp-6);
  }
}

@media (max-width: 480px) {
  .slide {
    padding: var(--sp-4) var(--sp-5);
  }
}
```

---

## Slide Types

### Title Slide

Opening slide with deck title, subtitle, and optional author/date.

```html
<div class="slide slide-title active" role="group" aria-roledescription="slide"
     aria-label="Slide 1 of 8: Title" data-notes="Welcome the audience. Set context for the talk.">
  <h1 class="slide-hero">Building Resilient APIs</h1>
  <p class="slide-subtitle">Patterns for graceful degradation at scale</p>
  <div class="slide-meta">
    <span class="slide-author">Engineering Team</span>
    <span class="slide-date">May 2026</span>
  </div>
</div>
```

```css
.slide-title {
  text-align: center;
  justify-content: center;
  gap: var(--sp-4);
}

.slide-hero {
  font-size: clamp(28px, 5vw, 48px);
  font-weight: 700;
  line-height: 1.15;
  letter-spacing: -0.02em;
  color: var(--color-text, var(--text-primary));
}

.slide-subtitle {
  font-size: clamp(16px, 2.5vw, 22px);
  color: var(--color-text-secondary, var(--text-muted));
  font-weight: 400;
}

.slide-meta {
  display: flex;
  justify-content: center;
  gap: var(--sp-4);
  margin-top: var(--sp-4);
  font: var(--type-small);
  color: var(--color-text-secondary, var(--text-muted));
}

.slide-author {
  font-weight: 500;
}

.slide-date {
  opacity: 0.7;
}
```

### Content Slide (Heading + Bullets)

Standard slide with a heading and bullet points.

```html
<div class="slide slide-content" role="group" aria-roledescription="slide"
     aria-label="Slide 2 of 8: Key Principles"
     data-notes="Emphasize that these are ordered by priority.">
  <h2 class="slide-heading">Key Principles</h2>
  <ul class="slide-bullets">
    <li>Fail fast, recover faster</li>
    <li>Degrade gracefully under load</li>
    <li>Circuit breakers on all external calls</li>
    <li>Retry with exponential backoff</li>
  </ul>
</div>
```

```css
.slide-content {
  gap: var(--sp-6);
}

.slide-heading {
  font-size: clamp(22px, 4vw, 36px);
  font-weight: 600;
  color: var(--color-text, var(--text-primary));
  line-height: 1.2;
}

.slide-bullets {
  list-style: none;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.slide-bullets li {
  font-size: clamp(16px, 2.5vw, 20px);
  line-height: 1.5;
  color: var(--color-text-secondary, var(--text-secondary));
  padding-left: var(--sp-6);
  position: relative;
}

.slide-bullets li::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0.6em;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-primary);
  opacity: 0.7;
}
```

### Code Slide

Slide with syntax-highlighted code block and an optional title.

```html
<div class="slide slide-code" role="group" aria-roledescription="slide"
     aria-label="Slide 4 of 8: Circuit Breaker Implementation"
     data-notes="Walk through the state machine: closed, open, half-open.">
  <h2 class="slide-heading">Circuit Breaker</h2>
  <pre class="slide-code-block"><code><span class="kw">class</span> <span class="fn">CircuitBreaker</span> {
  <span class="kw">constructor</span>(threshold = <span class="nr">5</span>, resetMs = <span class="nr">30000</span>) {
    <span class="kw">this</span>.failures = <span class="nr">0</span>;
    <span class="kw">this</span>.threshold = threshold;
    <span class="kw">this</span>.state = <span class="st">'closed'</span>;
  }

  <span class="kw">async</span> <span class="fn">call</span>(fn) {
    <span class="kw">if</span> (<span class="kw">this</span>.state === <span class="st">'open'</span>)
      <span class="kw">throw new</span> Error(<span class="st">'Circuit open'</span>);
    <span class="kw">try</span> {
      <span class="kw">const</span> result = <span class="kw">await</span> fn();
      <span class="kw">this</span>.onSuccess();
      <span class="kw">return</span> result;
    } <span class="kw">catch</span> (err) {
      <span class="kw">this</span>.onFailure();
      <span class="kw">throw</span> err;
    }
  }
}</code></pre>
</div>
```

```css
.slide-code {
  gap: var(--sp-4);
}

.slide-code-block {
  background: color-mix(in srgb, var(--color-bg, #1a1a19) 80%, black);
  border: 1px solid var(--color-border, var(--border-subtle));
  border-radius: var(--radius-sm);
  padding: var(--sp-5);
  font-family: var(--font-mono);
  font-size: clamp(12px, 1.8vw, 15px);
  line-height: 1.6;
  overflow-x: auto;
  color: var(--color-text, var(--text-primary));
}

/* Syntax highlight tokens */
.slide-code-block .kw { color: #C792EA; }
.slide-code-block .fn { color: #82AAFF; }
.slide-code-block .st { color: #C3E88D; }
.slide-code-block .cm { color: #6A737D; }
.slide-code-block .nr { color: #F78C6C; }
```

### Image/SVG Slide

Full-bleed SVG illustration or diagram as the slide content.

```html
<div class="slide slide-visual" role="group" aria-roledescription="slide"
     aria-label="Slide 5 of 8: Architecture Overview">
  <h2 class="slide-heading">Architecture</h2>
  <div class="slide-svg-container">
    <svg viewBox="0 0 640 280" xmlns="http://www.w3.org/2000/svg" role="img"
         aria-label="Three-tier architecture diagram">
      <!-- Inline SVG diagram -->
    </svg>
  </div>
</div>
```

```css
.slide-visual {
  gap: var(--sp-4);
}

.slide-svg-container {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 0;
}

.slide-svg-container svg {
  width: 100%;
  max-height: 100%;
  object-fit: contain;
}
```

### Split Slide (Text Left, Visual Right)

Two-column layout for combining text with a diagram or image.

```html
<div class="slide slide-split" role="group" aria-roledescription="slide"
     aria-label="Slide 6 of 8: Before and After">
  <div class="split-text">
    <h2 class="slide-heading">Before &amp; After</h2>
    <ul class="slide-bullets">
      <li>p99 latency: 2.4s &#8594; 180ms</li>
      <li>Error rate: 4.2% &#8594; 0.1%</li>
      <li>Uptime: 99.2% &#8594; 99.97%</li>
    </ul>
  </div>
  <div class="split-visual">
    <svg viewBox="0 0 280 200" xmlns="http://www.w3.org/2000/svg" role="img"
         aria-label="Latency improvement chart">
      <!-- Inline SVG chart -->
    </svg>
  </div>
</div>
```

```css
.slide-split {
  flex-direction: row;
  gap: var(--sp-7);
  align-items: center;
}

.split-text {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}

.split-visual {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.split-visual svg {
  width: 100%;
  height: auto;
}

@media (max-width: 640px) {
  .slide-split {
    flex-direction: column;
  }
}
```

### Quote Slide

Large centered quotation with attribution.

```html
<div class="slide slide-quote" role="group" aria-roledescription="slide"
     aria-label="Slide 7 of 8: Quote">
  <blockquote class="slide-blockquote">
    <p>"Everything fails all the time."</p>
    <cite>Werner Vogels, CTO Amazon</cite>
  </blockquote>
</div>
```

```css
.slide-quote {
  justify-content: center;
  align-items: center;
  text-align: center;
}

.slide-blockquote {
  max-width: 680px;
}

.slide-blockquote p {
  font-size: clamp(22px, 4vw, 36px);
  font-weight: 500;
  font-style: italic;
  line-height: 1.4;
  color: var(--color-text, var(--text-primary));
  margin-bottom: var(--sp-5);
}

.slide-blockquote cite {
  font-style: normal;
  font-size: var(--type-small);
  color: var(--color-text-secondary, var(--text-muted));
  display: block;
}

.slide-blockquote cite::before {
  content: '— ';
}
```

---

## Navigation JavaScript

### Arrow Key + Touch Navigation

```js
(function() {
  var slides = document.querySelectorAll('.slide');
  var counter = document.getElementById('slide-counter');
  var progress = document.getElementById('progress-fill');
  var btnPrev = document.getElementById('btn-prev');
  var btnNext = document.getElementById('btn-next');
  var notesPanel = document.getElementById('notes-panel');
  var notesContent = document.getElementById('notes-content');
  var current = 0;
  var total = slides.length;

  function showSlide(index) {
    if (index < 0 || index >= total) return;
    slides[current].classList.remove('active');
    current = index;
    slides[current].classList.add('active');

    // Update counter
    counter.textContent = (current + 1) + ' / ' + total;

    // Update progress bar
    var pct = ((current + 1) / total) * 100;
    progress.style.width = pct + '%';
    progress.parentElement.setAttribute('aria-valuenow', current + 1);

    // Update button states
    btnPrev.disabled = current === 0;
    btnNext.disabled = current === total - 1;

    // Update notes if panel is visible
    if (!notesPanel.hidden) {
      var noteText = slides[current].getAttribute('data-notes') || 'No notes for this slide.';
      notesContent.textContent = noteText;
    }

    // Update aria-label for current slide
    slides[current].setAttribute('aria-label',
      'Slide ' + (current + 1) + ' of ' + total + ': ' +
      (slides[current].querySelector('.slide-heading, .slide-hero, h2, h1') || {}).textContent || '');
  }

  // Expose navigation functions globally
  window.nextSlide = function() { showSlide(current + 1); };
  window.prevSlide = function() { showSlide(current - 1); };

  // Keyboard navigation
  document.addEventListener('keydown', function(e) {
    // Ignore if focus is in an input/textarea
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

    switch (e.key) {
      case 'ArrowRight':
      case 'ArrowDown':
        e.preventDefault();
        showSlide(current + 1);
        break;
      case 'ArrowLeft':
      case 'ArrowUp':
        e.preventDefault();
        showSlide(current - 1);
        break;
      case 'Home':
        e.preventDefault();
        showSlide(0);
        break;
      case 'End':
        e.preventDefault();
        showSlide(total - 1);
        break;
      case 'f':
      case 'F':
        toggleFullscreen();
        break;
      case 'n':
      case 'N':
        toggleNotes();
        break;
      case 'Escape':
        if (document.fullscreenElement) {
          document.exitFullscreen();
        }
        break;
    }
  });

  // Touch / swipe support
  var touchStartX = 0;
  var touchStartY = 0;
  var deck = document.getElementById('slide-deck');

  deck.addEventListener('touchstart', function(e) {
    touchStartX = e.changedTouches[0].screenX;
    touchStartY = e.changedTouches[0].screenY;
  }, { passive: true });

  deck.addEventListener('touchend', function(e) {
    var dx = e.changedTouches[0].screenX - touchStartX;
    var dy = e.changedTouches[0].screenY - touchStartY;

    // Only trigger on horizontal swipes (|dx| > |dy| and |dx| > threshold)
    if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 50) {
      if (dx < 0) {
        showSlide(current + 1); // Swipe left = next
      } else {
        showSlide(current - 1); // Swipe right = previous
      }
    }
  }, { passive: true });

  // Fullscreen toggle
  function toggleFullscreen() {
    if (!document.fullscreenElement) {
      deck.requestFullscreen().catch(function() {
        /* Fullscreen not supported or denied */
      });
    } else {
      document.exitFullscreen();
    }
  }
  window.toggleFullscreen = toggleFullscreen;

  // Notes toggle
  function toggleNotes() {
    if (notesPanel.hidden) {
      notesPanel.removeAttribute('hidden');
      var noteText = slides[current].getAttribute('data-notes') || 'No notes for this slide.';
      notesContent.textContent = noteText;
    } else {
      notesPanel.setAttribute('hidden', '');
    }
  }
  window.toggleNotes = toggleNotes;

  // Initialize
  showSlide(0);
})();
```

---

## Presenter Notes Panel

Hidden by default. Toggle with 'N' key.

```css
.notes-panel {
  margin-top: var(--sp-4);
  padding: var(--sp-4) var(--sp-5);
  background: var(--color-surface, var(--bg-muted));
  border: 1px solid var(--color-border, var(--border-subtle));
  border-radius: var(--radius-sm);
}

.notes-panel[hidden] {
  display: none;
}

.notes-panel h3 {
  font: var(--type-caption);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-text-secondary, var(--text-muted));
  margin-bottom: var(--sp-3);
}

#notes-content {
  font: var(--type-small);
  color: var(--color-text-secondary, var(--text-secondary));
  line-height: 1.6;
}
```

---

## Keyboard Shortcuts Reference

Include as a small help overlay or in the footer.

```html
<footer class="deck-footer">
  <div class="keyboard-help">
    <span class="kbd-hint"><kbd>&#8592;</kbd><kbd>&#8594;</kbd> Navigate</span>
    <span class="kbd-hint"><kbd>F</kbd> Fullscreen</span>
    <span class="kbd-hint"><kbd>N</kbd> Notes</span>
    <span class="kbd-hint"><kbd>Esc</kbd> Exit fullscreen</span>
  </div>
</footer>
```

```css
.deck-footer {
  margin-top: var(--sp-5);
  padding-top: var(--sp-3);
  border-top: 1px solid var(--color-border, var(--border-subtle));
}

.keyboard-help {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-4);
  justify-content: center;
}

.kbd-hint {
  font: var(--type-caption);
  color: var(--color-text-secondary, var(--text-muted));
  display: flex;
  align-items: center;
  gap: var(--sp-1);
}

kbd {
  display: inline-block;
  padding: 2px 6px;
  font-family: var(--font-mono);
  font-size: 11px;
  background: var(--color-surface, var(--bg-muted));
  border: 1px solid var(--color-border, var(--border-subtle));
  border-radius: var(--radius-xs);
  line-height: 1.4;
}
```

---

## Print Styles

Print view renders all slides vertically for PDF export. Each slide gets a page break.

```css
@media print {
  body {
    background: white;
    color: black;
  }

  .deck-wrapper {
    max-width: none;
  }

  .slide-deck {
    aspect-ratio: auto;
    height: auto;
    border: none;
    box-shadow: none;
    background: white;
    overflow: visible;
  }

  .slide {
    position: static;
    opacity: 1;
    pointer-events: auto;
    border: 1px solid #ccc;
    border-radius: 8px;
    margin-bottom: 24px;
    page-break-inside: avoid;
    break-inside: avoid;
    aspect-ratio: 16 / 9;
    min-height: 400px;
  }

  .slide.active {
    /* No special styling -- all slides are visible in print */
  }

  .deck-controls,
  .progress-bar,
  .notes-panel,
  .deck-footer {
    display: none;
  }

  .slide-hero,
  .slide-heading {
    color: black;
  }

  .slide-subtitle,
  .slide-bullets li,
  .slide-blockquote p {
    color: #333;
  }

  .slide-code-block {
    background: #f5f5f5;
    color: #333;
    border: 1px solid #ccc;
  }
}
```

---

## Fullscreen Styles

When the deck enters fullscreen, the slide fills the viewport.

```css
.slide-deck:fullscreen {
  border-radius: 0;
  border: none;
  box-shadow: none;
}

.slide-deck:fullscreen .slide {
  padding: var(--sp-10) calc(var(--sp-10) * 2);
}

/* Webkit prefix for Safari */
.slide-deck:-webkit-full-screen {
  border-radius: 0;
  border: none;
  box-shadow: none;
}
```

---

## Transition Variants

Default is fade. Alternative: slide transition (horizontal movement).

### Slide Transition (Alternative)

Replace the fade transition CSS if the user requests slide-style movement.

```css
/* Slide transition variant -- replace fade transition above */
.slide {
  transform: translateX(100%);
  opacity: 1;
  transition: transform 0.4s ease;
}

.slide.active {
  transform: translateX(0);
}

.slide.prev {
  transform: translateX(-100%);
}

@media (prefers-reduced-motion: reduce) {
  .slide {
    transform: none;
    transition: none;
  }
  .slide:not(.active) {
    display: none;
  }
}
```

When using slide transitions, add `.prev` class management to the navigation JS:

```js
// Inside showSlide function, before setting new active:
slides[current].classList.add('prev');
slides[current].classList.remove('active');
// Then set new slide:
slides[index].classList.remove('prev');
slides[index].classList.add('active');
```

---

## Composition Guide

Assemble slide decks by selecting slide types:

| Deck Type | Recommended Slide Sequence |
|---|---|
| Technical talk | Title, Content (overview), Code (2-3), Split (demo/results), Content (takeaways), Quote or Title (closing) |
| Pitch deck | Title, Content (problem), Split (solution), Content (metrics), Visual (architecture), Content (next steps) |
| Lightning talk (5 min) | Title, Content (one idea), Code or Visual (proof), Content (takeaway) |
| Training deck | Title, Content (goals), Code + Content (alternating), Content (exercises), Title (Q&A) |

### Slide Count Guidance

| Duration | Slide Count | Pace |
|---|---|---|
| 5 min (lightning) | 4-6 slides | ~1 min per slide |
| 15 min | 8-12 slides | ~90s per slide |
| 30 min | 15-20 slides | ~90s per slide |
| 45 min | 20-30 slides | ~90s per slide |

---

## Accessibility Requirements

| Requirement | Implementation |
|---|---|
| Slide carousel | `role="region"`, `aria-roledescription="carousel"` on deck container |
| Individual slides | `role="group"`, `aria-roledescription="slide"`, `aria-label="Slide N of M: Title"` |
| Slide counter | `aria-live="polite"` announces current position on navigation |
| Progress bar | `role="progressbar"` with `aria-valuenow`, `aria-valuemin`, `aria-valuemax` |
| Keyboard nav | Arrow keys, Home/End, F for fullscreen, N for notes, Escape to exit |
| Button labels | Previous/Next buttons have descriptive `aria-label` |
| Disabled state | Prev button disabled on first slide, Next on last |
| Focus visible | `:focus-visible` outlines on all buttons and interactive elements |
| Reduced motion | `prefers-reduced-motion` disables slide transitions |
| Code readability | Code slides use monospace font, sufficient contrast, scrollable overflow |
| Print | All slides rendered vertically with page breaks for PDF accessibility |

---

## Shape Selection Guidance

Use **deck** shape when the user's request matches any of:

| Signal | Example Request |
|---|---|
| Slides | "Create slides for my talk" |
| Presentation | "Make a presentation about our API" |
| Slide deck | "Build a slide deck for the team meeting" |
| Talk | "Prepare talk slides on circuit breakers" |
| Pitch | "Create a pitch deck for the product" |
| Keynote | "Keynote-style slides for the conference" |
| Slideshow | "Make a slideshow of the project highlights" |

Do NOT use deck when:
- The user wants a written document (use **report**)
- The user wants to compare options side by side (use **spec**)
- The user wants interactive parameter tuning (use **prototype**)
- The user wants diagrams without a presentation wrapper (use **diagram**)
- The user wants a dashboard with charts (use **data-viz**)
