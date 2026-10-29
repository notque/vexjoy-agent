# Review, feedback and delivery

A cloud session cannot watch or listen. The review is done with contact sheets, stills, tables and
the owner's eyes on a preview. Six cuts of ROAD TO THE BIG TIME went out this way; each review below
changed the next cut.

## Review a cut before sending it

| Step | Command | Look for |
|---|---|---|
| Whole-cut contact sheet | `python scripts/promo/compose/compose.py --sheet tmp/promo/sheet.jpg --every 0.75` | every shot readable as a thumbnail; captions over quiet frame areas; no caption over a game banner; VS cards landing; the thumbnail (frame 0) clean |
| Stills at suspect times | `compose.py --frames 8.3,20.1,49.3 --out tmp/promo/stills` | the exact frame under a banner, a count, a landing; cursor or tooltip in frame; a dropped layer |
| Pace lint | `python "$SKILL/scripts/edl_table.py" tmp/promo/edl.json --strict` | shots under 0.45 s, footage over 1.15×, zoom over 2.5, captions or VS cards under 0.9 s (cut 6 passes clean) |
| Loudness per beat | `python "$SKILL/scripts/beat_levels.py" tmp/promo/audio/mix.wav --timeline scripts/promo/timeline.json` | holes; a section 6 dB under its neighbours; the tail fading where the picture ends |
| Crowd cue audit | `PROMO_DEBUG=1 python scripts/promo/audio/mix.py \| grep crowd` | a boo on the player's play; a pop on a heel hit; two reactions of the same kind back to back (the second is dropped) |
| Balance table | printed by `mix.py` | `audio.md`, "The mix" |
| Take sheets | `python "$SKILL/scripts/take_sheet.py" tmp/promo/takes/<take> --out tmp/promo/<take>.jpg` | after `deglitch.py`: no half-rendered frames |

Fix, rebuild only what changed (a cue or level change: `mix.py` and a remux; a caption: `edl.mjs`,
`overlays.mjs`, render; a take: capture, then everything), then render.

## Send the preview

- 720p at 2.4 to 3 Mbit (17 to 19 MB for 61 s) so it opens in the app and on a phone; the final 1080p60
  stays on disk, named with the cut number.
- Send it with: what changed since the last cut (three to six lines), the length, and every trade-off
  (frame stepping where 60 fps footage was slowed, a caption removed because a banner sat there, a
  move swapped). The owner decides faster with the trade-offs stated than by finding them.
- One cut per message. A fix found after sending waits for the next cut unless it is a bug in the file
  itself.

## Owner feedback to fix (ROAD TO THE BIG TIME, cuts 1 to 6)

| The owner said | Cause | Fix |
|---|---|---|
| "it moves a little too fast for me, I can't see or understand things" (cut 1, 15 s at 128 BPM) | 16th-note cuts, 1.4 to 1.7× footage, 0.6 s captions | 96 BPM, holds of 1 s and up, captions 1.2 s and up, slower creator flips and roulette (cut 2) |
| "we need to communicate that it's a card game as well" | the reel showed impacts, not play | hook caption "A wrestling card game"; captions on the table set and end card; then a full-screen turn (cut 3) |
| "the captures need to be in our poster style" | takes were from an older build | recapture every take on the current build; new boot path (cut 2) |
| "cut 2 still uses the wrong and old sounds" | stand-in CC0 sounds and crowd | log the game's sounds during capture, rebuild them offline; the crowd from the shared engine (cut 3) |
| "some more actual gameplay ... a full picture of the whole screen as you play cards" | no shot showed the UI whole | the `turn` take: four cards, end turn, the enemy's hit, a new hand, full screen, 7.5 s, captioned (cut 3) |
| "I'd rather the video be longer than end with just a sizzle reel" | the roster montage closed the cut | `layout` reorder: roster before the main event; finisher, 1-2-3, WINNER, title close it (cut 3) |
| "show it moving options you can select" in the creator | random rolls on 16ths | the `studio` take: ten picks one at a time, full screen, 6.25 s (cut 4) |
| "tattoos are harder to see ... pick a change that is very visual and obvious" | ink and hair are small at 720p | picks that change the figure: build, hat, mask, face paint, three outfits, two colour schemes (cut 4) |
| "the only parts I don't like are where the movement is still too fast ... I'd rather it be a full minute" (cut 4, 46 s) | the table-to-roulette half still ran at cut-1 pace | `layout` stretch `k` 1.5 to 4 on those blocks; 61 s (cut 5) |
| "the One Winged Angel doesn't look like one ... pick a finisher that looks like what it is" | the move's pictogram reads as a lift, not the move | Busaiku Knee: a dedicated pictogram with a run-in and a knee to the face; run-in at 0.42×; `IMPACT` 260 (cut 5) |
| "have it cheer for you when you're playing cards, it's kind of booing, and then boo when the enemy attacks" | an edit boo at the turn's start held the reaction slot for 7 s; the engine drops a second reaction | the boo removed, a pop on the first card landing, the game's own boo on the enemy's hit; a reaction of the other kind now cuts in with a 0.25 s fade (cut 6) |
| (found in review, not by the owner) a 1 s music hole mid-video | the end fade at cut beat 56 sat past every layout block and stayed unmapped | beats past the last block follow it, in edl, score and mix |
| (found in review) "Hits pop the crowd" caption under the game's "THE CROWD IS BUILDING!" banner | the game's own callout on that beat | only the band kept, moved under the banner |

Patterns in that table: pace problems are solved by stretching blocks, never by cutting shots; "what is
this game" problems are solved by showing the whole screen and captioning the rule; sound problems are
solved by logging what the game plays, not by better stand-ins; a move that does not read is swapped, not
re-shot.

## Delivery

| Output | Encode |
|---|---|
| YouTube (upload the full file) | `compose.py --audio mix.wav --crf 16 --maxrate 20M` (bufsize 2× maxrate, `+faststart`, yuv420p, high profile); 1080p60; about 1.6 MB/s |
| X / Twitter | same file if under 512 MB and 2:20; otherwise `-crf 18 -maxrate 10M -bufsize 20M -g 120 -ar 48000 -b:a 192k` |
| Preview for the owner | `-vf scale=1280:720 -b:v 2.4M -maxrate 3M -bufsize 6M -c:a aac -b:a 160k` |
| Sound-only change | `ffmpeg -i last.mp4 -i mix.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 320k -shortest` |

YouTube title and description template (the cut-6 copy):

```
Road to the Big Time | Wrestling Deckbuilder Trailer

Every move is a card. Build your wrestler, work the crowd, and fight your way from the indies to the big time.
Play now: https://5starbooker.com/game

- Create your wrestler: build, masks, face paint, outfits, colours
- Every move is a card: drag it into the ring, and hits pop the crowd
- Work the crowd: fill the meter for your signatures and finishers
- Steal finishers from the wrestlers you beat
- Go hardcore: tables, thumbtacks, light tubes, barbed wire, kendo sticks
- Blood and the Muta Scale
- Target body parts and make them tap
- 85 opponents between you and the main event

Chapters
0:00 Create your wrestler
0:08 Every move is a card
0:16 Tables, blood & hardcore
0:36 Body parts, the roster & the main event

#wrestling #prowrestling #deckbuilder #cardgame #indiegame #roguelike
```

Check numbers that come from captions (the roster count) against the game data before publishing,
and add the price or "free to play" when known.

## Git hygiene

- `tmp/promo/` is gitignored. Rendered videos at the repo root go in `.git/info/exclude` (one line
  per file), never in the repo.
- Commit the pipeline after every cut with the cut's reasoning in the body: the commit log is the
  edit history (`git log -- scripts/promo`).
- The game repo's pre-push hook runs the whole unit suite; push in the background with a long timeout
  and read the log, or the push looks hung.
- Run the game's formatter on the promo scripts before committing (lint-staged formats staged files
  on commit; ESLint ignores `scripts/**/*.tsx`).
