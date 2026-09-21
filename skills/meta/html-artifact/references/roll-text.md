# Roll Text — per-character slot transition

Animates a text element from string A to string B. Each character sits in a clipped cell; the old glyph slides out while the new glyph slides in, staggered left to right. Vanilla JS + CSS transitions. No build step, no npm, no canvas, no animation loop.

Clean-room implementation written from a behavior spec; no external code or license applies.

## Behavior

- `rollTo(el, next, opts)` retargets `el` to display `next`.
- Unchanged characters stay static; changed characters roll.
- Strings of different lengths work: missing positions roll to/from an empty cell, and each cell animates its width from old-glyph width to new-glyph width, so the line reflows smoothly.
- Interruptible: a new call mid-animation rebuilds from the last requested target and rolls to the new one.
- `prefers-reduced-motion: reduce` collapses duration and stagger to 0 (instant swap).
- Screen readers get the plain string via `aria-label`; the per-character cells are `aria-hidden`.

## Standalone demo (copy-paste runnable)

Save as `roll-text-demo.html` and open in any browser. Works offline.

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Roll text demo</title>
<style>
  body { font-family: system-ui, sans-serif; background: #14141c; color: #f2f0ea;
         display: grid; place-items: center; min-height: 100vh; margin: 0; }
  main { text-align: center; }
  h1 { font-size: 3rem; margin: 0 0 1.5rem; }
  button { font: inherit; padding: 0.4rem 1rem; margin: 0 0.25rem;
           background: #2c2c3a; color: inherit; border: 1px solid #4a4a5e;
           border-radius: 6px; cursor: pointer; }

  /* Roll-text core */
  .rolltext { display: inline-flex; --cell-h: 1.2em; line-height: var(--cell-h); }
  .rolltext .rt-cell { display: inline-block; overflow: hidden;
                       height: var(--cell-h); white-space: pre; }
  .rolltext .rt-col { display: flex; flex-direction: column; will-change: transform; }
  .rolltext .rt-glyph { display: block; height: var(--cell-h);
                        line-height: var(--cell-h); white-space: pre; }
</style>
</head>
<body>
<main>
  <h1 id="headline"></h1>
  <button id="next">Next phrase</button>
  <button id="spam">Interrupt test</button>
</main>
<script>
/* Roll-text core ----------------------------------------------------- */
function rollTo(el, next, opts) {
  var cfg = Object.assign({
    duration: 450,                       /* ms per character roll */
    stagger: 45,                         /* ms delay added per character */
    easing: 'cubic-bezier(0.33, 0, 0.2, 1)',
    direction: 'up'                      /* 'up' or 'down' */
  }, opts || {});
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    cfg.duration = 0;
    cfg.stagger = 0;
  }

  /* Retarget cleanly: start from the last requested string. */
  var prev = el.dataset.rtTarget != null ? el.dataset.rtTarget : el.textContent;
  el.dataset.rtTarget = next;
  el.classList.add('rolltext');
  el.setAttribute('aria-label', next);
  el.replaceChildren();

  var count = Math.max(prev.length, next.length);
  var movers = [];
  for (var i = 0; i < count; i++) {
    var from = prev[i] || '';
    var to = next[i] || '';
    var cell = document.createElement('span');
    cell.className = 'rt-cell';
    cell.setAttribute('aria-hidden', 'true');
    if (from === to) {
      cell.textContent = from;           /* unchanged: static cell */
      el.appendChild(cell);
      continue;
    }
    var col = document.createElement('span');
    col.className = 'rt-col';
    /* Stack order decides roll direction. */
    col.appendChild(makeGlyph(cfg.direction === 'up' ? from : to));
    col.appendChild(makeGlyph(cfg.direction === 'up' ? to : from));
    if (cfg.direction === 'down') col.style.transform = 'translateY(-50%)';
    cell.appendChild(col);
    el.appendChild(cell);
    movers.push({ cell: cell, col: col, from: from, to: to, delay: i * cfg.stagger });
  }

  /* Measure glyph widths in the element's own font. */
  var probe = document.createElement('span');
  probe.style.cssText = 'position:absolute;visibility:hidden;white-space:pre;';
  el.appendChild(probe);
  movers.forEach(function (m) {
    probe.textContent = m.from;
    m.w0 = probe.getBoundingClientRect().width;
    probe.textContent = m.to;
    m.w1 = probe.getBoundingClientRect().width;
  });
  probe.remove();

  /* Commit start state, force one reflow, then set end state.
     The reflow makes the browser register the start values so the
     transition actually runs. No rAF loop needed. */
  movers.forEach(function (m) { m.cell.style.width = m.w0 + 'px'; });
  void el.offsetHeight;
  movers.forEach(function (m) {
    var t = cfg.duration + 'ms ' + cfg.easing + ' ' + m.delay + 'ms';
    m.col.style.transition = 'transform ' + t;
    m.cell.style.transition = 'width ' + t;
    m.col.style.transform = cfg.direction === 'up' ? 'translateY(-50%)' : 'translateY(0)';
    m.cell.style.width = m.w1 + 'px';
  });
}

function makeGlyph(ch) {
  var s = document.createElement('span');
  s.className = 'rt-glyph';
  s.textContent = ch;
  return s;
}

/* Demo wiring --------------------------------------------------------- */
var phrases = ['Hello, world', 'Different length here', 'Hi', 'Roll the text'];
var idx = 0;
var headline = document.getElementById('headline');
rollTo(headline, phrases[0]);

document.getElementById('next').addEventListener('click', function () {
  idx = (idx + 1) % phrases.length;
  rollTo(headline, phrases[idx]);
});

/* Two rapid calls: the second retargets mid-animation. */
document.getElementById('spam').addEventListener('click', function () {
  rollTo(headline, 'Interrupted...');
  setTimeout(function () { rollTo(headline, 'Retargeted cleanly'); }, 200);
});
</script>
</body>
</html>
```

## Extraction guide (for embedding in an artifact)

1. Copy the three CSS rules under "Roll-text core" into the artifact's `<style>`. Rename the `rolltext`/`rt-*` classes if they collide.
2. Copy `rollTo` and `makeGlyph` into the artifact's `<script>`. No other code is required.
3. Call `rollTo(element, 'new string')` whenever the text should change. The first call may target an empty element; pass the initial string.
4. Keep the `data-rt-target` attribute untouched — it stores the last target so interruption retargets from a known string instead of half-rolled glyphs.
5. Verify standalone: open the file from disk; text rolls with no console errors and no network requests.

## Knobs

| Knob | Default | Effect |
|---|---|---|
| `duration` | `450` ms | Length of each character's roll and width change |
| `stagger` | `45` ms | Extra delay per character index; 0 = all roll together |
| `easing` | `cubic-bezier(0.33, 0, 0.2, 1)` | Any CSS easing; an overshoot curve (y > 1) gives a springy land |
| `direction` | `'up'` | `'up'` rolls old glyph out the top; `'down'` out the bottom |
| `--cell-h` (CSS) | `1.2em` | Cell height; raise it if descenders clip in the chosen font |

## Notes

- Monospace fonts make the width transition invisible (all glyphs equal width) — that is fine, not a bug.
- For a rolling counter, call `rollTo` with the formatted number string; unchanged digits stay still, changed digits roll.
- Cells use `white-space: pre` so space characters keep their width.
