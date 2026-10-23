---
name: game-trailer
description: "Make a trailer, promo, teaser, sizzle reel, launch or gameplay video for one of our browser games (Road to AEW / ROAD TO THE BIG TIME, 5 Star Booker, or any game built the same way) from the real game: frame-exact 4K capture under a virtual clock, a beat-mapped edit with poster overlays printed in the game's own CSS, a score written in code, the game's own sounds and its crowd engine. Use it whenever someone asks for a trailer, a promo or social video of a game, a YouTube or X cut, a re-cut or recapture of an existing trailer, or just 'make a video that shows the game off'. Carries the pace rules the owner settled on and the capture, edit and audio traps that cost time."
user-invocable: true
argument-hint: "<game, and what the trailer must show>"
agent: python-general-engineer
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
  - Task
  - Skill
routing:
  force_route: true
  category: game
  not_for: "cutting footage from a camera or screen recorder (use video-editing); making art or clips with an image or video model (use image-gen or image-to-video)"
  triggers:
    - game trailer
    - trailer for my game
    - cut a trailer
    - trailer cut
    - trailer
    - promo video
    - promo trailer
    - sizzle reel
    - launch video
    - teaser video
    - gameplay video
    - video for socials
    - youtube trailer
    - recapture the trailer
    - re-cut the trailer
    - new cut of the trailer
    - show the game off
    - virtual clock capture
    - frame-exact capture
  pairs_with:
    - video-editing
    - building-with-jev
    - grill-jev
  agents:
    - python-general-engineer
    - pixijs-combat-renderer
---

# Game trailer

A trailer for one of our games is the game itself, filmed. Nothing is mocked up and no generated art or
stock footage goes in. The build itself runs on its dev server and is captured frame by frame under a
virtual clock, the cut is pinned to a beat map, the poster graphics print with the game's own CSS, the
score is written in code, and the sound is the game's own sounds plus its crowd engine, rebuilt offline
to the picture.

This skill carries that pipeline, the pace rules the owner settled on across six cuts of ROAD TO THE
BIG TIME (Road to AEW), and the traps that cost time. Reference implementation: `road-to-aew`,
`scripts/promo/` plus `scripts/audio/dsp.py`, at commit `2cba9ac` (2026-10-22). The finished trailer:
cut 6, 61 s, 1080p60, captured at `20943e7`.

## The bar

What "good" meant to the owner, in the order the reviews raised it. Judge every cut against this table
before sending it.

| Rule | Why (owner's words) | What it looks like in the cut |
|---|---|---|
| Readable before fast | "it moves too fast, I can't see or understand things", said of the 15 s cut and again of the 46 s cut | Shots hold about 1 to 2.5 s (median 1.4 s); quick cuts only inside slow motion. Footage plays at or under real speed. Impacts in slow motion. The viewer registers what a thing is before the next thing. |
| Longer beats shorter | "I'd rather it be a full minute than so fast my eyes can't follow" | 61 s final. Stretch a fast block 1.5 to 2× (layout `k`) instead of cutting shots. |
| Say what the game is | "we need to communicate that it's a card game" | A hook caption on frame 0 ("A wrestling card game"); one whole turn played full screen with captions ("Every move is a card", "They hit back", "New hand, new turn"). |
| Show the whole screen playing | "a full picture of the whole screen as you play cards" | Full-screen sections at zoom 1.0 to 1.05 for the creator and the turn. Zoomed cameras only on moments. |
| The creator shows choices changing | "show it moving options you can select"; "tattoos are harder to see, pick a change that is obvious" | One pick per 0.4 to 0.6 s: build, headgear, mask, face paint, outfit, colour scheme. Hair and ink are too small at trailer size. |
| Moves must read as themselves | "the One Winged Angel doesn't look like one, pick a finisher that looks like what it is" | Pick moves with a dedicated pictogram whose action is legible (Busaiku Knee: run-in, knee, head snaps back). Play the run-in at 0.42×. |
| The crowd knows who's who | "cheer when you're playing cards, boo when the enemy attacks" | Cheers on the player's plays, boos on heel intros and heel hits, one reaction at a time. Audit the cue list every cut. |
| The game's own look and sound | "the captures need to be in our poster style"; "cut 2 still uses the wrong and old sounds" | Recapture on the current build. Poster overlays from the game's CSS. Sounds logged during capture and rebuilt offline; the crowd from the shared engine. |
| End on the win | "I'd rather the video be longer than end with just a sizzle reel" | The roster montage moves before the main event. Finisher, 1-2-3, WINNER, title and call to action close the cut. |
| Music that holds | the 128 BPM cut was the one that "moves too fast" | 96 BPM, one tempo throughout, every hit on picture, a beat of silence before each drop. |

## Two paths

| Situation | Do |
|---|---|
| Same game, new trailer or re-cut | Reuse `scripts/promo/`. New for the cut: the takes in `capture/takes/`, `timeline.json`, the `edl.mjs` body, the score's arrangement (`render()` and `DYNAMICS` in `compose_trailer.py`) and the mix's `GAPS` and `BED_CURVE`, all keyed to the beat map's hit and section names. Unchanged unless the game changed: `lib.mjs`, `compose/`, the synths, `arena.py`, `render_game_audio.mjs`. |
| A game without the pipeline | Port it: `references/pipeline.md`, "Port to another game". Copy the pipeline, rewrite the boot path and stage seams, the sound log hooks, the overlay's wrestler lookup and the sample map. Budget a day for the port before the first take. |

## Workflow

### Phase 1: Scope with the owner

List what must be seen (mechanics, moments, screens), the hero, the opponents, the platform and the
length target. X caps a video at 2:20 and 512 MB; YouTube takes the full file. Write the shot list as a
table: moment, the take that produces it, caption, sound. The owner confirms the list before any
capture. Output: `tmp/promo/plan.md`.

### Phase 2: Rig and smoke test

Dev server up, Chromium headless shell on disk, a Python env with numpy, scipy, opencv-python and
Pillow, ffmpeg with libx264 (`references/pipeline.md`, "Environment"). Write each take, run it at
`--dsf 1` (about 10× faster than 4K), build a contact sheet around its marks with
`scripts/take_sheet.py`, and confirm every mark fired and every moment is on screen. A take that works
at 1× works at 3×; a take that fails at 3× costs 20 minutes to find out.

The stage seam sets engine state (hand, piles, energy, HP, body parts, meter, intent). The match's
billing (stipulation, level, the booked opponent) comes from the booking path, so book it before the
bell (`references/capture.md`, "What the stage seam reaches").

### Phase 3: Capture at 4K

Run `run-take.mjs <take>` in the background with its log in `tmp/promo/logs/<take>.log`. Budget 0.7 to
0.8 s per 4K frame of combat (a 15 s take with slow-motion sections is about 19 minutes). Then
`deglitch.py` on the take and `render_game_audio.mjs <take>` for its sound log (no argument: every
take on disk). Takes can run side by side; cut 6 ran up to three at once, one of them against a
second dev server on :3001 through `PROMO_GAME_URL`.

### Phase 4: Beat map and running order

`timeline.json` holds the bpm, the sections and hits in cut beats, the `layout` (running order with a
stretch factor per block), the `inserted` sections and `length_out`. The edit, the score and the mix
all read it, so a moment moves in one place. `references/edit.md` has the schema and the rules.

### Phase 5: Edit, overlays, score, mix

`edl.mjs` writes the shots, fx, overlays and cues; `overlays.mjs` renders the poster frames;
`compose_trailer.py` writes the score; `mix.py` places the game's sounds, renders the crowd and masters.
The score's `render()` and `DYNAMICS` and the mix's `GAPS` and `BED_CURVE` name the beat map's hits and
sections: a new beat map means rewriting them first (`references/audio.md`, "A new cut"), or the
scripts stop on a `KeyError`. Read the per-section balance table mix.py prints before rendering any
picture.

### Phase 6: Review, then the owner

Whole-cut contact sheet (`compose.py --sheet --every 0.75`), stills at every suspect time
(`--frames`), `scripts/edl_table.py --strict` for pace, `scripts/beat_levels.py` for music holes,
`PROMO_DEBUG=1 mix.py` for the crowd cue list. Fix what you find. Render the final and a 720p preview
under 20 MB, send the preview with a short list of what changed and any trade-off (frame stepping in
slowed footage, a dropped caption). The owner's reply is the next cut's brief;
`references/review.md` maps each kind of feedback to its fix.

### Phase 7: Deliver

Final 1080p60 (`--crf 16 --maxrate 20M`) for YouTube, a social encode when asked, a title and
description (`references/review.md`). Commit the scripts; the videos stay out of git through
`.git/info/exclude`. A new trap goes into `references/lessons.md` the day it is found.

## Commands

From the game repo root, dev server running on :3000.

```bash
SKILL=${SKILL:-~/.claude/skills/game-trailer}   # installed copy, or vexjoy-agent/skills/game/game-trailer
FFMPEG=${PROMO_FFMPEG:-ffmpeg}

# takes: smoke test at 1x, then 4K in the background
node scripts/promo/capture/run-take.mjs turn --dsf 1 --out tmp/promo/smoke
node scripts/promo/capture/run-take.mjs turn > tmp/promo/logs/turn.log 2>&1 &
python scripts/promo/compose/deglitch.py tmp/promo/takes/turn
node scripts/promo/audio/render_game_audio.mjs turn

# the cut
node scripts/promo/edl.mjs > tmp/promo/edl.json
node scripts/promo/capture/overlays.mjs
python scripts/promo/audio/compose_trailer.py
PROMO_FFMPEG=$FFMPEG python scripts/promo/audio/mix.py

# review
python scripts/promo/compose/compose.py --sheet tmp/promo/sheet.jpg --every 0.75
python scripts/promo/compose/compose.py --frames 8.3,20.1 --out tmp/promo/stills
python "$SKILL/scripts/edl_table.py" tmp/promo/edl.json --strict
python "$SKILL/scripts/beat_levels.py" tmp/promo/audio/mix.wav --timeline scripts/promo/timeline.json

# render: final, then a preview the owner can watch in the app
python scripts/promo/compose/compose.py --audio tmp/promo/audio/mix.wav \
  --out tmp/promo/trailer.mp4 --ffmpeg $FFMPEG --crf 16 --maxrate 20M
$FFMPEG -y -i tmp/promo/trailer.mp4 -c:v libx264 -preset slow -b:v 2.4M -maxrate 3M -bufsize 6M \
  -vf scale=1280:720 -c:a aac -b:a 160k trailer-preview.mp4
```

A sound-only change (cues, levels, crowd) needs no picture render: rerun `mix.py` and mux the new
`mix.wav` onto the last render with `ffmpeg -i video.mp4 -i mix.wav -map 0:v -map 1:a -c:v copy`.

## Time and size budgets (measured, cut 6)

| Step | Cost |
|---|---|
| Take at `--dsf 1` | 0.08 to 0.14 s per frame (a 10 s take in about 1 to 2 min) |
| Take at 4K (`--dsf 3`) | 0.7 to 0.8 s per combat frame; creator and title screens 0.3 s. 8 takes: table 19 min, hardcore 16, finishers 19, moneymaker 14, pretzel 8, turn 6, studio 3, title 2 |
| Overlays | about 13 frames/s (2600 frames in 3 min) |
| Score + mix | 1 to 2 min each |
| Final render 1080p60 crf 16 | about 1.8 frames/s (61 s = 25 min); run it in the background |
| Final file | 98 MB for 61 s at maxrate 20M; 720p preview at 2.4 to 3 Mbit: 17 to 19 MB |

## Reference loading

| Read | When |
|---|---|
| `references/pipeline.md` | Setting up the rig, porting to another game, or lost in the file map; the data contracts (take.json, timeline.json, edl.json, events.json) |
| `references/capture.md` | Writing or fixing a take: virtual clock, stage seams, marks, slow motion, the sound log |
| `references/edit.md` | Writing `timeline.json` and `edl.mjs`: running order, stretch, pacing numbers, cameras, captions, the finisher timing model |
| `references/audio.md` | The score, the mix, the game's sounds, the crowd engine, the loudness checks |
| `references/review.md` | Reviewing a cut, the owner feedback to fix map, encodes, YouTube copy, git hygiene |
| `references/lessons.md` | Any time something is wrong and you have a symptom: the symptom to cause to fix register |
| `references/worked-example.md` | The whole cut 6 as a template: takes, running order in beats and seconds, captions, cues |

## Scripts

| Script | Use |
|---|---|
| `scripts/take_sheet.py <take dir> --out sheet.jpg` | Contact sheet of a take around its marks, before and after the 4K run |
| `scripts/edl_table.py edl.json [--strict]` | Shot and overlay table with the pace lint: shots under 0.45 s, footage over 1.15×, zoom over 2.5, captions or VS cards under 0.9 s. Cut 6 passes clean; a flag is a slide back |
| `scripts/beat_levels.py mix.wav --bpm 96 [--timeline timeline.json]` | Per-beat loudness, hole detection, per-section means in output beats |

## Related skills

The poster style itself (slab type, bands, starbursts, halftone) is the game's; its rules live in the
game repo's own poster-style skill. For a cut that will be judged on pace, build a Score ladder
(levels: "every moment registers", "one or two blur", "the owner can't follow") and send the contact
sheet as the image: Call the Skill tool with `building-with-jev`.
