# Wrestler Archetypes

Catalog of road-to-aew character archetypes. Loaded only when `--target road-to-aew` or `--archetype <name>` is set. Replaces the article's `gym_leader`/`vendor` table.

Two axes: **procedural color archetype** (palette + body type), **gimmick type** (presentation + accessory). A character is one of each. Tier (`--tier act1|act2|act3`) modifies gear quality and venue signal.

## Procedural color archetypes (9)

| Archetype | Primary color | Secondary | Body type | Prompt fragment |
|-----------|---------------|-----------|-----------|------------------|
| `powerhouse` | red | black | heavy musculature, broad shoulders | "powerhouse build, broad shoulders, heavy musculature, red and black gear, intimidating stance" |
| `technical` | purple | silver | lean athletic | "lean athletic build, technical wrestler frame, purple and silver gear with mat-wrestling boots" |
| `high-flyer` | green | white | agile wiry | "wiry agile build, high-flyer frame, green and white gear, lightweight boots, ready stance" |
| `brawler` | orange | brown | rugged mid-weight | "rugged mid-weight build, brawler frame, orange and brown gear, taped wrists, weathered look" |
| `striker` | yellow | black | sharp athletic | "sharp athletic build, striker frame, yellow and black gear, kickpads, defined calves" |
| `submission` | teal | navy | lean grappler | "lean grappler build, submission specialist frame, teal and navy gear, no-nonsense gear, worn knee pads" |
| `showman` | magenta | gold | theatrical flamboyant | "theatrical flamboyant build, showman frame, magenta and gold gear with rhinestones, dramatic pose" |
| `giant` | grey | black | 1.2x scale modifier | "giant frame (1.2x scale, towering presence), grey and black gear, slow imposing stance" |
| `player` | blue | gold | hero athletic | "hero athletic build, player-character frame, blue and gold gear, championship-aspirant pose" |

The `--archetype giant` modifier triggers a 1.2x scale instruction in the prompt; downstream rendering should compensate (existing road-to-aew code does so via React `transform: scale(1.2)` on giant-flagged sprites).

## Gimmick types (10)

| Gimmick | Prompt fragment |
|---------|-----------------|
| `face` | "heroic presentation, confident upright posture, polished gear, eye contact with viewer" |
| `heel` | "villainous presentation, sneering expression, dark accents on gear, intimidating posture" |
| `manager` | "manager character, suit and tie, clipboard in hand, accompanies wrestler (full-body suit not wrestling gear)" |
| `referee` | "referee character, black-and-white striped uniform, whistle on lanyard, neutral authoritative posture" |
| `valet` | "ring-side valet character, glamorous attire, accessories, accompanying-role pose (not wrestling gear)" |
| `commentator` | "commentator character, headset over ears, suit jacket, ringside-desk framing, mid-call expression" |
| `jobber` | "low-tier jobber character, plain unmarked gear, generic features, less-defined musculature, indie-show aesthetic" |
| `dojo-student` | "young dojo-student character, training gear (basic singlet or shorts/shirt), green expression, athletic but unrefined" |
| `prospect` | "mid-tier prospect character, polished but generic gear, aspiring talent expression, ready-to-prove-it stance" |
| `veteran` | "weathered veteran character, scar tissue or visible age, well-worn gear, experienced calm expression" |

A character can combine archetype + gimmick: `--archetype powerhouse --gimmick heel` produces a red-and-black powerhouse with sneering villainous presentation.

## Tier modifiers

| Tier | Gear quality slot | Venue signal slot |
|------|-------------------|-------------------|
| `act1` (Indies) | "basic gear, mass-produced wrestling shorts/boots, no logos or sponsorships" | "smaller venue context (lighting suggests bingo-hall or VFW-show backdrop, but no visible audience or background)" |
| `act2` (ROH) | "upgraded gear, custom-fit shorts and boots, mid-tier sponsor logos visible" | "mid-tier venue context (lighting suggests theater or small arena, polished production)" |
| `act3` (AEW) | "championship-tier gear, custom embroidery, premium materials, possible title belt or championship marker" | "championship-tier venue context (lighting suggests major arena, polished entrance pyrotechnics implied)" |

Tier slots are appended to the prompt only when `--tier` is set. Default (no tier) skips both slots.

## Naming convention

The road-to-aew enemy manifest uses `snake_case` IDs derived from the character display name:

```
"Bangkok Belle Nisa" → bangkok_belle_nisa
"General Gideon"     → general_gideon
"The Giant Pyotr"    → giant_pyotr (definite article dropped)
```

`road_to_aew_integration.py snake-case` handles the conversion. Drop leading articles (`The`, `A`, `An`); replace spaces with underscores; lowercase everything; strip non-alphanumeric except underscore.

## Composition example

```bash
python3 sprite_prompt.py build-portrait \
    --style slay-the-spire-painted \
    --archetype showman \
    --gimmick heel \
    --tier act2 \
    --description "Bangkok Belle Nisa, kabuki-inspired makeup, Thai national colors woven into the showman gear" \
    --output prompts/bangkok_belle_nisa.txt \
    --metadata-out prompts/bangkok_belle_nisa.json
```

This produces a prompt that includes:
- ART_STYLE from `slay-the-spire-painted`
- CHAR_STYLE combining `showman` color/build + `heel` presentation
- TIER appending Act 2 ROH gear quality + venue
- DESCRIPTION = user free text
- RULES = standard magenta-bg full-body block

## Adding an archetype or gimmick

1. Add a row to the relevant table with a single concrete prompt fragment.
2. Mention only color, build, and presentation. Avoid named individuals or trademarked moves.
3. Test the resulting prompt with both backends. Fragments that work on Nano Banana may produce flat output from Codex CLI and vice versa.
4. Add the new key to the `--archetype` or `--gimmick` choices in `sprite_prompt.py`.
5. Update the road-to-aew archetype enum if the project consumes archetype names directly.

## Reference loading hint

Load this file when:
- `--target road-to-aew` is set
- `--archetype <name>` or `--gimmick <name>` is passed
- The user asks "what archetypes are available"

Do not load for spritesheet-mode pipelines that lack the road-to-aew context. The catalog is wrestling-specific; non-wrestling characters use plain `--description` text without archetype slots.

<!-- no-pair-required: section header; pair lives in subsection -->
## Anti-pattern

### Anti-pattern: Mixing archetype with custom style without slot discipline

**What it looks like:** `--archetype showman --style-string "showman wrestler in pink and gold tights"`. The archetype already says showman/magenta/gold; the style string says the same thing.

**Why wrong:** Duplicating slot content confuses the model — it interprets the second mention as a contradiction or doubles down to garish levels. Output drifts from the stable archetype baseline.

**Do instead**: Let archetype own the color/build slot. Use `--style-string` only for visual treatment (palette dithering, outline weight, perspective). If you need archetype-aware art style, edit the relevant preset's prompt fragment in `style-presets.md` instead of layering slot content at runtime.
