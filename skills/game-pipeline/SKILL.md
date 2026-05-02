---
name: game-pipeline
description: "Game lifecycle orchestrator: scaffold, assets, audio, QA, deploy."
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
  - Grep
  - Edit
  - Task
routing:
  triggers:
    - make game
    - game pipeline
    - game audio
    - add audio game
    - game testing
    - game qa
    - playtest
    - deploy game
    - ship game
    - promo video
    - record gameplay
    - game polish
    - add juice
    - screen shake
    - capacitor ios
  pairs_with:
    - threejs-builder
    - phaser-gamedev
    - game-asset-generator
  complexity: Complex
  category: game-development
---

# Game Pipeline Skill

Orchestrates full game lifecycle: SCAFFOLD -> ASSETS -> DESIGN -> AUDIO -> QA -> DEPLOY. Each phase can be entered independently. The orchestrator delegates each phase to the appropriate engine skill or domain reference -- it never writes game code directly.

**Scope**: Browser-based games (Three.js, Phaser, vanilla canvas), cross-engine concerns (audio, QA, promo, deploy), iOS via Capacitor. Not for Unity/Godot/native engines, non-game web apps, or server-side logic.

---

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| `references/game-audio.md` | `game-audio.md` | AUDIO |
| `references/game-qa.md` | `game-qa.md` | QA |
| `references/game-designer.md` | `game-designer.md` | DESIGN |
| `references/promo-video.md` | `promo-video.md` | DEPLOY |
| `references/deploy.md` | `deploy.md` | DEPLOY |
| `references/capacitor-ios.md` | `capacitor-ios.md` | DEPLOY |

## Instructions

### Entry Point Detection

| User request | Entry phase |
|---|---|
| "make a game", "new game" | SCAFFOLD |
| "generate assets", "add sprites", "need art" | ASSETS |
| "add juice", "game feels flat", "particles", "screen shake" | DESIGN |
| "add audio", "background music", "sound effects" | AUDIO |
| "test my game", "visual regression", "game qa" | QA |
| "deploy", "ship", "publish", "github pages", "promo video", "ios" | DEPLOY |

If entry phase is not SCAFFOLD, skip to that phase. Phases are independently re-enterable.

---

### Phase 1: SCAFFOLD

**Goal**: Initialize project and delegate engine-specific setup.

**Step 1: Detect engine**

| Signal | Engine | Delegate to |
|---|---|---|
| `import * as THREE`, three.js in package.json | Three.js | `threejs-builder` |
| `new Phaser.Game()`, phaser in package.json | Phaser | `phaser-gamedev` |
| No engine signal | Ask user | -- |

**Step 2: Initialize project structure**

```
game/
├── index.html
├── src/
│   └── main.js
├── assets/
│   └── assets_index.json   # Required for Capacitor iOS
└── dist/
```

`assets_index.json`:
```json
{
  "version": "1.0",
  "assets": {
    "player": "assets/player.png",
    "bgm": "assets/music.ogg"
  }
}
```

**Step 3: Wire EventBus**

EventBus is the integration contract -- audio, effects, analytics attach without touching game logic:

```javascript
export const EventBus = new EventTarget();
export const emit = (name, detail = {}) =>
  EventBus.dispatchEvent(new CustomEvent(name, { detail }));
export const on = (name, fn) =>
  EventBus.addEventListener(name, (e) => fn(e.detail));
```

Pre-wire: `ENEMY_HIT`, `PLAYER_DEATH`, `LEVEL_UP`, `GAME_OVER`, `SCORE_CHANGE`, `SPECTACLE_*`

**Gate**: Engine chosen, structure created, EventBus wired.

---

### Phase 2: ASSETS

**Goal**: Source or generate assets and register in manifest.

**Step 1: Audit existing**: `ls assets/` and `cat assets/assets_index.json`

**Step 2: Delegate to game-asset-generator** with: asset list, art style, output format (PNG spritesheet for Phaser, GLB for Three.js), target path `assets/`.

**Step 3: Update `assets/assets_index.json`**. Use relative paths only (manifest read by both web game and Capacitor iOS).

**Gate**: All assets generated, manifest updated, assets load without errors.

---

### Phase 3: DESIGN

**Goal**: Add visual polish ("juice") wired to EventBus, not game logic.

**Load reference**: `references/game-designer.md`

| Effect | Trigger event | Impact |
|---|---|---|
| Screen shake | `ENEMY_HIT`, `EXPLOSION` | Impact weight |
| Hit freeze frame | `ENEMY_HIT` (big) | Dramatic pause |
| Particle burst | `ENEMY_HIT`, `GAME_OVER` | Visual feedback |
| Floating score text | `SCORE_CHANGE` | Progress reward |
| Combo text | `COMBO_REACHED` | Achievement surge |

**Opening moment rule**: First 3 seconds must hook the player -- immediate spectacle, never loading screen or empty scene.

**Gate**: At least 3 juice effects wired to EventBus. Opening moment compelling. No effects hardcoded into gameplay logic.

---

### Phase 4: AUDIO

**Goal**: Background music and SFX via Web Audio API.

**Load reference**: `references/game-audio.md`

**Key constraint**: Create `AudioContext` only on first user interaction -- browser autoplay policy silently blocks premature contexts.

```javascript
let ctx = null;
export function getCtx() {
  if (!ctx) ctx = new AudioContext();
  return ctx;
}
```

**AudioBridge -- wire to EventBus**:
```javascript
on('ENEMY_HIT', () => playSFX('hit'));
on('LEVEL_UP',  () => { stopBGM(); startBGM('level2'); });
on('GAME_OVER', () => playSFX('gameover'));
```

**Volume hierarchy**: master gain -> category gains (music, sfx, ambient) -> individual sources. Never set volume directly on sources.

**Gate**: AudioContext on user interaction only. BGM plays. At least 2 SFX wired. Volume controls work.

---

### Phase 5: QA

**Goal**: Automated testing via Playwright with visual regression and canvas test seams.

**Load reference**: `references/game-qa.md`

**Scripts**:
```bash
python3 skills/game-pipeline/scripts/imgdiff.py baseline.png current.png
python3 skills/game-pipeline/scripts/with_server.py "npx playwright test"
```

**Test seam**:
```javascript
const TEST_MODE = new URLSearchParams(location.search).get('test') === '1';
const SEED = parseInt(new URLSearchParams(location.search).get('seed') || '0');
if (TEST_MODE) window.__TEST__ = { seed: SEED, state: null };
```

**Visual regression**: Take baseline -> make change -> diff with imgdiff.py -> RMS > 5.0 means investigate.

**Gate**: At least 1 Playwright test passes. Visual baseline captured. Canvas test seam exists.

---

### Phase 6: DEPLOY

**Goal**: Ship to live URL.

**Load**: `references/deploy.md`. Add `references/capacitor-ios.md` if iOS. Add `references/promo-video.md` if recording gameplay.

**Pre-deploy checklist**:
```bash
npm run build
ls dist/
grep -r "localhost" dist/ && echo "FAIL: localhost refs" || echo "OK"
grep -r 'src="/' dist/ && echo "WARN: absolute paths" || echo "OK"
```

| Target | Command | Notes |
|---|---|---|
| GitHub Pages | `npx gh-pages -d dist` | Public repo or GitHub Pro |
| Vercel | `vercel --prod` | Best for preview URLs |
| Static host | Upload `dist/` | Works anywhere |
| iOS (Capacitor) | See `capacitor-ios.md` | Requires Xcode |

**Gate**: Build succeeds. Deploy URL live. Game loads. No console errors.

---

## Error Handling

### Error: AudioContext Blocked
**Cause**: Created outside user gesture handler
**Fix**: Use `getCtx()` lazy-init. First call must be inside click/keydown handler.

### Error: Playwright Can't Interact With Canvas
**Cause**: No test seams, non-deterministic state, or missing readiness signal
**Fix**: Add `window.__TEST__` with `?test=1&seed=42`. Wait for `game.events.once('ready')`. Use `render_game_to_text()` to expose state.

### Error: imgdiff.py Unexpected Diff
**Cause**: Font rendering or anti-aliasing differences between platforms
**Fix**: `python3 skills/game-pipeline/scripts/imgdiff.py a.png b.png --tolerance 10.0`. If still failing, retake baseline on same platform.

### Error: Capacitor iOS Build Fails
**Cause**: Absolute paths, missing `webDir`, or CocoaPods conflict
**Fix**: All paths relative. Check `capacitor.config.ts` has `webDir: 'dist'`. Capacitor 5+ uses SPM -- `npx cap sync`, not `pod install`. See `capacitor-ios.md`.

### Error: Assets Missing After Deploy
**Cause**: Absolute paths (`/assets/player.png` instead of `assets/player.png`)
**Fix**: `grep -r '"/assets/' dist/`. Use relative paths everywhere.

### Error: Promo Video Choppy
**Cause**: Screenshot rate too slow or FFmpeg framerate mismatch
**Fix**: Use CDP screencast. Set game speed to 0.5, encode with `-r 50`. See `promo-video.md`.

---

## References

| Reference | Phase | Content |
|---|---|---|
| `references/game-audio.md` | AUDIO | Web Audio API: AudioManager, BGM sequencer, SFX pool, AudioBridge, volume hierarchy |
| `references/game-qa.md` | QA | Playwright: visual regression, canvas seams, deterministic mode, imgdiff patterns |
| `references/game-designer.md` | DESIGN | Juice: particles, screen shake, hit freeze, combo text, spectacle events |
| `references/promo-video.md` | DEPLOY | Slow-mo trick, Playwright recording, FFmpeg assembly, mobile portrait format |
| `references/deploy.md` | DEPLOY | GitHub Pages, Vercel, static hosting, pre-deploy checklist |
| `references/capacitor-ios.md` | DEPLOY | Capacitor 5+ iOS: SPM setup, asset contracts, touch controls, debugging |
