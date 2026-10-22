# The pipeline

The reference implementation lives in `road-to-aew`, `scripts/promo/` (plus `scripts/audio/dsp.py`),
commit `2cba9ac`. Everything it writes goes under `tmp/promo/` (gitignored).

## Stages

```
timeline.json   beat map: bpm, sections and hits in cut beats, the running order (layout) and
                inserted sections; read by the edit, the score and the mix
capture/        Playwright + virtual clock: scripted takes -> 4K JPEG frames + take.json
edl.mjs         the edit: shots, speed ramps, camera, impact fx, poster overlays, sound cues;
                every game moment pinned to a beat
pages/          overlay.tsx renders the poster graphics (VS cards, captions, end card) with the
                game's own CSS; heroes.tsx is a grid for picking the hero's look
compose/        compose.py cuts takes + overlays into 1920x1080 60 fps; deglitch.py repairs frames
audio/          compose_trailer.py writes the score; render_game_audio.mjs rebuilds the game's
                logged sounds; arena.py renders the crowd engine; mix.py places and masters
```

## File map

| File | Role | Portable |
|---|---|---|
| `capture/vclock.js` | Replaces every time source in the page (performance.now, Date, timers, rAF, idle callbacks) with one virtual clock; drives CSS and Web Animations through `document.getAnimations()` in manual mode | yes |
| `capture/lib.mjs` | `launch()` (headless shell, device scale 3, GPU memory flag, API mocks, tutorial flags, toast hide, the sound log stand-in), `Recorder` (step, run, hold, mark, save), `dragCardRecorded`, game boot and stage helpers | launch and Recorder yes; boot, stage and mock routes are game-specific |
| `capture/run-take.mjs` | `node run-take.mjs <take> [--dsf 3] [--out dir]`; merges `window.__AUDIO_LOG__` into take.json | yes |
| `capture/takes/*.mjs` | One scripted scene per file; exports `default async ({page, cdp, dir})` | no: written per trailer |
| `capture/overlays.mjs` | Renders `pages/overlay.html` at 1920x1080 for every frame an overlay is active -> `tmp/promo/overlay/o#####.png` (RGBA) | yes |
| `pages/overlay.tsx` | Poster elements: `vs`, `caption`, `cta`, `flash`; deterministic `window.__promo.render(t)` | the element renderers yes; the wrestler lookup and hero spec are game-specific |
| `edl.mjs` | Beat helpers, the remap through `layout`, `shot`/`posterShot`/`impact`/`bump`/`caption`/`vs`/`cue`, `sfxBeat`; then the cut itself | helpers yes; the cut no |
| `compose/compose.py` | Per output frame: shot -> source time through the speed curve -> camera (focus x,y in CSS px, zoom, roll, eased keys) -> impact fx -> grade + vignette -> overlay -> flash and chromatic split -> ffmpeg. `--sheet`, `--frames`, `--from/--to`, `--scale`, `--crf`, `--maxrate` | yes |
| `compose/deglitch.py` | Replaces a frame that differs from both neighbours while they agree (a compositor dropout); keeps `f#####.orig.jpg` | yes |
| `audio/compose_trailer.py` | The score: drum, bass, stab, lead, pad, braam, riser, impact and bell synths; groove on the output grid; section loudness curve; stems + premix | synths and machinery yes; the arrangement (`render()`, `DYNAMICS`) is the cut's |
| `audio/mix.py` | Cue sounds (samples + synthesized), the game layer, the crowd render, ducking, gaps, mastering to -13 LUFS / -1 dBTP, the per-section balance table | the machinery yes; `GAPS`, `BED_CURVE` and the inserted-section cases are the cut's; `SAMPLE_FILES` is the game's |
| `audio/arena.py` | numpy render of the shared crowd engine's audience mode from its own files and gains | yes for any game on the shared engine |
| `audio/render_game_audio.mjs` | With no argument, every take on disk. Turns a take's sound log into `tmp/promo/audio/game/<take>/events.json`: samples (key, vol, rate), synth clips rendered offline inside the game page, crowd-engine cues | the synth replay is game-specific |
| `audio/render_engine.mjs` | Offline render through the engine itself (Tone.js). Kept for checks; the audience engine loses voices offline, so arena.py is the path | optional |
| `scripts/audio/dsp.py` (game repo) | Shared numpy DSP: oscillators, ADSR, EQ, reverb IR, compressor, sidechain, WAV in/out, loudness via ffmpeg | yes |

## Data contracts

### take.json (per take, written by Recorder.save)

```json
{"frames": [0.0, 16.667, ...],            "// virtual ms of every f#####.jpg"
 "marks":  [{"label": "chop_card", "vt": 9065.2, "frame": 125}, ...],
 "sfx":    [{"kind": "table_crash", "t": 12480.1}, ...],   "// the game's own SFX log (hardcore layer)"
 "audio":  [{"t": 9648.0, "src": "engine", "kind": "impact", "data": {...}},
            {"t": 9648.0, "src": "road", "kind": "playCardPlay", "nested": false, "data": [...]}],
 "take": "table", "finisher": "busaiku_knee_finisher"}       "// extra fields passed to save()"
```

Frames are 60 fps unless the take switched `rec.fps` to 120 or 240 for a slow-motion window; the
compositor reads whatever frame is nearest the source time, so slowed sections stay smooth only where
they were captured dense.

### timeline.json

```json
{"bpm": 96, "length_beats": 55,
 "sections": {"tease": [0, 1], "creator": [1, 5], ...},         "// cut beats"
 "hits": {"brainbuster_hit": 12, "pin1": 38, "roster": [42, 43, 44, 45, 46, 47], ...},
 "layout": [[0, 1, 0], [5, 8, 11], [8, 12, 26, 1.5], ...],     "// [cutStart, cutEnd, outStart, stretch?]"
 "inserted": {"creator": [1, 11], "gameplay": [14, 26]},       "// output beats"
 "length_out": 98}
```

Cut beats are the order the trailer was first written in; `layout` maps each block of cut beats to
where it plays in the output and how much slower (`k`). A beat past the last block follows that block
(the ring-out tail). Inserted sections exist only in output beats. Details in `edit.md`.

### edl.json (written by edl.mjs, read by compose.py, overlays.mjs, mix.py)

```json
{"fps": 60, "size": [1920, 1080], "duration": 61.25, "bpm": 96,
 "takes_dir": "tmp/promo/takes", "overlay_dir": "tmp/promo/overlay",
 "hero": {"name": "Jax Dynamo", "arch": "strong_style", "seed": "promo-4"},
 "grade": {"lift": 0.03, "contrast": 1.07, "gamma": 0.95, "saturation": 1.12, "vignette": 0.32},
 "shots": [{"t0": 8.75, "t1": 16.25, "take": "turn", "src": {"vt": 8465.2},
            "speed": [[0, 0.92]], "cam": [{"t": 0, "x": 640, "y": 360, "z": 1, "r": 0, "e": "inOut"}]}],
 "fx": [{"type": "shake", "t": 20.0, "amp": 26, "decay": 0.29, "freq": 28, "rot": 1.0},
        {"type": "punch", "t": 20.0, "amt": 0.12, "decay": 0.19},
        {"type": "flash", "t": 20.0, "dur": 0.2, "peak": 0.93},
        {"type": "chroma", "t": 20.0, "amt": 10, "decay": 0.16}],
 "overlays": [{"kind": "caption", "t0": 8.88, "t1": 10.88, "lines": ["Every move", "is a card"],
               "x": 960, "y": 330, "size": 84, "rot": -3, "band": "Drag it into the ring"},
              {"kind": "vs", "t0": 7.5, "t1": 8.75, "opp": ["no_gimmicks_steve", "bulldozer_barry"],
               "slotStep": 0.156, "venue": "Legion Hall · Friday Night Fights", "tag": "Tonight!"},
              {"kind": "cta", "t0": 57.25, "t1": 61.25, "url": "5starbooker.com/game", "line": "Wrestling card game · Play now"}],
 "cues": [{"t": 20.0, "sound": "hit_heavy", "gain": 2}, {"t": 20.02, "sound": "crowd_roar", "gain": 0, "dur": 3.2}]}
```

A shot with `take: "black"` is a poster shot (the overlay covers the frame). Speeds and camera times
in the file are already stretched by the layout: they are what the viewer sees.

### events.json (per take, from render_game_audio.mjs)

```json
[{"t": 9648.0, "type": "engine", "kind": "impact", "data": {"strike": "chop", "strong": false, "id": "..."}},
 {"t": 9648.0, "type": "sample", "key": "cardPlay", "vol": 0.8, "rate": 1, "offset": 0},
 {"t": 10998.0, "type": "synth", "kind": "playTierUp", "file": "tmp/promo/audio/game/clips/3.pcm", "sr": 48000}]
```

mix.py maps each event's virtual time through the speed curve of every shot that shows that take, so
a sound plays at normal speed wherever its moment appears in the cut, slow motion included.

## Environment

| Need | Detail |
|---|---|
| Game dev server | `setsid nohup npm run dev -- --port 3000 --strictPort > tmp/promo/logs/dev.log 2>&1 &`; `PROMO_GAME_URL` overrides the default `http://localhost:3000/static/game/` |
| Chromium headless shell | `PROMO_CHROME` path; the default is Playwright's cache path in cloud sessions (`/opt/pw-browsers/chromium_headless_shell-*/chrome-linux/headless_shell`). `playwright-core` is the only npm dependency |
| Python | 3.11+, a venv with `numpy scipy opencv-python Pillow`; `imageio-ffmpeg` as the ffmpeg fallback |
| ffmpeg | with libx264; `PROMO_FFMPEG=/path/to/ffmpeg` when it is not on PATH (a static build in the scratchpad works) |
| Crowd library | `tmp/promo/shared-audio/`: the shared engine's audio files (`ambience/`, `reactions/`, `chants/`, `referee/`, `effects/`) staged from the engine's repo (`mmr-ratings`, branch `dev`, `audio/`). arena.py reads them directly. Reuse of the recordings was cleared by the owner |
| Static server (optional) | `python3 -m http.server 3005 --directory tmp/promo/shared-audio`, only for `render_engine.mjs`: the Vite dev server rewrites `.js` and breaks the engine's integrity hash |

Chromium runs with `--mute-audio`; no audio is captured. Every sound in the trailer is rebuilt
offline from logs, sample-exact and deterministic.

## Port to another game

The pipeline assumes a React or DOM game on a dev server. Copy `scripts/promo/` and
`scripts/audio/dsp.py`, then rewrite the pieces below. Keep the names so the skill's references still
apply.

| Piece | Rewrite |
|---|---|
| `lib.mjs` `launch()` | The API routes to mock (saves, auth, analytics), the localStorage flags that skip tutorials and tips, the CSS that hides toasts, the `window.FSMatchAudio` stand-in if the game uses the shared crowd engine (keep it returning `true` from `cue` so the game behaves as it does live) |
| `lib.mjs` boot (`toCombat`) | The click path from the title screen to the scene; wait for a state the DOM shows (a button enabled), with a screenshot and a button-text dump on failure |
| Stage seams in the game | A test-only global behind an enable flag set by `addInitScript`, that mutates the live state and re-renders: see `capture.md`, "Stage seams". Add one per scene you need to set up |
| Sound log | Wrap the game's audio system so every play call lands in `window.__AUDIO_LOG__` with the virtual time; mark nested calls. Rebuild them in `render_game_audio.mjs` by replaying the outer calls into an `OfflineAudioContext` in the real page |
| `overlay.tsx` | The hero spec and the opponent lookup (name, nickname, title, alignment, look) from the game's roster module; the poster CSS classes from the game's stylesheet |
| `edl.mjs` hero, grade | Hero spec; grade to taste (the defaults are mild) |
| `mix.py` | `SAMPLE_FILES` (sample key -> asset path), `BASE_DB` for any new cue sound, `GAME_REPLACES` (trailer cues the game now plays for real) |
| `arena.py` | Only `LIB` and the volume constant, if the game is on the shared engine; otherwise replace it with the game's crowd files at the game's gains |
| `timeline.json`, `edl.mjs` body, takes | New |

Everything else (virtual clock, recorder, drag helper, compositor, deglitch, overlay renderer, synths,
mastering) ports unchanged.
