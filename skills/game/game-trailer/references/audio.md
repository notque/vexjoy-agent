# Audio

Three layers, all rendered offline and deterministic: the score (written in code), the game's own
sounds (logged during capture, rebuilt in sync), and the crowd (the shared crowd engine's audience
mode, rendered from its own files). `mix.py` places them, ducks, gates and masters.

## The score (`audio/compose_trailer.py`)

E minor, tempo from `timeline.json`, rendered with numpy through `scripts/audio/dsp.py`. No samples,
no third-party or generated music.

| Part | Synth |
|---|---|
| Drums | `kick` (pitch drop + click, tanh), `clap` (four noise bursts + tone + snap), `snare`, `hat` (six square partials + noise, 7.2 to 16 kHz), `crash`, `tom` |
| Bass | `bass808(midi, dur, glide_from)`: knock, glide, saturation so small speakers hear the note |
| Tonal | `stab` (brass supersaw chord, filter close), `pluck` (arp), `lead`, `pad`; chords Em C D B G with 808 roots 28 36 38 35 31 |
| Trailer | `braam` (power-chord supersaw whose filter blooms), `impact` (sub drop + thump + crack + tail), `riser(beats)`, `reverse_swell`, `blip` (slot tick), `ring_bell` (inharmonic partials) |

Arrangement rules:

- `groove(b0, b1, stabs, lead_line, rolls)` lays bars on the output grid from the drop: a stretched
  block keeps the tempo and only its hits move. Four-beat bars cycle Em C D B with per-bar kick
  patterns, claps on 2 and 4, rolling hats, a brass hook, an optional lead line.
- Sections written by hand in cut beats (the creator arp, the slot-machine blips, the half-time
  table groove) use `RAW = True` blocks or `out_beat()` so they sit on the output grid too.
- Every hit and both gaps (`gap`, `gap2`) come from `HITS` in the beat map: drop, table crash, blood, Muta stamps, weapons, tap-out,
  the signature, the crowd demand, the finisher panel and impact, the three counts, WINNER, the
  roster cards, the title, three bells.
- Risers take `span(b0, b1)` beats so they reach their hit after a stretch.
- `K()` records every kick in output beats; `dsp.sidechain_env` ducks bass, stabs, pad, arp and lead
  under them (depth 0.55, tau 70 ms).
- Gaps: from `hits.gap` to the drop and from the roulette's end to the finisher panel, everything but
  the fx bus is gated to silence (a 200-sample ramp in). The building holds its breath too (`mix.py`
  gates the crowd -16 dB over the same spans).
- `DYNAMICS` is the section loudness curve: (cut beat, dB) points, -10 dB under the creator, 0 on the
  drops. `dynamics_curve()` adds the inserted sections' points and applies it after the glue
  compressor so it survives.
- Master: mono below 120 Hz, EQ (hp 30, -1.5 at 3k, +1.5 at 1.2k, -2 shelf at 10k), peak -6, compress
  -16 dB 2:1, loudness curve, soft clip, peak -1. Stems (`drums`, `bass`, `music`, `fx`) are written
  normalized for inspection; the premix keeps the real balance.

## A new cut

The synths, the groove machinery, the mastering and the mix's plumbing carry over. The arrangement is
the cut's, keyed to the beat map's names, and a new `timeline.json` stops both scripts on a `KeyError`
until these are rewritten:

| File | Rewrite |
|---|---|
| `compose_trailer.py` | `render()`: every `HITS[...]`, `SECTIONS[...]` and `TL["inserted"][...]` reference and the hand-written sections; `DYNAMICS`; the inserted-section points in `dynamics_curve()` |
| `mix.py` | `GAPS` (the silences before the drops), `BED_CURVE` (the crowd bed through the video, in cut beats), the inserted-section bed cases; `BASE_DB` for any new cue sound |
| unchanged | synths, `groove()`, `mix()`, `master()`, `TRAILER_CROWD`, `SAMPLE_FILES`, `GAME_REPLACES`, `arena.py` |

Keep the cut-6 hit names where the moment is the same kind (a drop, a stamp, a pin count) and the
arrangement comes along for free.

## The game's own sounds

1. During capture `lib.mjs` logs every `audioSystem` call and every crowd-engine cue with the virtual
   time (`capture.md`, "The sound log").
2. `render_game_audio.mjs [take ...]` (no argument: every take on disk) turns each log into
   `tmp/promo/audio/game/<take>/events.json`:
   `sample` events keep key, volume, rate and offset (the mix rebuilds them from the game's asset files,
   tape-style rate change); `synth` events (slams, tier-ups, clicks, turn end) are replayed into an
   `OfflineAudioContext` inside the real game page and saved as PCM clips; `engine` events are the
   crowd cues.
3. `mix.py` `game_layer()` maps each event through the speed curve of every shot that shows that take
   (`shot_map`, 1 ms grid), so a sound fires at normal speed wherever its moment appears, slow motion
   included. Events that fire on a cut's first frame land up to 60 ms before the shot's source start;
   they are kept.
4. The game layer sits at `GAME_DB = +6` over the logged volume (`GAME_VOLUME 0.3` × call volume).
   Trailer cues the game now plays for real are skipped (`GAME_REPLACES`), so the hit is never doubled.

A take with no log (a poster shot, or a take captured before the log existed) falls back to the
trailer's own cue sounds (`BASE_DB` table): game samples picked by cue name, plus synthesized foley.

## The crowd engine (`audio/arena.py`)

The games run the shared crowd engine (`mmr-ratings`, `static/js/fs-match-audio.js`, branch `dev`) in
audience mode: recorded files at fixed gains, nothing synthesized. Rendering through the engine
offline lost voices (Tone.js offline context), so `arena.py` reproduces the audience mode in numpy
from the same files and the numbers read out of the engine source. Keep it in sync with that file.

| Rule | Value |
|---|---|
| Reactions (`pop`/`woo`/`entry`/`elimination`/`kickout` -> cheer, `boo`, `comeback` -> slow claps) | Level `0.55 + 0.35 i` (claps `0.35 + 0.25 i`); one at a time: a new reaction of the same kind is dropped while one plays (clips are 6 to 10 s); the bed dips to 60% for up to 3 s under it |
| Trailer liberty | A reaction of the other kind cuts in: the current one fades out over 0.25 s. The engine would drop it; the owner wanted the boo on the enemy's hit to be heard over the cheer for the player's plays |
| Effects (bell, mat contacts heavy/medium/sharp/tap, referee slap, rope rebounds, strikes punch/kick/chop/elbow/slap/stomp, steps) | Each at its dB from the FX table; at most 3 at once by rank; deduped per contact id and within 50 ms; variations alternate; the bell once |
| Chants (`this_is_awesome`, `holy_shit`) | -8 dB × (0.8 + 0.2 i), 30 s cooldown, bed at 75% under |
| Referee count (`slap` with `n`, `matSlap`) | Referee voice at 0.55, the crowd's count at 0.22 on three |
| Bed | The arena ambience loop at `0.12 + 0.13 × level`; level from `BED_CURVE` in the mix (out of the arena for the creator, a building that gets louder match by match, 0.45 to 0.6 under the full-screen turn) |
| Master | Knee-0 limiter at -1 dBFS, then the game's crowd volume (45% -> `0.45^0.8`); the mix adds `CROWD_DB = 10` and then -4 |

Cue sources in the mix: every `engine` event from the takes (strikes, contacts, bell, pops, boos
the game itself fired) plus the edit's `crowd_*` cues translated through `TRAILER_CROWD`
(`crowd_pop` -> pop 0.7, `crowd_roar` -> pop 0.95, `crowd_demands` -> pop 1.0, `crowd_boo` -> boo 0.85,
`chant_awesome` -> chant; `crowd_ooh` and `crowd_gasp` have no engine equivalent and are dropped).
`PROMO_DEBUG=1 python mix.py` prints the merged reaction list with times: read it every cut and check
each boo sits on a heel moment and each pop on the player's.

## The mix (`audio/mix.py`)

| Layer | Level | Notes |
|---|---|---|
| Score | -3.5 dB, ducked 0.45 (0.3 for `hit_heavy`) over 0.45 s under the big hits | so the game's sounds cut through |
| Trailer cues (sfx bus) | `BASE_DB[sound] + cue.gain` | impacts -7/-11, table crash -2, finisher hit -3, VS slam -9, ticks -22 |
| Game layer | +6 dB | the logged sounds at their logged volumes |
| Crowd | engine render × +10 dB, then -4 dB; -16 dB over the gaps | |
| Master | mono below 110 Hz, hp 28 Hz, compress -14 dB 1.8:1, true-peak limiter -1.3 dBTP, loudness iterated to -13 LUFS integrated | measured with ffmpeg `ebur128` |

The balance table mix.py prints (dB RMS per section, per layer, pre-master) is the ears in a session
that cannot listen. Read it as: the score leads at about -16 to -24; game and sfx reach -18 to -20 on
the impact sections; a `-180` means the layer is silent there (fine for a poster shot, a bug under a
fight); a crowd row above the music on a quiet section is a stray reaction.

## Checks that found real bugs

| Check | Command | What it caught |
|---|---|---|
| Per-beat loudness | `python "$SKILL/scripts/beat_levels.py" tmp/promo/audio/mix.wav --timeline scripts/promo/timeline.json` | the -40 dB hole from the unmapped ring-out tail; the creator bed too quiet |
| Crowd cue list | `PROMO_DEBUG=1 python scripts/promo/audio/mix.py` | an edit boo at the start of the turn swallowing the cheers for every card play |
| Balance table | printed by `mix.py` | the game layer silent on a section whose take had no events (render it), the roulette's game layer at -85 (expected: poster slots) |
| Stems | `tmp/promo/audio/mixstem-{music,sfx,game,crowd}.wav`, `stem-{drums,bass,music,fx}.wav` | play one layer alone against the contact sheet when a sound is at the wrong time |
