# Capture

The game is filmed frame by frame under a virtual clock, so a 60 fps take is exact however long each
screenshot takes (0.8 s at 4K). Takes are 1280x720 layouts rendered at device scale 3 (3840x2160), so
the compositor can zoom to 2.5× and stay sharp.

## The virtual clock (`capture/vclock.js`)

Injected with `addInitScript` before the page loads. It replaces `performance.now`, `Date`,
`setTimeout`, `setInterval`, `requestAnimationFrame` and `requestIdleCallback`.

| Mode | Use |
|---|---|
| `auto` (default) | A native rAF pump advances virtual time with real time (capped at 100 ms per pump). Menus, boot, waits. |
| `manual` (`rec.manual()`) | The recorder advances time one video frame at a time. `advance(ms)` runs due timers in order, one rAF frame, then syncs every CSS and Web Animation through `document.getAnimations()` (pause, set `currentTime`, finish at the end), then yields three task boundaries so React settles. |

Consequences:

- Playwright's actionability waits (`click()`, `waitFor()`) use timers the clock owns. Under manual
  mode they stall. Use `page.mouse.move/down/up` with `rec.run(n)` between, and resolve every
  bounding box before `rec.manual()` where you can.
- A pulsing or animated button is never "stable" to Playwright even in auto mode:
  `click({ force: true })`.
- `performance.now()` inside the game equals the recorder's clock, so any in-game log stamped with it
  (the hardcore SFX log, the audio log) lines up with the frames exactly.

## Recorder (`capture/lib.mjs`)

```js
const rec = new Recorder(page, cdp, dir, { fps: 60 });   // clears old f#####.jpg in dir
await rec.manual();
await rec.hold(700);              // 700 ms of virtual time at the current fps, capturing
await rec.mark('chop_card');      // label + virtual time + frame index, printed to the log
await dragCardRecorded(rec, 'promo-chop', target, { hover: 5, lift: 4, frames: 12 });
await rec.mark('chop_release');
rec.fps = 240; await rec.hold(1600); rec.fps = 60;   // slow-motion window captured dense
rec.save({ take: 'table', sfx: await page.evaluate(() => window.__HC_SFX__ ?? []) });
```

- `step()` advances 1/fps s and grabs a JPEG through CDP `Page.captureScreenshot` (quality 93,
  `optimizeForSpeed`). `run(n)`, `hold(ms)`. `PROMO_SETTLE_MS` adds a real-time wait before each grab
  (it did not fix 4K layer dropouts; the GPU memory flag did).
- Capture at 120 or 240 fps only across the window that will be slowed in the edit. Slowed footage
  captured at 60 fps repeats frames and steps.
- `dragCardRecorded(rec, instancePrefix, to, {hover, lift, frames, settle, arc})` finds
  `[data-card-instance-id^=prefix]`, hovers `hover` frames, mouse down, lifts `lift` frames, moves
  along an eased arc over `frames` frames (the arc reads as a throw), settles, releases. The marks
  around it (`*_card`, `*_release`) are the edit's anchors.
- Park the mouse off the action between steps (`page.mouse.move(40, 360)` or `(1270, 10)`): a resting
  cursor over a card raises its hover state in the frames.

## A take, end to end

```js
// capture/takes/turn.mjs: one ordinary turn, shown whole
import { toCombat, installStage, Recorder, dragCardRecorded, setHero, ringBell } from '../lib.mjs';
import { HERO } from './table.mjs';
export default async function take({ page, cdp, dir }) {
  await toCombat(page, { name: HERO.name });   // title -> guest -> create -> map -> first match
  await setHero(page, HERO);                    // the hero's appearance, from the game's recipes
  await ringBell(page);                         // waits for END TURN enabled; the bell is force-clicked
  await installStage(page);                     // window.__mk(cardId) and window.__stage(fn)
  await page.evaluate(() => window.__stage((s) => {
    s.enemy.name = '"Bulldozer" Barry Blackacre'; s.enemy.maxHp = 150; s.enemy.hp = 150;
    s.hand = ['chop', 'jab', 'dropkick', 'suplex', 'rope_break'].map((id) => window.__mk(id));
    s.energy = 4; s.maxEnergy = 4; s.crowdNoise = 22;
    s.enemyIntent = { type: 'attack', damage: 9, signatureName: 'Shoulder Tackle' };
  }));
  await page.mouse.move(40, 360);
  const rec = new Recorder(page, cdp, dir, { fps: 60 });
  await rec.manual();
  await rec.hold(700);
  const enemy = await page.locator('[data-testid="enemy-drop-zone"]').boundingBox();
  const target = { x: enemy.x + enemy.width * 0.5, y: enemy.y + enemy.height * 0.45 };
  for (const id of ['chop', 'jab', 'dropkick', 'suplex']) {
    await rec.mark(`${id}_card`);
    await dragCardRecorded(rec, `promo-${id}`, target, { hover: 5, lift: 4, frames: 12 });
    await rec.mark(`${id}_release`);
    await rec.hold(id === 'suplex' ? 900 : 650);
  }
  const endBtn = await page.getByRole('button', { name: /^end/i }).first().boundingBox();
  await page.mouse.move(endBtn.x + endBtn.width / 2, endBtn.y + endBtn.height / 2);
  await rec.run(6); await rec.mark('end_turn');
  await page.mouse.down(); await rec.run(2); await page.mouse.up();
  await page.mouse.move(40, 360);
  await rec.hold(3600);
  rec.save({ take: 'turn' });
}
```

Stage the scene so the moment lands clean: crowd meter just under a tier line when the first play
should tip it (49 -> LOUD), or far from one when a tier banner would sit on the spot; body-part HP just
above the critical line when a kick should put it in the red live; HP set so nobody gets pinned early
(999) or so the pin lands (118 against a 90-damage finisher); the draw pile with the one finisher the
"crowd demands it" pull must find, or with none when it must stay quiet.

## Stage seams in the game

The game exposes test-only globals behind an enable flag the capture sets before boot
(`window.__ROAD_TO_AEW_E2E_ENABLE__ = true` in `addInitScript`). Production never sets it.

```ts
// in the combat screen's effect, guarded by the flag
window.__ROAD_TO_AEW_E2E_COMBAT_STAGE__ = (mutate) => {
  mutate(engine.getState() as CombatState);     // mutate the live engine state
  setState(structuredClone(engine.getState()));  // re-render from it
};
```

`installStage()` wraps it as `window.__stage(fn)` and adds `window.__mk(id, patch)` that builds a
combat card from the live card catalog (`instanceId: promo-<id>-<n>`, which the drag helper matches).
Other seams used: `setHero` (store `setAppearance` from a rolled archetype), `setAct` (store game
state), `window.__HC_SFX__` (the hardcore layer pushes `{kind, t}` on every sound call).

## What the stage seam reaches

`__stage` mutates the combat engine's state: the hand and the piles, energy, HP and Block, body parts,
the crowd meter, the enemy's intent, names. The match's billing is not engine state. The stipulation
(ladder, cage), the grudge, the Main Event Level and the booked opponent are props of the combat
screen that come from the booking path: `useNodeSelection.ts` books the node, `getNodeStipulation(node,
{mapSeed, stipulationsWorked})` rolls a stipulation from `seedrandom("<mapSeed>:<node.id>:stipulation")`
on elite and boss nodes, the opponent comes from `getCustomEnemyWithName` through `Math.random` (which
the virtual clock does not seed), and the result lives in `useCombatFlow`'s React state. Setting
`s.stipulation = 'ladder'` in `__stage` gives the engine the rules and the screen no billing band,
meter or climb strips.

| Need | Do |
|---|---|
| A stipulation or level on the match | Book it through the map before the bell: a node whose seeded roll gives it (or a `mapSeed` that does), or a test-only seam behind the E2E flag that sets the booked match card (a `__ROAD_TO_AEW_E2E_MATCH_CARD__` next to `__STAGE__`) |
| A specific opponent in the ring | Seed `Math.random` in the take's init script before boot, or book the roster node. Renaming `s.enemy.name` puts the roster wrestler on the VS card and the rolled one in the ring |
| A picker's progress state (the Main Event Level picker reads `localStorage['rta-main-event-progress']`; a fresh profile has only level 0 open) | Seed the key in the init script next to the tutorial flags |
| The hero's look | `setHero()` (the store's `setAppearance` from a rolled archetype) |

## The sound log

Chromium runs muted and no audio is captured. Instead every sound the game plays is logged with its
virtual time and rebuilt offline (`audio.md`):

- `launch()` installs a stand-in `window.FSMatchAudio` (the shared crowd engine's global) whose `cue`
  records `{t, src: 'engine', kind, data}` and returns `true`, so the game ducks and skips its own
  fallback sounds exactly as it does live.
- `installStage()` calls `logGameAudio()`, which wraps every `play*`, `start*`, `stop*` method of the
  game's `audioSystem`; a call made from inside another is marked `nested` so the replay only fires
  the outer one.
- `run-take.mjs` merges `window.__AUDIO_LOG__` into `take.json` as `audio` after the take.

## Boot and the current build

`toCombat()` encodes the click path at the time of writing; the game moves under it. The traps that
appeared in one month: the creator rolling a ring name over the typed one (fill, wait, re-check up to
five times); a layout-2 career opening on an "RJ City" present node before the first match (pick a
present with a force click, prefer the HP one); "Ring the Bell" text staying after the click (wait for
the END TURN button to be enabled and the starting overlay to be gone, not for the text); the save
toast landing in frames (mock the POST as success and hide `.pl-toast[role=alert]` with injected CSS).
On any boot failure the helpers screenshot to `tmp/promo/logs/*-fail.png` and dump the button texts.

## Smoke test, then 4K

1. `node scripts/promo/capture/run-take.mjs <take> --dsf 1 --out tmp/promo/smoke` (1 to 2 min).
2. `python "$SKILL/scripts/take_sheet.py" tmp/promo/smoke/<take> --out tmp/promo/smoke/<take>.jpg`
   and look: every mark present in the log, the move on screen, no tooltip or cursor in frame, no
   banner over the moment you need, the slow-motion window covering the impact.
3. `node scripts/promo/capture/run-take.mjs <take> > tmp/promo/logs/<take>.log 2>&1 &` for the 4K run;
   then `deglitch.py` (expect "repaired 0" with the GPU flag; a non-zero count is a frame the
   compositor dropped, now patched from its neighbour) and `render_game_audio.mjs <take>` (no argument:
   every take on disk).

Takes can run side by side. Cut 6 ran two sequential lanes in parallel (`lane table moneymaker
finishers creator & lane hardcore pretzel title &`) and later a third lane against a second dev
server (`PROMO_GAME_URL=http://localhost:3001/static/game/`). One log file per take; memory is the
limit.

Two things matter at 4K: `--force-gpu-mem-available-mb=4096` is in `launch()` because the default
tile budget drops whole layers from busy frames (the finisher cinematic stacks several full-screen
layers; the DOM is right, the screenshot is not); and `deglitch.py` is the safety net behind it.

## Frame 0 and the thumbnail

Frame 0 is the thumbnail on X and YouTube. Keep it clean: the most striking frame of the trailer, no
flash, no cursor, the hook caption already on. Land the first impact on a fraction of a beat later
(0.55) so the thumbnail is the frame before the hit.
