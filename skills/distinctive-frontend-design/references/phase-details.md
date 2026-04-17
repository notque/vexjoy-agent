## Phase Details

### Phase 1: Aesthetic Direction Examples

Example directions and what they mean:
- **Neo-Brutalist Technical**: Bold typography, harsh contrasts, geometric precision, industrial textures
- **Warm Artisan**: Handcrafted feel, organic colors, subtle textures, serif elegance
- **Midnight Synthwave**: Dark backgrounds, neon accents, retro-futurism, gradient glows
- **Botanical Minimal**: Natural greens, generous whitespace, serif elegance, organic shapes
- **Arctic Technical**: Cool blues, sharp geometry, monospace accents, clean precision

### Phase 1: Narrative Brief Detail

Before any code or visual exploration, commit three sentences to the page:

1. **Visual thesis**: One sentence describing the mood and energy of the page. Example: "A calm, sun-warmed product page for a pottery studio where the ceramics themselves are the loudest element."
2. **Content plan**: Name the sections in order. For landing pages use Hero, Supporting imagery, Product detail, Social proof, Final CTA. For apps use the top navigation targets and what lives under each. Assign one job to each section, not two.
3. **Interaction thesis**: Two or three motion ideas. No more. Examples: "hero headline reveals on load with a 600ms stagger", "sticky product image follows the scroll through the detail section", "testimonials cross-fade on hover".

The narrative brief is the design brief. Every later phase is expected to be consistent with it. If a phase is producing choices that contradict the visual thesis or content plan, stop and revise the brief rather than drifting the design.

### Phase 2: Selection Process Detail

Select font pairing using this process:
1. Identify 3-5 candidate fonts from the appropriate aesthetic category
2. Eliminate any that feel "obvious" or overused for this context -- resist the first instinct and explore deeper in the catalog, because beautiful unexpected combinations are the goal
3. Test combinations: Display font + Body font, or single font family with weight variation
4. Verify the pairing creates clear visual hierarchy
5. Check against project history to confirm you are not reusing recent choices

Selection criteria:
- Matches aesthetic direction from Phase 1
- Creates clear hierarchy (Display/Heading + Body, or single font with weight variation)
- Is unexpected -- avoid first instinct, explore deeper in the catalog
- Has not been used in recent projects
- **Two typefaces maximum**. If the pairing needs a third family to feel complete, something upstream is wrong. A single family with weight and size variation beats three families fighting each other.
- **Brand first on branded pages**. When the page is promoting a named product or brand, the product name must be set at hero level in the display face. The product name is not a label, it is the loudest element in the first viewport.

### Phase 2: Font Validation Block

```bash
# TODO: scripts/font_validator.py not yet implemented
# Manual alternative: check fonts against banned list
# Banned: Inter, Roboto, Arial, Helvetica, system fonts, Space Grotesk
```

Manually verify: no banned fonts in selection or fallback stacks (`sans-serif` alone counts as a banned system font), pairing not recently used, aesthetic match with direction.

### Phase 3: Inspiration Sources

Inspiration sources include:
- **Cultural aesthetics**: Japanese indigo, Scandinavian earth tones, Mediterranean warmth
- **IDE themes**: Dracula, Nord, Gruvbox, Tokyo Night, Catppuccin
- **Natural phenomena**: Desert sunsets, deep ocean, autumn forests, arctic twilight
- **Historical periods**: Art Deco, Mid-century modern, Victorian industrial
- **Artistic movements**: Bauhaus, De Stijl, Impressionism

Select an inspiration source that resonates with the project context from Phase 1. The palette must trace back to that context -- convenience or personal preference is not a valid reason for a color choice.

### Phase 3: Anti-Pattern Checks

Check against anti-patterns in `references/anti-patterns.json`:
- No purple (#8B5CF6, #A855F7) as accent on white background -- the most cliched color scheme in modern web design, signaling generic SaaS template
- No evenly distributed colors without clear dominance
- No generic blue (#3B82F6) as primary on white
- No pastels without saturation variation
- No pure black (#000000) or pure white (#FFFFFF) as dominant color

### Phase 3: Palette Validation Block

```bash
# TODO: scripts/palette_analyzer.py not yet implemented
# Manual alternative: check palette against anti-patterns in references/anti-patterns.json
```

Manually verify: no cliche patterns, clear 60/30/10 dominance ratio, sufficient contrast for accessibility. Report results with specific hex values rather than describing colors abstractly.

### Phase 4: Three Motion Slots Detail

**Step 1: Fill the three motion slots**. Pick one from each slot, not five from slot A:

1. **Entrance slot**: One entrance sequence in the hero. The hero headline, the hero media, or a staggered reveal of both. Happens once, on load.
2. **Scroll slot**: One scroll-linked or sticky effect. A sticky product image following the scroll, a parallax depth layer, a reveal-on-scroll sequence for the supporting sections.
3. **Interaction slot**: One hover, reveal, or layout transition. A hover effect on the primary CTA, a card that expands on click, a tab that slides under the label.

If a proposed motion does not fit into one of these three slots, it is extra noise and should be cut.

**Moments NOT worth animating** (resist the urge):
- Every hover state on every element
- Every button click feedback
- Low-importance UI elements (footers, metadata)
- Background elements that distract from content

**Decorative-only litmus**. For every motion in the design, ask: does removing this motion change what the user understands about the page? If the answer is no, the motion is decorative and should be cut. Motion is a tool for establishing hierarchy and presence, not a tool for making the page feel "alive".

**Recommended stack**: Framer Motion for React, CSS transitions for simple hover/focus. Do not mix five animation libraries on one page.

**Step 2: Design choreography** for each identified moment. Reference `references/animation-patterns.md` for battle-tested patterns:
- Orchestrated page load with staggered reveal
- State transition choreography (empty to populated)
- Loading-to-success celebration sequences
- Scroll-triggered section reveals
- Interactive hover effects (use sparingly)

### Phase 4: Easing and Timing Tables

Easing by purpose:
- **Entrances**: `cubic-bezier(0.22, 1, 0.36, 1)` -- smooth deceleration into view
- **Exits**: `cubic-bezier(0.4, 0, 1, 1)` -- smooth acceleration out of view
- **Interactions**: `cubic-bezier(0.4, 0, 0.2, 1)` -- Material Design standard for hover/click
- **Elastic**: `cubic-bezier(0.68, -0.55, 0.265, 1.55)` -- playful overshoot for celebrations

Duration by scope:
- Micro-interactions (hover, focus): 150-250ms
- Component transitions (card, modal): 300-500ms
- Page transitions (hero load, section): 500-800ms
- Stagger delay between elements: 100-200ms
- Never exceed 1000ms for any UI animation

### Phase 5: Hero Composition Rules (landing pages)

The first viewport must read as one composition, not a grid of parts. Apply these hard rules before any background work:

- **One composition**. The first screen the user sees must read as a single unified image. If a new user cannot describe the hero in one sentence, it is not a composition yet.
- **No cards in the hero. Ever.** The hero is where the product speaks directly. Putting the hero content inside a rounded card with a drop shadow instantly converts a landing page into a generic dashboard tile.
- **Full-bleed hero by default**. The hero spans the full viewport width on landing pages. No content-width containers, no max-width wrapping, no sidebars stealing from the hero.
- **Brand-first composition**. On branded pages, the product name must be set at hero scale in the display typeface from Phase 2. The product name is the loudest thing in the first viewport.
- **One job per section**. The hero has one purpose, one takeaway, one CTA intent. If the hero is promising two things, cut one.
- **Hero image litmus**. Remove the hero image mentally. Does the page still work without it? If yes, the image was too weak and needs to be replaced, not decorated.

Apps and dashboards follow different rules; see `references/app-vs-landing-rules.md`.

### Phase 5: Background Techniques

Choose technique from `references/background-techniques.md` based on aesthetic direction:
- **Layered radial gradients**: Atmospheric depth with soft colored glows (sophisticated, landing pages)
- **Geometric patterns**: Grid lines, dots, diagonal stripes (technical precision, developer tools)
- **Noise textures**: Grain overlays for tactile organic feel (portfolios, artisan brands)
- **Contextual effects**: IDE scanlines, paper texture, cursor spotlight (thematic immersion)
- **Multi-layer composition**: Combine 2-3 techniques for rich atmospheric depth

A good atmospheric background combines at minimum:
- Base surface color (never pure white or pure black)
- Gradient layer for depth and focus direction
- Pattern or texture layer for character

### Phase 6: Validation Report Checks

The report checks:
- No banned fonts in selection or fallback stacks
- No cliche color schemes detected
- Font pairing uniqueness versus recent projects
- Two typefaces maximum in the selected pairing
- Color dominance ratio meets 60/30/10 target
- Exactly one accent color in the accent slot (functional colors do not count)
- Sufficient contrast ratios (WCAG AA minimum)
- Animation strategy is defined (not missing)
- Motion count fits the 2-to-3 slot rule (entrance, scroll, interaction)
- Every motion passes the decorative-only litmus
- Background atmosphere is present (not flat)
- Narrative brief is present (visual thesis, content plan, interaction thesis)
- Surface type classified as landing page or app, with matching rule set applied
- For landing pages: hero reads as one composition, no cards in hero, full-bleed hero confirmed
- For apps: Linear-style restraint applied, no decorative gradients or card mosaics
