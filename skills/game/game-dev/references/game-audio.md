# Game Audio Reference

Web Audio API patterns for browser games. Zero external dependencies. Optional Strudel.cc upgrade for advanced music (AGPL-3.0 — check license compatibility before using).

---

## AudioManager Singleton

Create `AudioContext` lazily on first user gesture — browsers block contexts created before interaction silently.

```javascript
// src/AudioManager.js
let ctx = null;
const masterGain = { node: null };
const categoryGains = {};

export function getCtx() {
  if (!ctx) {
    ctx = new AudioContext();
    masterGain.node = ctx.createGain();
    masterGain.node.connect(ctx.destination);
    masterGain.node.gain.value = 1.0;

    for (const cat of ['music', 'sfx', 'ambient']) {
      const g = ctx.createGain();
      g.connect(masterGain.node);
      g.gain.value = 1.0;
      categoryGains[cat] = g;
    }
  }
  return ctx;
}

export function setVolume(category, value) {
  // category: 'master' | 'music' | 'sfx' | 'ambient', value: 0.0–1.0
  if (category === 'master') {
    masterGain.node.gain.setTargetAtTime(value, getCtx().currentTime, 0.01);
  } else if (categoryGains[category]) {
    categoryGains[category].gain.setTargetAtTime(value, getCtx().currentTime, 0.01);
  }
}

export function getCategoryOutput(category) {
  getCtx(); // ensure initialized
  return categoryGains[category] ?? masterGain.node;
}
```

**Volume hierarchy**: master gain → category gains (music, sfx, ambient) → individual sources. Never set `gain.value` on a BufferSourceNode directly — wire it through the category gain.

---

## Sound Effects (SFX)

Load audio buffers once at startup. Pool `AudioBufferSourceNode` instances — they are one-shot and cheap to create.

```javascript
// src/SFX.js
import { getCtx, getCategoryOutput } from './AudioManager.js';

const buffers = {};

export async function loadSFX(name, url) {
  const ctx = getCtx();
  const resp = await fetch(url);
  const data = await resp.arrayBuffer();
  buffers[name] = await ctx.decodeAudioData(data);
}

export function playSFX(name, { volume = 1.0, rate = 1.0 } = {}) {
  const ctx = getCtx();
  const buf = buffers[name];
  if (!buf) { console.warn(`SFX "${name}" not loaded`); return; }

  const src = ctx.createBufferSource();
  src.buffer = buf;
  src.playbackRate.value = rate;

  const gainNode = ctx.createGain();
  gainNode.gain.value = volume;
  src.connect(gainNode);
  gainNode.connect(getCategoryOutput('sfx'));

  src.start();
  // BufferSourceNode auto-disconnects after playback — no cleanup needed
}
```

**Rapid-fire sounds** (e.g., bullet hits): vary `rate` slightly per call (`0.9 + Math.random() * 0.2`) to avoid the "machine gun" artifact.

---

## Background Music (BGM) — Procedural Sequencer

No audio files needed. Uses Web Audio oscillators and timing.

```javascript
// src/BGM.js
import { getCtx, getCategoryOutput } from './AudioManager.js';

const NOTES = {
  C4: 261.63, D4: 293.66, E4: 329.63, F4: 349.23,
  G4: 392.00, A4: 440.00, B4: 493.88, C5: 523.25,
};

const SEQUENCE = ['C4', 'E4', 'G4', 'A4', 'G4', 'E4', 'D4', 'C4'];
const STEP_DURATION = 0.25; // seconds per note

let schedulerTimer = null;
let nextStepTime = 0;
let stepIndex = 0;
let playing = false;

function scheduleNote(freq, startTime, duration) {
  const ctx = getCtx();
  const osc = ctx.createOscillator();
  const env = ctx.createGain();

  osc.type = 'triangle';
  osc.frequency.value = freq;
  env.gain.setValueAtTime(0, startTime);
  env.gain.linearRampToValueAtTime(0.3, startTime + 0.01);
  env.gain.exponentialRampToValueAtTime(0.001, startTime + duration * 0.9);

  osc.connect(env);
  env.connect(getCategoryOutput('music'));

  osc.start(startTime);
  osc.stop(startTime + duration);
}

function scheduler() {
  const ctx = getCtx();
  const lookahead = 0.1; // schedule 100ms ahead
  while (nextStepTime < ctx.currentTime + lookahead) {
    const noteName = SEQUENCE[stepIndex % SEQUENCE.length];
    scheduleNote(NOTES[noteName], nextStepTime, STEP_DURATION * 0.8);
    nextStepTime += STEP_DURATION;
    stepIndex++;
  }
  schedulerTimer = setTimeout(scheduler, 25);
}

export function startBGM() {
  if (playing) return;
  playing = true;
  nextStepTime = getCtx().currentTime;
  scheduler();
}

export function stopBGM() {
  playing = false;
  clearTimeout(schedulerTimer);
}
```

**Swap sequences for level progression**: define multiple `SEQUENCE` arrays and pass one as an argument to `startBGM(sequence)`.

---

## AudioBridge — EventBus Integration

Connect game events to audio without coupling game logic to AudioManager:

```javascript
// src/AudioBridge.js
import { on } from './EventBus.js';
import { playSFX } from './SFX.js';
import { startBGM, stopBGM } from './BGM.js';

export function initAudioBridge() {
  on('ENEMY_HIT',    () => playSFX('hit', { rate: 0.9 + Math.random() * 0.2 }));
  on('PLAYER_DEATH', () => { stopBGM(); playSFX('death'); });
  on('LEVEL_UP',     () => { stopBGM(); startBGM(nextLevelSequence); playSFX('levelup'); });
  on('GAME_OVER',    () => { stopBGM(); playSFX('gameover'); });
  on('SCORE_CHANGE', ({ combo }) => {
    if (combo >= 10) playSFX('combo', { rate: 1.0 + combo * 0.02 });
  });
}
```

Call `initAudioBridge()` inside the first user-gesture handler alongside `getCtx()`.

---

## Preloading SFX at Game Start

```javascript
// In main.js, inside click handler:
document.addEventListener('click', async () => {
  const { getCtx } = await import('./AudioManager.js');
  const { loadSFX } = await import('./SFX.js');
  const { startBGM } = await import('./BGM.js');
  const { initAudioBridge } = await import('./AudioBridge.js');

  getCtx(); // create context

  await Promise.all([
    loadSFX('hit',      'assets/hit.wav'),
    loadSFX('death',    'assets/death.wav'),
    loadSFX('levelup',  'assets/levelup.wav'),
    loadSFX('gameover', 'assets/gameover.wav'),
    loadSFX('combo',    'assets/combo.wav'),
  ]);

  initAudioBridge();
  startBGM();
}, { once: true });
```

---

## Optional: Strudel.cc Upgrade

[Strudel.cc](https://strudel.cc) provides a live-coding music pattern language that runs in the browser.

**License warning**: Strudel is AGPL-3.0. If your game is closed-source or commercial, AGPL requires you to open-source the entire project that links to it. Check license compatibility before using.

```javascript
// Strudel pattern example (replaces BGM.js procedural sequencer)
import { repl } from 'https://unpkg.com/@strudel/repl@1.0.0';

const pattern = `note("c4 e4 g4 a4").sound("triangle").room(0.4)`;
const { start, stop } = repl({ pattern });

export const startBGM = () => start();
export const stopBGM  = () => stop();
```

---

## Error Handling

### Error: AudioContext Blocked (DOMException: play() failed)
**Cause**: Context created before user gesture
**Fix**: Ensure `new AudioContext()` only runs inside event listener. Use `getCtx()` lazy pattern — never call it at module load time.

### Error: Sound Plays But Volume Is Always 0
**Cause**: Source connected directly to destination, bypassing gain nodes, or gain value is 0
**Fix**: Verify wiring: source → gainNode → categoryGain → masterGain → destination. Log `gainNode.gain.value` to confirm.

### Error: Rapid SFX Triggers Sound "Machine Gun" Effect
**Cause**: Same buffer played repeatedly at identical pitch
**Fix**: Randomize `playbackRate`: `src.playbackRate.value = 0.9 + Math.random() * 0.2`.

### Error: BGM Sequencer Drifts Over Time
**Cause**: Using `setTimeout` for timing instead of AudioContext clock
**Fix**: The scheduler pattern above uses `ctx.currentTime` for scheduling and `setTimeout` only for wakeup. Never schedule relative to `Date.now()`.
