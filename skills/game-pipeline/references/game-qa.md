# Game QA Reference

Playwright-based testing patterns for browser canvas games. Covers visual regression, canvas test seams, deterministic mode, and clock control.

---

## Test Seam: window.__TEST__ Global

Inject a global in the game bootstrap that switches the game to deterministic test mode. Playwright reads this to verify game state without pixel inspection.

```javascript
// src/main.js — at the very top, before any game init
const params = new URLSearchParams(location.search);
const TEST_MODE = params.get('test') === '1';
const SEED      = parseInt(params.get('seed') || '0');

if (TEST_MODE) {
  window.__TEST__ = {
    seed:  SEED,
    state: null,   // game writes current state here each frame
    frame: 0,
  };
}
```

Game code checks `window.__TEST__` before using `Math.random()`:

```javascript
// src/utils/random.js
export function rand() {
  if (window.__TEST__) return seededRandom(window.__TEST__.seed);
  return Math.random();
}
```

---

## render_game_to_text()

Expose game state as human-readable text for AI-readable verification. Playwright reads `window.__TEST__.state` after calling this.

```javascript
// src/main.js — call every frame when TEST_MODE is active
function render_game_to_text() {
  return [
    `frame:    ${game.frame}`,
    `score:    ${game.score}`,
    `lives:    ${game.lives}`,
    `entities: ${game.entities.length}`,
    `phase:    ${game.phase}`,
  ].join('\n');
}

// In game loop:
if (window.__TEST__) {
  window.__TEST__.state = render_game_to_text();
  window.__TEST__.frame++;
}
```

Playwright assertion:
```javascript
const state = await page.evaluate(() => window.__TEST__.state);
expect(state).toContain('lives:    3');
```

---

## Readiness Signal

Never assert before the game is ready. Emit a ready event and wait for it in Playwright.

**Game side** (Phaser example):
```javascript
this.events.once('create', () => {
  window.dispatchEvent(new Event('game-ready'));
});
```

**Game side** (vanilla):
```javascript
// After all assets loaded and game loop started:
window.dispatchEvent(new Event('game-ready'));
```

**Playwright side**:
```javascript
await page.waitForFunction(() =>
  window.__GAME_READY__ === true || document.querySelector('canvas') !== null
);
// Or explicit event:
await page.evaluate(() =>
  new Promise(resolve => window.addEventListener('game-ready', resolve, { once: true }))
);
```

---

## Clock Control: Mock requestAnimationFrame

For frame-perfect deterministic tests, replace `requestAnimationFrame` with a manual stepper:

```javascript
// In test seam setup:
if (window.__TEST__) {
  let rafCallbacks = [];
  window.requestAnimationFrame = (cb) => { rafCallbacks.push(cb); return rafCallbacks.length; };
  window.__TEST__.step = (n = 1) => {
    for (let i = 0; i < n; i++) {
      const cbs = rafCallbacks.splice(0);
      cbs.forEach(cb => cb(performance.now()));
    }
  };
}
```

Playwright usage:
```javascript
// Advance exactly 60 frames
await page.evaluate(() => window.__TEST__.step(60));
const state = await page.evaluate(() => window.__TEST__.state);
expect(state).toContain('frame:    60');
```

---

## Visual Regression Workflow

Captures screenshots and compares pixel-level RMS difference.

**Step 1: Capture baseline**

```javascript
// tests/baseline.spec.js
import { test } from '@playwright/test';

test('capture baseline', async ({ page }) => {
  await page.goto('http://localhost:3000?test=1&seed=42');
  await page.waitForFunction(() => typeof window.__TEST__ !== 'undefined');
  await page.evaluate(() => window.__TEST__.step(30));  // advance 30 frames
  await page.screenshot({ path: 'tests/baseline.png', fullPage: false });
});
```

**Step 2: Run imgdiff after changes**

```bash
python3 skills/game-pipeline/scripts/imgdiff.py \
  tests/baseline.png tests/current.png --tolerance 5.0
```

Exit code 0 = PASS, 1 = FAIL. A diff image is written to `tests/diff.png` on failure.

**Step 3: Integrate into Playwright test**

```javascript
// tests/visual.spec.js
import { test, expect } from '@playwright/test';
import { execSync } from 'child_process';

test('visual regression', async ({ page }) => {
  await page.goto('http://localhost:3000?test=1&seed=42');
  await page.evaluate(() => window.__TEST__.step(30));
  await page.screenshot({ path: 'tests/current.png' });

  const result = execSync(
    'python3 skills/game-pipeline/scripts/imgdiff.py tests/baseline.png tests/current.png',
    { encoding: 'utf8' }
  );
  expect(result).toContain('PASS');
});
```

---

## Playwright Config for Games

```javascript
// playwright.config.js
import { defineConfig } from '@playwright/test';

export default defineConfig({
  use: {
    viewport:     { width: 800, height: 600 },
    baseURL:      'http://localhost:3000',
    launchOptions: { args: ['--disable-web-security'] }, // canvas cross-origin
  },
  webServer: {
    command: 'npm run dev',
    url:     'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
  },
});
```

---

## with_server.py Usage

When you can't rely on Playwright's `webServer` config (e.g., agent-driven tests), use the wrapper script:

```bash
# Start server, run tests, stop server regardless of outcome
python3 skills/game-pipeline/scripts/with_server.py \
  --port 3000 \
  --dir dist/ \
  "npx playwright test tests/visual.spec.js"
```

Exit code mirrors the test command exit code.

---

## Deterministic Mode URL Parameters

| Param | Value | Effect |
|---|---|---|
| `test` | `1` | Enables `window.__TEST__` global and deterministic mode |
| `seed` | integer | Fixed random seed for reproducible runs |
| `speed` | float | Game speed multiplier (default 1.0, use 0.0 to pause) |

Usage: `http://localhost:3000?test=1&seed=42&speed=0.5`

---

## Error Handling

### Error: page.evaluate() Returns undefined for window.__TEST__
**Cause**: Test seam code not executed (asset load race) or wrong URL parameters
**Fix**: Check URL has `?test=1`. Add `await page.waitForFunction(() => typeof window.__TEST__ !== 'undefined')` before any evaluation.

### Error: Screenshots Differ on CI But Pass Locally
**Cause**: Font rendering and OS-level anti-aliasing differ between environments
**Fix**: Increase tolerance: `--tolerance 10.0`. Or run baseline capture on the same CI image and commit that as the baseline.

### Error: requestAnimationFrame Mock Breaks Audio
**Cause**: AudioContext timing is separate from rAF; game code might use rAF for audio scheduling
**Fix**: Use `AudioContext.suspend()` / `resume()` for test mode. Do not mock `AudioContext.currentTime`.

### Error: Canvas Content Is Blank in Screenshot
**Cause**: WebGL context lost or canvas not yet rendered when screenshot is taken
**Fix**: Use `page.evaluate(() => window.__TEST__.step(1))` to force at least one render before screenshotting. Wait for `game-ready` event first.
