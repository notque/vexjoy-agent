# Game UI Polish Reference

Use this reference when the work mentions game UI, AAA game polish, Steam game polish, roguelike UI, Slay the Spire, deckbuilder UI, or when a user says an interface feels like a website instead of a game.

## Core Thesis

Polished game UI does not come from more gradients, heavier chrome, or “premium” colors. It comes from a coherent interaction metaphor, disciplined hierarchy, and surfaces that feel authored as part of the game world. When a game UI feels wrong, first remove web-product idioms before adding decoration.

For game surfaces, the goal is not “beautiful panel.” The goal is “a screen the game would have shipped.”

## First Diagnostic Question

Ask: would a shipped game like Slay the Spire build this exact surface?

If the honest answer is no, do not tune the palette. Identify the structural web idiom:

- Nested rounded containers around every group.
- Gradient panels used to imply polish.
- Badges and pills explaining state.
- Instructional text explaining obvious interactions.
- Form-like labels and helper text everywhere.
- Dashboard/card mosaics where every item is boxed.
- Decorative glow, shine, blur, or texture competing with readability.
- Multiple accent hues used because the screen lacks hierarchy.

Fix those before color, typography, or asset generation.

## AAA / Steam Polish Heuristics

High-polish game UI usually has these properties:

- One composed screen, not a stack of web sections.
- A small number of strong materials, reused consistently.
- Flat or lightly painted surfaces with intentional edges.
- Selection state shown by position, value, highlight strip, silhouette, or icon, not by a full bordered card treatment.
- Text hierarchy that behaves like game signage: short headers, object names, numbers, terse mechanical labels.
- Interaction objects carry the visual weight; containers stay quiet.
- The background supports focus rather than proving visual effort.
- Fewer simultaneous effects than a website mockup. Restraint reads expensive.

## Layout Rules

Prefer:

- One shell or board per screen.
- Rows, columns, dividers, tabs, silhouettes, and object placement.
- Spatial grouping instead of nested cards.
- One persistent preview/summary region if the interaction needs it.
- Selection marks: left strip, lift, glow, check, slot fill, or value change.

Avoid:

- A modal containing a header gradient, then panels, then cards, then badges.
- Rounded boxes around every option.
- Pill labels for every small attribute.
- Repeating borders with the same visual weight.
- Multiple section backgrounds inside one screen.
- “Step 1 / Step 2” web-form structure unless the game fiction genuinely supports it.

## Color Rules

Game UI can use any palette, but hierarchy must be obvious.

- Choose material first, then color. Example: parchment, steel, canvas, leather, arcade plastic, CRT glass, blueprint paper.
- Avoid “gold equals premium” unless the game fiction truly needs gold.
- Avoid brown by default. Brown often reads muddy unless paired with strong material contrast and deliberate art direction.
- Avoid pink/red fades as a generic drama layer. They often reduce readability and look like a web gradient.
- Accent color should mark state or action, not decorate every border.
- If color is doing too much, remove surfaces instead of inventing a better palette.

## Texture And Gradient Rules

Gradients are not banned, but they must have a job.

Acceptable jobs:

- Lighting a scene.
- Separating foreground from background.
- Simulating a specific material.
- Directing attention to the primary action.

Bad jobs:

- Making an empty rectangle feel premium.
- Decorating every panel.
- Hiding weak hierarchy.
- Adding “AAA vibes” without a game-world reason.

Default to flat material plus one restrained lighting layer. If every box has a gradient, the screen will feel like a website.

## Typography And Text Budget

Game UI text should be terse.

- One screen title, usually 1-3 words.
- Option names and mechanical payoffs are allowed.
- Helper sentences should be rare and only solve confusion discovered in play.
- If the screen still works after removing a sentence, remove it.
- Do not use badges to narrate state. Make the state visible.

Common cuts:

- “Click to...”
- “Choose X to...”
- “Step 1”
- “Your name appears...”
- “4 sprite looks”
- Repeated subtitles under every item.

## Slay The Spire-Style Deckbuilder Guidance

Slay the Spire-like polish comes from object clarity and low container count.

Prefer:

- Cards, relics, rewards, map nodes, and characters as the primary objects.
- Dark scrim or simple board behind the objects.
- Clear hover/selected states.
- Minimal labels.
- Layouts where the player understands the interaction from object placement.

Avoid:

- Website modals with explanatory sections.
- Reward choices in uniform rounded boxes when the card/relic itself should be the object.
- Overdesigned chrome competing with card art.
- Fake “premium” metallic treatments.

## Corrective Workflow

When a user says “this does not feel AAA/polished/game-like,” do this in order:

1. Screenshot the current UI and name the structural failures.
2. Remove nested boxes and decorative gradients before choosing new colors.
3. Define the screen metaphor in one sentence: board, hand, poster, locker, map, shop shelf, ring apron, etc.
4. Rebuild hierarchy with layout and state, not decoration.
5. Reduce text to object names, mechanical labels, and one screen title.
6. Reuse existing game assets as objects, not as stickers inside web cards.
7. Validate with a screenshot and ask the Slay-the-Spire test again.

Do not respond to “make it AAA” by making surfaces shinier. That is the failure mode.

## Road To AEW Lesson

In Road to AEW, the useful improvement came only after removing:

- Metallic gold “premium” treatment.
- Pink/red gradient wash.
- Rounded boxes around every option.
- Nested modal > panel > card > badge structure.
- Decorative badge labels.

The better direction was:

- One flat game board.
- Dark material base.
- Thin dividers.
- Generated emblems as actual option objects.
- Selection as a left accent strip and subtle fill.
- Fewer gradients and fewer words.

The remaining palette issue was brownness, not structure. This distinction matters: once the structure became game-native, color could be iterated separately.
