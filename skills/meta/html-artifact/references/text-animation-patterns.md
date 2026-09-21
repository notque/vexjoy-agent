# Text Animation Patterns — companions to roll-text

Three small dependency-free patterns. Each is self-contained: copy the CSS into `<style>`, the JS into `<script>`, call the function. All respect `prefers-reduced-motion` and keep the readable string in `aria-label` when they split text into spans.

## 1. Split-letter reveal

Entrance animation: each letter fades and rises in with a stagger. Use for headlines on first paint or when a section scrolls into view.

```html
<style>
  .reveal-glyph { display: inline-block; white-space: pre;
                  opacity: 0; transform: translateY(0.5em); }
  .reveal-glyph.is-in { opacity: 1; transform: none;
                        transition: opacity 350ms ease-out, transform 350ms ease-out; }
  @media (prefers-reduced-motion: reduce) {
    .reveal-glyph { opacity: 1; transform: none; }
  }
</style>
<script>
function revealText(el, stagger) {
  stagger = stagger == null ? 35 : stagger;
  var text = el.textContent;
  el.setAttribute('aria-label', text);
  el.replaceChildren();
  text.split('').forEach(function (ch, i) {
    var s = document.createElement('span');
    s.className = 'reveal-glyph';
    s.setAttribute('aria-hidden', 'true');
    s.textContent = ch;
    el.appendChild(s);
    void s.offsetHeight;                      /* register start state */
    s.style.transitionDelay = (i * stagger) + 'ms';
    s.classList.add('is-in');
  });
}
</script>
```

Usage: `revealText(document.querySelector('h1'))`. For scroll-triggered reveals, call it from an `IntersectionObserver` callback (see html-artifact `scrollytelling-patterns.md`).

## 2. Typewriter

Characters appear one at a time with a blinking caret. Use for terminal-style output or narrative emphasis. Returns a cancel function so a new run can interrupt the old.

```html
<style>
  .tw-caret::after { content: ''; display: inline-block; width: 0.08em;
                     height: 1em; background: currentColor; vertical-align: -0.1em;
                     animation: tw-blink 1s steps(1) infinite; }
  @keyframes tw-blink { 50% { opacity: 0; } }
</style>
<script>
function typeText(el, text, speed) {
  speed = speed == null ? 40 : speed;          /* ms per character */
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) speed = 0;
  el.setAttribute('aria-label', text);
  el.textContent = '';
  el.classList.add('tw-caret');
  var i = 0;
  var timer = setInterval(function () {
    el.textContent = text.slice(0, ++i);
    if (i >= text.length) {
      clearInterval(timer);
      el.classList.remove('tw-caret');
    }
  }, speed);
  return function cancel() { clearInterval(timer); el.classList.remove('tw-caret'); };
}
</script>
```

Usage: `var stop = typeText(el, 'Booting...'); /* later */ stop();`. With `speed = 0` the interval still fires immediately, so reduced-motion users get near-instant text.

## 3. Crossfade swap

Old text fades out, new text fades in with a slight vertical drift. Use when whole phrases change (status lines, tab labels) and per-character motion would be noise.

```html
<style>
  .xfade { display: inline-block;
           transition: opacity 200ms ease, transform 200ms ease; }
  .xfade.is-out { opacity: 0; transform: translateY(-0.3em); }
  @media (prefers-reduced-motion: reduce) { .xfade { transition: none; } }
</style>
<script>
function swapText(el, next) {
  el.classList.add('xfade', 'is-out');
  function commit() {
    el.removeEventListener('transitionend', commit);
    el.textContent = next;
    el.classList.remove('is-out');           /* fades back in */
  }
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    el.textContent = next;
    el.classList.remove('is-out');
    return;
  }
  el.addEventListener('transitionend', commit);
}
</script>
```

Usage: `swapText(statusEl, 'Saved')`. Interruption-safe enough for status lines: a second call before `transitionend` re-adds `is-out` and the newest `next` wins because each call registers a fresh listener — if calls can arrive faster than 200ms, debounce them.

## Choosing a pattern

| Intent | Pattern |
|---|---|
| String-to-string transition, counters, labels | roll-text (see `roll-text.md`) |
| First-paint or on-scroll headline entrance | Split-letter reveal |
| Terminal output, narrative pacing | Typewriter |
| Phrase swaps where motion should stay quiet | Crossfade swap |
