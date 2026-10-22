# The edit

One beat map drives picture, score and mix. Every in-game moment is pinned to a beat: a shot names a
take event (a mark or a logged SFX) and the output beat it lands on, and the source start is solved
through the shot's speed curve. Nothing is eyeballed.

## Beat map (`timeline.json`)

| Field | Meaning |
|---|---|
| `bpm` | 96 in cut 6 (0.625 s per beat). 128 read as frantic. |
| `sections` | Named spans in cut beats; the mix prints a balance row per section |
| `hits` | Named beats for the moments the score accents (drops, stamps, pin counts, roster cards, title, bells) |
| `layout` | Running order: `[cutStart, cutEnd, outStart, k?]` per block. The block of cut beats `[a, z)` plays from output beat `c`, each cut beat lasting `k` output beats (default 1). Blocks must tile the output with the inserted sections, in any order |
| `inserted` | Sections that exist only in output beats (`{"creator": [1, 11]}`); their shots and cues are written in output beats with `raw = true` |
| `length_out` | Total output beats; `duration = length_out * 60 / bpm` |

Mapping rule, implemented identically in `edl.mjs` (`outBeat`), `compose_trailer.py` (`out_beat`)
and `mix.py` (`out_beat`): find the block containing the cut beat, `out = c + (b - a) * k`; a block's
end time maps from inside the block (`end = true`); a beat past every block follows the last block,
so the ring-out tail keeps moving with the end card. That last clause fixed a -40 dB hole mid-video.

Changing the order or the pace of a block is one line in `layout`. Then rerun `edl.mjs`,
`overlays.mjs`, `compose_trailer.py`, `mix.py`.

## What stretch does

With `k` on a block:

| Thing | Effect |
|---|---|
| Shot speed curve | `[[t*k, v/k]]` (`stretch: true`, default): the footage plays `k` times slower. `stretch: false` keeps `v` and shows `k` times more footage (the finisher roulette: more of each move) |
| Camera keys | Times scale by `k`; moves get gentler for free |
| Captions, VS cards, cues, fx | Map through `at()`; VS slot machines scale `slotStep` by `k` |
| Score | Drums and bass are laid on the output grid (the tempo holds); hits, risers and the loudness curve map through `out_beat`; a riser's length is `span(b0, b1)` so it reaches its hit |
| Sidechain kicks | Stored in output beats (a stretched block otherwise ducks at the wrong times) |

Cut 6 stretches, block by block: the table set through FULL MUTA 1.5×; VS Stan, the hardcore run and
VS Preston 2×; body parts 1.5×; the roster 1.5×; VS Marcus 2×; the crowd build 1.5×; THE CROWD DEMANDS
IT 2×; the finisher roulette 4×; the second gap 2×. At 1×: the tease, the creator, INTRODUCING, VS
Barry, the turn, the finisher, the pin, WINNER and the title.

## EDL helpers (`edl.mjs`)

```js
shot(take, b0, b1, [eventVtMs, beat], { speed: [[localSec, v], ...], cam: [cam(t, x, y, z, r, ease)], stretch })
posterShot(b0, b1)                 // take: 'black'; the overlay is the picture (VS cards, roster)
impact(beat, k, { flash })         // shake 24k px, zoom punch 0.11k, flash, chromatic split 9k, all decaying
bump(beat, k)                      // the small version for tier stamps and slot ticks
caption(b0, b1, lines, { x, y, size, align, rot, band, burst, gold })
vs(b0, b1, [rosterKeys], venue, { slotStep, tag, heroPose, oppPose })
cue(beat, sound, { gain, dur, n })
sfxBeat(take, kind, n, b0, speed, pinVt, pinBeat)   // the output beat where a logged SFX lands inside a shot
mark(take, label); sfx(take, kind, n)                // take.json lookups (throw when missing)
```

- `cam` is the focus point in game CSS px (1280x720 layout), zoom, roll in degrees, and the ease of the
  segment ending at that key: `linear`, `in`, `out`, `expo` (fast start, long settle), `snap`, `inOut`.
- Speed curves are piecewise linear; the compositor integrates them on a 2 kHz grid. Use a plateau
  then a ramp (`[[0, 1.4], [b(1.1), 1.4], [b(1.4), 0.55]]`) to fly a card in and land the hit slow.
- Grade: `{lift 0.03, contrast 1.07, gamma 0.95, saturation 1.12, vignette 0.32}`; a shot can set
  `nograde` or its own `saturation`.

## Pacing numbers that passed review

| Element | Cut 6 value | What failed before |
|---|---|---|
| Ordinary shot | 0.94 to 2.5 s, median 1.4 s. The one exception: the three-cut on the hit (hit, table, blood) at 0.47 s each, inside slow motion | 0.3 to 0.6 s shots everywhere, "can't see or understand" |
| Footage speed | 1.0× or slower; card drags inside the 1.5× blocks reach 1.07 to 1.13× | 1.4 to 1.7× footage |
| Slow motion on impacts | 0.42 to 0.8× over 120/240 fps capture | none |
| Full-screen sections | Creator 6.25 s at zoom 1.0 -> 1.06; the turn 7.5 s at 1.0 -> 1.045 | a 2.5 s creator flurry at 2× zoom |
| Caption on screen | 1.2 to 3.7 s; a one-word stamp ("Tap out!") at 0.9 s | 0.6 s |
| Creator picks | one per 0.42 s, 10 picks, visible changes (build, hat, mask, paint, 3 outfits, 2 colour schemes) | 16th-note random rolls |
| VS card | 1.25 s with a 4-step slot machine for a match; 0.94 s each in the roster montage | 0.62 s |
| Finisher roulette | 0.94 s per finisher, slow motion kept (`stretch: false`, 0.5×) | 0.23 s per finisher |
| Finisher | run-in 0.42× for 1.15 beats, 0.6× to the hit, 0.75× after | 1.02× |
| Pin count | one count per beat (the game counts every 420 ms: play at 0.672×) | |
| Camera zoom | 1.0 to 2.45; tight only on an impact or a stamp | |
| Total | 61.25 s (98 beats); the hook 0.62 s, INTRODUCING 0.62 s, WINNER 0.94 s | 15 s, 42 s, 46 s |

Rule of thumb: if you had to look twice at the contact sheet to know what a shot is, the viewer
cannot know at all. Stretch the block. `scripts/edl_table.py --strict` passes cut 6 clean with these
numbers as its defaults; any flag is a slide back toward a rejected cut.

## Captions, VS cards, call to action (`pages/overlay.tsx`)

The overlay page imports the game's stylesheet and its poster components, so the trailer prints in
the house style. Elements:

| Kind | Fields | Notes |
|---|---|---|
| `caption` | `lines[]`, `band`, `burst`, `x`, `y`, `size`, `align`, `rot`, `gold` | Slab lines (`.pt-print-slab`), a band under (`.pt-print-band`), an optional starburst (`.pt-starburst`). Stamps in over 0.13 s from 1.9×, drops a few degrees of rotation, scales out over 0.08 s. Two lines maximum; `fitSize` keeps a VS name inside 820 px. An empty `lines` with a `band` is a strip under a game banner |
| `vs` | `opp[]` (roster keys), `slotStep`, `venue`, `tag`, poses | Face side midnight blue lit gold, heel side oxblood lit red, bone split rule, venue band on top, VS burst, hero plate and opponent plate with nickname and title, landing shake and flash. Several `opp` keys make a slot machine that lands on the last |
| `cta` | `url`, `line` | Logo stamps in at top, the line and the URL band at the bottom |
| `flash` | `color`, `peak` | Rarely needed; `impact()` has its own flash |

Fonts load before the first capture (`window.__promo.fonts()`); the overlay captures only frames where
an element is active, as RGBA PNG, and the compositor alpha-blends them after the grade.

Placement rules learned the hard way:

- The game posts its own banners ("THE CROWD IS BUILDING!", tier-ups, "THE CROWD DEMANDS IT", the
  finisher name lockup). Check a still at every banner time; move the caption, or keep only its band
  under the banner.
- Captions go where the frame is quiet: the far side from the wrestlers, or the bottom 25% for a hook
  line. Rotations of -4 to 4 degrees; bigger reads as sloppy.
- One idea per caption. The band says the rule ("Drag it into the ring", "Their next move is always
  on screen"); the slab says the headline.
- The roster count ("85 opponents") sits at the top centre over the montage, not over a name plate.

## The finisher timing model

Where the moment is, and where each number lives:

| Step | ms | Where |
|---|---|---|
| Card release -> cinematic start | 224, measured with stills at 1× | `CINE_DELAY` in `edl.mjs` (`PROMO_CINE_DELAY` overrides) |
| Cinematic start -> the move's first impact | Package Piledriver 300, Rainmaker 240, Coffin Drop 520, Destino 280, Styles Clash 300, Stunner 280, One Winged Angel 480, Busaiku Knee 260 | the `IMPACT` table in `edl.mjs`, copied by hand from the move's pictogram: in `src/components/cards/pictogram/dedicated.ts`, the sum of `d` over the keys up to and including the first key with `hit: true`. The game computes the same through `finisherPanelImpactMs()` in `src/components/combat/finisherPanel.ts` |
| Cinematic length | `max(1400, impact + 900)` | `FINISHER_PLAIN_MS`, `FINISHER_PANEL_HOLD_MS` in `finisherPanel.ts` |
| Pin overlay after the cinematic | 700 | `COMBAT_END_OVERLAY_DELAY_MS` in `TurnBasedCombat.tsx` |
| Counts | every 420 ms: 1, 2, 3, then WINNER | `PIN_STEP_MS` in `CombatPopups.tsx` |

So the finisher shot pins `release + 224 + IMPACT + 1` to the finisher-impact beat, and the pin shot
pins `release + 224 + max(1400, IMPACT + 900) + 700 + 5` to the first count, played at 0.672× so each
count sits on a beat. For a new finisher, add its row to `IMPACT` from the pictogram, then verify with
stills at the impact and the count times; do the same after any change to those four source files. A
finisher without a dedicated pictogram (the plain 1400 ms spotlight) does not read as a move; pick one
that has one.

## Sound cues from the edit

`cue(beat, sound, {gain, dur, n})` names a sound in `mix.py`'s vocabulary: trailer hits
(`impact_big`, `impact_mid`, `title_hit`, `vs_slam`, `finisher_panel`), the game's own sounds by
name (`hit_heavy`, `table_crash`, `blood_splat`, `muta_stamp`, `pin` with `n`), synthesized foley
(`whoosh`, `whoosh_big`, `riser_air`, `tick`, `slot`, `glass_smash`, `bone_crack`, `table_set`) and the
crowd (`crowd_pop`, `crowd_cheer`, `crowd_roar`, `crowd_demands`, `crowd_boo`, `chant_awesome`).
When a take has a sound log, the game plays its own hits and the matching trailer cues are skipped
(`GAME_REPLACES`); keep the cues anyway as the fallback for a take without a log.

The crowd cues are semantic: the player's plays and wins get `crowd_pop`/`crowd_roar`; heel intros,
heel weapons and the enemy's hits get `crowd_boo`; the heel roster cards get boos and the faces get
pops. The engine plays one reaction at a time, so place a cheer where the cheer should start, not on
every hit (`audio.md`, "The crowd engine").
