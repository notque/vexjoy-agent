# Lessons: symptom, cause, fix

Everything that cost more than an hour on the first trailer. Search by symptom. Add a row the day a
new one is found.

## Capture

| Symptom | Cause | Fix |
|---|---|---|
| Whole layers missing from random 4K frames (the finisher cinematic shows the ring but no panel) | The compositor's tile budget at device scale 3; a full-screen layer is about 33 MB and busy frames drop one | `--force-gpu-mem-available-mb=4096` in `launch()`; `deglitch.py` after every take as the net; a settle delay before the grab did nothing |
| `page.click()` / `locator.waitFor()` hang under the manual clock | Playwright's actionability waits use timers the virtual clock owns | Resolve bounding boxes first; `page.mouse.move/down/up` with `rec.run(n)` between |
| A button never clicks in auto mode (the bell) | It pulses; Playwright waits for it to be "stable" | `click({ force: true })` |
| "Ring the Bell" text stays after the click, the wait times out | The text persists while the match-starting overlay runs | Wait for the overlay to be gone and an enabled END TURN button |
| "SAVE FAILED" toast in the frames | The save POST hit the mock and got a GET-shaped reply | Mock POST `/game/api/saves` -> `{success: true}`; inject CSS hiding `.pl-toast[role=alert]` |
| The Match node is locked at career start | Layout-2 careers open on an RJ City present node | Click the present (`[data-testid^="rj-boon-"]`, prefer `rj-boon-hp`) with force, then the match |
| The typed ring name is replaced | The creator rolls a name on mount, sometimes after the fill | Fill, wait 150 ms, re-check, up to five times |
| A finisher in a roulette never fires | Out of energy by the fourth card | Set `energy` per card in the stage call; verify the marks at 1× before 4K |
| A finisher on a broken body part ends the match | The game's tap-out rule | Heal every part in the stage call for a roulette; set HP 999 |
| THE CROWD DEMANDS IT fires in the wrong take | A finisher left in the draw or discard pile when the meter crossed 90 | Filter finishers out of both piles; put exactly one in when the pull is wanted |
| Hover tooltip or raised card in a frame | The cursor rested over the hand | Park the mouse at (40, 360) or (1270, 10) after every action |
| The thumbnail is a white flash | `impact()` at beat 0 with its flash | Pin the first hit to 0.55; frame 0 gets no flash |
| Logged game sounds are silent in the mix | A `playSample` call was nested inside another (`playCardPlay` calls `playSample`) and both were rebuilt, or neither | Log depth marks `nested`; replay only outer synth calls; samples are rebuilt from the logged key/volume |
| `take.json` missing after a crashed run | `save()` runs last | Marks are printed to the log as they happen; rebuild `marks` from `tmp/promo/logs/<take>.log` and `frames` from the file count |
| The dev server is gone after a container restart | It ran in the shell that died | `setsid nohup npm run dev -- --port 3000 --strictPort &` |
| `pkill -f <pattern>` killed the session's own shell | The pattern matched the command line running it | `pkill` on the process name, or `kill` by PID from `pgrep -af` |
| A smoke test take looks right, the 4K take is off by frames | Different device scale changes nothing in time, but a layout change between runs did | Rerun the smoke test on the build you capture |
| The VS card shows one wrestler, the ring another | `s.enemy.name` renamed a randomly rolled opponent; the card used the roster look | Seed `Math.random` in the init script or book the roster node; rename only when the look matches |
| A stipulation, level or grudge set through `__stage` shows the rules but no billing band, meter or strips | Those are props of the combat screen from the booking path, not engine state | Book through the map (seeded by `mapSeed:node.id`), or add a test-only match-card seam behind the E2E flag; seed `localStorage` for a picker's progress (`capture.md`, "What the stage seam reaches") |

## Edit

| Symptom | Cause | Fix |
|---|---|---|
| A hit lands a frame off the beat | The source start was eyeballed | `shot(take, b0, b1, [eventVt, beat])` solves the start through the speed curve; anchor to a mark or a logged SFX (`sfx(take, kind, n)`) |
| The finisher's name lockup lands off the drop | `IMPACT[id]` wrong for a new move, or `CINE_DELAY` changed | Read the move's first hit from the pictogram timeline; measure the delay once with stills at 1×; `PROMO_CINE_DELAY` overrides |
| The 1-2-3 counts drift off the beats | The game counts every 420 ms | Play the pin shot at `420 / 1000 / BEAT` speed (0.672× at 96 BPM) |
| A caption sits on a game banner | The game posts "THE CROWD IS BUILDING!", tier-ups, the finisher lockup on its own schedule | Stills at banner times; move the caption, or keep only its band under the banner |
| Slowed footage steps | Captured at 60 fps, played at 0.5× | Switch `rec.fps` to 120 or 240 across the window that will be slowed |
| After a stretch the camera whips | Camera key times were not scaled | `shot()` scales `cam` times and the speed curve by `k`; write cameras in beats (`b(1.2)`) |
| A stretched roulette shows one frozen pose | Speed divided by `k` on footage that was already slow | `stretch: false` on those shots: keep the speed, show more footage |
| The VS slot machine lands late after a stretch | `slotStep` in seconds | `vs()` scales `slotStep` by `k` |
| Fonts wrong on the first overlay frame | `font-display: swap` faces load on first use | `window.__promo.fonts()` before the first capture |
| A VS name overflows its plate | Long names | `fitSize(text, 820, 96)` |
| The overlay page shows the game's background | The game's stylesheet paints `html`/`body` | Injected `html, body, #root { background: transparent !important }`; CDP `setDefaultBackgroundColorOverride` alpha 0 |
| The roster count caption covers a name plate | Both at the bottom | Count at the top centre |

## Audio

| Symptom | Cause | Fix |
|---|---|---|
| A 1 s hole in the music mid-video | A beat past the last layout block (the end fade) was left unmapped and landed inside the video | `out_beat` past the last block continues from it, in edl, score and mix |
| The bass ducks at the wrong times after a reorder | Sidechain kicks stored in cut beats | Store kicks in output beats |
| A riser ends before its hit | Riser length in cut beats across a stretched block | `riser(span(b0, b1))` |
| Drums go off-tempo in a stretched block | Hand-placed 16ths mapped through the stretch | Lay drums on the output grid (`RAW = True` or `groove()`); map only the hits |
| The crowd cheers under the enemy's hit | An edit boo or cheer earlier holds the engine's single reaction slot (clips are 6 to 10 s) | `PROMO_DEBUG=1 mix.py` lists reactions; place one cheer where it should start; the trailer render lets the other kind cut in with a 0.25 s fade |
| The offline engine render is silent except chants | Tone.js offline context loses the audience engine's voices | `arena.py`: the audience mode in numpy from the engine's files and constants |
| Engine assets fail with an integrity error | The Vite dev server rewrites `.js`; the SRI hash no longer matches | Serve `tmp/promo/shared-audio` with `python3 -m http.server` for `render_engine.mjs` |
| The game's crowd library on `main` lacks effects | The effects shipped on the engine's `dev` branch | Stage the library and engine from `dev`; note the engine file's hash in `arena.py` |
| A game sound on a cut's first frame is missing | It fired up to 60 ms before the shot's source start | The 60 ms tolerance in `game_layer()` |
| A hit is doubled | The game played it and the trailer cue fired too | `GAME_REPLACES`: cues the game now plays for real are skipped when the take has a log |
| The creator is dead quiet | The bed curve drops out of the arena there and the music sat at -10 | A pad and a louder arp under the creator; a small bed (0.1) so the room is not empty |
| `KeyError: 'brainbuster_hit'` (any hit name) from `compose_trailer.py` or `mix.py` on a new beat map | `render()`, `DYNAMICS`, `GAPS` and `BED_CURVE` are the cut's arrangement, keyed to its hit and section names | Rewrite them for the new cut (`audio.md`, "A new cut"), or keep the names |
| The balance table shows a `-180` game row under a fight | `render_game_audio.mjs` ran with a hard-coded take list and skipped the new take | Run it with the take's name; with no argument it now renders every take on disk |

## Process

| Symptom | Cause | Fix |
|---|---|---|
| Twenty minutes to learn a take is wrong | Captured at 4K first | `--dsf 1` smoke test and a take sheet first; 4K in the background with a log |
| The owner cannot judge the cut from a description | No picture | Send the 720p preview every cut; name what changed and the trade-offs |
| "I love a lot of it" plus one complaint | The cut was mostly right | Change only what the complaint names; a sound-only fix is a remux, not a re-render |
| The pre-push hook runs for ten minutes | The game repo's hook runs the unit suite | Push in the background with a 30 min timeout; read the log |
| A 98 MB video in `git status` | Rendered at the repo root | `.git/info/exclude` |
| The README still says 128 BPM, and lists takes the cut no longer uses | Docs were not touched when the beat map or the take set changed | Change `timeline.json`, the take set and the README in the same commit; the renderer reads the takes on disk instead of a list |
| Lost context mid-project | Long sessions compact | Every decision is in `timeline.json`, `edl.mjs` comments and the commit bodies; the cut number is in the file names |
