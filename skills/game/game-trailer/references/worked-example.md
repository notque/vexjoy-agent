# Worked example: ROAD TO THE BIG TIME, cut 6

61.25 s (98 output beats at 96 BPM), 1080p60, delivered 2026-10-02. Hero: Jax Dynamo (face,
brawler; look `strong_style` seed `promo-4`). Captured on `road-to-aew` commit `20943e7`; the pipeline as described is `2cba9ac`:
`scripts/promo/timeline.json`, `scripts/promo/edl.mjs`, `scripts/promo/capture/takes/*.mjs`.

## Takes

| Take | Scene | Staged | Marks and logs | 4K time |
|---|---|---|---|---|
| `title` | The title screen, menu plates hidden by injected CSS | guest click, 4.5 s hold | `title_in` | 2 min |
| `studio` | Create-a-wrestler, one pick at a time, then the hero's look | picks: Muscular, Giant, Cowboy, Masked, Monster Paint, Luchador, Hardcore, Showman, Neon Nights, Blood Money; then the editor set to the hero look; three pose clicks | `pick0..9`, `hero`, `hero_victory` | 3 min |
| `turn` | Act 1, Legion Hall, vs "Bulldozer" Barry Blackacre: one whole turn | hand chop, jab, dropkick, suplex, rope break; 4 energy; crowd 22; intent attack 9 "Shoulder Tackle" | `*_card`, `*_release` ×4, `end_turn`; 66 sound events | 6 min |
| `table` | Act 1 vs Barry: Set Up a Table, Brainbuster through it, two Cookie Sheet Shots | hand set-up-a-table, brainbuster, cookie ×2, western lariat; 8 energy; crowd 49 (the table card tips LOUD); head at 62% so the shots bust him open; 240 fps over the brainbuster, 120 over the cookies | `table_*`, `brainbuster_*`, `cookie1/2_*`; SFX log: `table_set`, `table_crash`, `splat` ×3, `muta` ×2, `muta_full` | 19 min |
| `hardcore` | Act 2, The Armory, vs "Staplegun" Stan Scarface | Bag of Tacks, Thumbtack Bodyslam, end turn (Stan's Light Tube Swing busts Jax open), Barbed Wire Bat, Singapore Cane Shots; 120 fps on each landing | `tacks_*`, `slam_*`, `end_turn`, `bat_*`, `cane_*`; SFX `tacks`, `tack_crunch`, `splat` | 16 min |
| `pretzel` | Act 2 vs "The Pretzel" Preston Twister: body parts | every part worn; legs at critical + 9 so the Leg Kick puts them in the red live; Texas Cloverleaf taps him | `kick_*`, `clover_*` | 8 min |
| `moneymaker` | Act 3, The Big Room, vs "Moneymaker" Marcus Millions: the main event | Western Lariat (signature), Corner Punches to SOLD OUT, the pull, Busaiku Knee (`PROMO_FINISHER`), 1-2-3; HP 118; 9 energy; crowd 75; 120 fps over the finisher | `lariat_*`, `punches_*`, `fin_card`, `fin_release`; 101 sound events | 14 min |
| `finishers` | Act 3 vs "Commercial Break" Carson Craft: the roulette | one finisher per hand, energy 9, crowd 95, HP 999, parts healed; Package Piledriver, Rainmaker, Coffin Drop, Destino, Styles Clash, Stunner (Styles Clash never fired: four used) | `<id>_card`, `<id>_release` | 19 min |

A ninth directory, `creator`, is the cut-4 random-roll take; it stayed on disk unused after `studio`
replaced it.

## Running order

Cut beats are the order the trailer was first written in (the beat map's `sections`); the layout
reorders and stretches them. Output seconds = output beat × 0.625.

| Output | Cut beats | k | Section | Picture | Captions | Sound |
|---|---|---|---|---|---|---|
| 0.00 to 0.62 | 0 to 1 | 1 | tease | `table`: the brainbuster through the table, blood in the air, 0.42×, the splat on beat 0.55 (frame 0 is the thumbnail) | "A wrestling card game" (bottom) | impact, table crash, splat, pop |
| 0.62 to 6.88 | inserted | | creator | `studio` full screen, zoom 1.0 to 1.06, ten picks, lands on the hero at 1.7× | "Build your wrestler" + band "Every pick shows up in the ring" + burst "Yours!" | tick per pick, arp and pad, kick from halfway, riser |
| 6.88 to 7.50 | 5 to 6 | 1 | introducing | `studio`: the hero's victory pose at 1.9 to 2.2× | (the game's own INTRODUCING plate) | impact, pop |
| 7.50 to 8.75 | 6 to 8 | 1 | vs_barry | VS card, 4-step slot machine landing on Barry, tag "Tonight!" | venue "Legion Hall · Friday Night Fights" | slot ticks, braam, boo |
| 8.75 to 16.25 | inserted | | gameplay | `turn` full screen at 0.92×, zoom 1.0 to 1.045: four cards, End Turn, Barry's hit, a new hand | "Every move is a card" / "Drag it into the ring"; band "Hits fill the meter"; "They hit back" / "Their next move is always on screen"; "New hand, new turn" | the game's own card and hit sounds, pop on the first card landing, the game's boo on Barry's hit |
| 16.25 to 18.13 | 8 to 10 | 1.5 | table_set | `table`: the Set Up a Table card, the table landing | "Set up a table" / "Hardcore cards change the ring" | card lift, whoosh, table unfold, ooh |
| 18.13 to 20.00 | 10 to 12 | 1.5 | brainbuster | the card flies in, slow motion into the gap | "Brainbuster!" / "Play the card · through the table" | riser into silence |
| 20.00 to 21.88 | 12 to 14 | 1.5 | impact, first_blood | hit (tight), THROUGH THE TABLE (wide), FIRST BLOOD (tight), Muta 2 stamp | | the drop: braam, impact, crash; roar; splat; muta stamp |
| 21.88 to 27.50 | 14 to 20 | 1.5 | muta | Cookie Sheet Shot to Muta 5, again to FULL MUTA, hold on the crimson mask | "This is awesome!" (gold) / "Clap · clap · clap-clap-clap" | hits, splats, stamps, braam on FULL MUTA, the chant |
| 27.50 to 28.75 | 20 to 21 | 2 | vs_stan | VS Stan, tag "No DQ!" | "The Armory · Honor Series" | slam, boo |
| 28.75 to 35.00 | 21 to 26 | 2 | hardcore | tacks scatter, bodyslam onto them, the light tube busts Jax open, bat, cane | "Thumbtacks"; "Light tube!" / "Heel weapon · first blood"; "Barbed wire. Kendo sticks." | tacks, crunch, glass, splat, boo on the tube, hits |
| 35.00 to 36.25 | 26 to 27 | 2 | vs_pretzel | VS Preston | | slam, boo |
| 36.25 to 39.06 | 27 to 30 | 1.5 | bodyparts | Leg Kick puts the legs in the red, the Cloverleaf taps him | "Break a body part" / "Head · Neck · Back · Arms · Legs"; "Tap out!" (gold) | bone crack, submission hit, roar |
| 39.06 to 44.69 | 42 to 48 | 1.5 | roster | six VS cards, one per beat: Steve, Crenshaw, Chadwick, Victor, Carson, Hannah; faces pop, heels boo | "85 opponents" / "Every one a gimmick" | slam per card, pop or boo |
| 44.69 to 45.94 | 30 to 31 | 2 | vs_money | VS Marcus, tag "Main Event" | "The Big Room · Prime Time" | slam, boo |
| 45.94 to 48.75 | 31 to 34 | 1.5 | crowd | Western Lariat, Corner Punches, the meter to SOLD OUT | "Work the crowd" / "Sold out = finisher time" | signature hit, four light hits with rising pops, riser |
| 48.75 to 49.06 | 34 to 34.25 | 2 | demands | THE CROWD DEMANDS IT (the game's banner) | | braam, impact |
| 49.06 to 52.81 | 34.25 to 35.75 | 4 | roulette | Package Piledriver, Rainmaker, Coffin Drop, Stunner panels, 0.94 s each, slow motion kept | "Steal their finishers" | slot blips, riser, snare roll |
| 52.81 to 53.13 | 35.75 to 36 | 2 | gap | black | | silence |
| 53.13 to 54.38 | 36 to 38 | 1 | finisher | the BUSAIKU KNEE panel slams in, the run-in at 0.42×, the knee on the next beat | (the game's lockup) | panel slam, finisher hit, impact, roar |
| 54.38 to 55.94 | 38 to 40.5 | 1 | pin | 1, 2, 3 on the beats | | mat slaps, referee, bell on three |
| 55.94 to 56.88 | 40.5 to 42 | 1 | winner | WINNER at 0.8× | (the game's plate) | braam, crash, roar |
| 56.88 to 61.25 | 48 to 55 | 1 | end | `title`: the title screen, beams and bulbs | CTA: logo, "Wrestling card game · Play now", `5starbooker.com/game` | title slam, Em chord, three bells, decay |

## Numbers worth copying

- Hook: the single most striking frame at 0.42× with the genre in one line at the bottom.
- Full-screen sections: 6.25 s (creator), 7.5 s (turn). Everything a new player needs to see is in
  those two.
- Two VS cards per match (slot machine for the first, plain for the rest); the roster as six cards at
  one beat each after the stretch.
- One gap of silence before each of the two drops (0.25 cut beats, stretched to 0.5).
- The whole second half at 1.5 to 2×, the roulette at 4×.
- Sound: 101 logged game events in the main-event take alone; the trailer's own cues are the fallback
  for the poster shots.

## Score shape (cut beats)

tease impact and swell -> creator arp, pad, kick from halfway, riser and snare roll into INTRODUCING
(stab) -> VS blips and braam -> half-time groove under the table (drums on the output grid), riser
into the gap -> DROP 1 on the hit: full groove Em C D B, braam, crash; accents on the crash, blood,
stamps, FULL MUTA braam -> hardcore groove with the lead line, a tom on every weapon -> body parts
drums and bass only, tap-out stab -> build with the lead line, riser, braam on the demand, roulette
blips, riser and roll into the second gap -> DROP 2: panel slam, the finisher braam and impact, three
counts with toms and claps, the bell, WINNER braam -> groove under the roster, riser -> the title slam,
Em brass chord, pad, three bells, decay over the last six beats.
