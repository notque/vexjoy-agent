---
name: distinctive-frontend-design
description: "Context-driven aesthetic exploration with anti-cliche validation."
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
  - Skill
routing:
  triggers:
    - "frontend design"
    - "typography exploration"
    - "anti-cliche design"
    - "visual identity"
    - "design language"
  category: frontend
---

# Distinctive Frontend Design Skill

Systematic aesthetic exploration that produces contextual, validated design specifications. Every design choice flows from project context -- purpose, audience, emotion -- not from defaults or convenience. The workflow enforces exploration before implementation: you cannot write CSS until you have a validated aesthetic direction, typography selection, color palette, animation strategy, and atmospheric background.

Optional capabilities (off unless explicitly enabled by the user): design system generation, full WCAG accessibility auditing, animation performance profiling, dark mode variant generation.

## Instructions

### Vocabulary

These terms appear throughout the phases as hard rules. Read them once before Phase 1 so the rules do not feel like jargon when they gate your work.

- **Hero**: The first viewport section a visitor sees on page load. On landing pages it is the single largest decision in the design.
- **Full-bleed**: Spanning the entire viewport width with no max-width container, sidebar, or padding. A full-bleed hero touches both edges of the browser.
- **Narrative brief**: Three short sentences written before any code: visual thesis (mood and energy), content plan (named sections in order, one job each), interaction thesis (two or three motion ideas). See Phase 1 Step 4 for the full definition and examples.
- **Surface type**: Whether the page is a landing page (marketing, promotion, portfolio intro) or an app/dashboard (operator tools, data consoles, admin surfaces). The two types take different rule sets and must never be mixed.
- **Linear-style restraint**: A reference to the Linear project management tool's dashboard aesthetic. Calm surface hierarchy, strong typography, tight spacing, very few colors, no decorative ornament. The default posture for apps and dashboards.
- **Decorative-only motion**: Motion that exists purely for visual interest. It does not communicate state, guide attention, or reveal hidden content. Decorative-only motion fails the Phase 4 litmus and should be cut.
- **Brand override**: Any of these rules bend when the user supplies an explicit brand guide that contradicts the default (two accent colors, three typefaces, cards in hero for a specific identity reason). In that case, follow the brand guide and note the override in the specification document. Defaults are defaults, not overrides of stated client identity.

### Phase 1: Context Discovery

**Goal**: Understand the project deeply before making any aesthetic decisions.

**Step 1: Read and follow the repository CLAUDE.md**, then gather context by asking (adapt based on what is already known):

1. **Purpose**: What is this frontend for? (portfolio, SaaS product, creative showcase, documentation, landing page)
2. **Surface type**: Landing page or app/dashboard? Design rules diverge sharply. Landing pages lean on a full-bleed hero and narrative sequence. Apps and dashboards lean on Linear-style calm surfaces, strong typography, few colors, and dense readable information. Classify this up front because every downstream decision depends on it.
3. **Audience**: Who will use it? (developers, artists, enterprise users, general public, specific demographics)
4. **Emotion**: What should users feel? (professional, playful, sophisticated, rebellious, calm, energetic)
5. **Cultural context**: Any geographic, cultural, or thematic associations? (Japanese minimalism, industrial, retro, academic)
6. **Constraints**: Accessibility requirements, performance budgets, existing brand elements to preserve?
7. **Tech stack**: React, Vue, vanilla HTML/CSS, Next.js, framework preferences?
8. **Real content**: Gather the actual copy, real product name, real imagery, real product context. Placeholder text produces placeholder thinking. If final content is not yet available, secure at minimum the hero headline, product name, and the single promise you want the first viewport to convey.
9. **Previous projects**: Any recent frontend work? Variety across projects is mandatory, so check for choices that would overlap with recent work and avoid them.

**Step 2: Define 3-5 distinct aesthetic directions** using `references/color-inspirations.json` and `references/font-catalog.json` as starting points. Providing multiple directions prevents anchoring on a first instinct, which is the primary source of generic "AI slop" output.

Example directions and what they mean:
- **Neo-Brutalist Technical**: Bold typography, harsh contrasts, geometric precision, industrial textures
- **Warm Artisan**: Handcrafted feel, organic colors, subtle textures, serif elegance
- **Midnight Synthwave**: Dark backgrounds, neon accents, retro-futurism, gradient glows
- **Botanical Minimal**: Natural greens, generous whitespace, serif elegance, organic shapes
- **Arctic Technical**: Cool blues, sharp geometry, monospace accents, clean precision

**Step 3: Output** `aesthetic_direction.json` with chosen direction(s) and contextual justification. Every direction must link back to project purpose, audience, and emotion -- context-driven justification is what separates distinctive design from arbitrary choices. See `references/implementation-examples.md` for template.

**Step 4: Write the narrative brief**. Before any code or visual exploration, commit three sentences to the page:

1. **Visual thesis**: One sentence describing the mood and energy of the page. Example: "A calm, sun-warmed product page for a pottery studio where the ceramics themselves are the loudest element."
2. **Content plan**: Name the sections in order. For landing pages use Hero, Supporting imagery, Product detail, Social proof, Final CTA. For apps use the top navigation targets and what lives under each. Assign one job to each section, not two.
3. **Interaction thesis**: Two or three motion ideas. No more. Examples: "hero headline reveals on load with a 600ms stagger", "sticky product image follows the scroll through the detail section", "testimonials cross-fade on hover".

The narrative brief is the design brief. Every later phase is expected to be consistent with it. If a phase is producing choices that contradict the visual thesis or content plan, stop and revise the brief rather than drifting the design.

**Gate**: Aesthetic direction defined with contextual justification linking project purpose, audience, and emotion to chosen direction. Narrative brief from Step 4 written (visual thesis, content plan, interaction thesis). Do NOT proceed without both gate items passing.

**Skip-if-answered**: If the user's original request already provides the surface type, the product name, and a clear promise for the hero, treat those answers as already gathered. Do not interrogate the user for information they have already supplied. The context-gathering questions exist to close gaps, not to gate every request on ceremony.

### Phase 2: Typography Selection

**Goal**: Select distinctive, contextual font pairings that define the design's personality.

**Step 1: Load** `references/font-catalog.json`. All fonts in the catalog are pre-approved. The following fonts are banned because they are overused to the point of invisibility and signal generic output: Inter, Roboto, Arial, Helvetica, system fonts (e.g., `-apple-system, BlinkMacSystemFont, 'Segoe UI'`), Space Grotesk. Do not use them in selections or fallback stacks.

**Step 2: Select font pairing** using this process:
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

**Step 3: Validate**

```bash
# TODO: scripts/font_validator.py not yet implemented
# Manual alternative: check fonts against banned list
# Banned: Inter, Roboto, Arial, Helvetica, system fonts, Space Grotesk
```

Manually verify: no banned fonts in selection or fallback stacks (`sans-serif` alone counts as a banned system font), pairing not recently used, aesthetic match with direction.

**Step 4: Document** typography specification with font families, weights, usage roles, and rationale for each selection. Be specific -- include exact font names and weights, not vague descriptions. See `references/implementation-examples.md` for template.

**Gate**: Font validation passes (no banned fonts, no recent reuse, aesthetic match confirmed). Do NOT proceed until gate passes.

### Phase 3: Color Palette

**Goal**: Create a contextual palette with clear dominance hierarchy, not a random collection of colors.

**Step 1: Research** cultural/contextual inspiration using `references/color-inspirations.json`. Inspiration sources include:
- **Cultural aesthetics**: Japanese indigo, Scandinavian earth tones, Mediterranean warmth
- **IDE themes**: Dracula, Nord, Gruvbox, Tokyo Night, Catppuccin
- **Natural phenomena**: Desert sunsets, deep ocean, autumn forests, arctic twilight
- **Historical periods**: Art Deco, Mid-century modern, Victorian industrial
- **Artistic movements**: Bauhaus, De Stijl, Impressionism

Select an inspiration source that resonates with the project context from Phase 1. The palette must trace back to that context -- convenience or personal preference is not a valid reason for a color choice.

**Step 2: Build palette** with strict dominance structure:
- **Dominant** (60-70%): Base background and major surfaces -- this sets the mood
- **Secondary** (20-30%): Supporting elements, containers, navigation -- provides structure
- **Accent** (5-10%): High-impact moments, CTAs, highlights -- demands attention sparingly
- **Functional**: Success, warning, error, info states -- consistent across all designs

Colors distributed evenly without a clear dominant create visual chaos. The 60/30/10 ratio is non-negotiable because without it, no coherent aesthetic emerges.

**One accent color, not two.** The accent slot is for a single hue. If a second accent seems necessary, it is almost always either (a) a functional color (error/success/warning/info, which belongs in the Functional group), or (b) a weight variation of the dominant or secondary. Two competing accents dilute the hierarchy and signal a page that does not know what it wants the user to look at.

**Step 3: Check against anti-patterns** in `references/anti-patterns.json`:
- No purple (#8B5CF6, #A855F7) as accent on white background -- the most cliched color scheme in modern web design, signaling generic SaaS template
- No evenly distributed colors without clear dominance
- No generic blue (#3B82F6) as primary on white
- No pastels without saturation variation
- No pure black (#000000) or pure white (#FFFFFF) as dominant color

**Step 4: Validate**

```bash
# TODO: scripts/palette_analyzer.py not yet implemented
# Manual alternative: check palette against anti-patterns in references/anti-patterns.json
```

Manually verify: no cliche patterns, clear 60/30/10 dominance ratio, sufficient contrast for accessibility. Report results with specific hex values rather than describing colors abstractly.

**Gate**: Palette passes cliche detection and demonstrates clear 60/30/10 dominance ratio. Do NOT proceed until gate passes.

### Phase 4: Animation Strategy

**Goal**: Design choreography for high-impact moments only. Restraint is a feature -- animating everything dilutes impact and signals lack of intentionality.

**The 2-to-3 rule**. Ship two or three intentional motions per page, not ten. Motion creates presence and hierarchy. Too much motion creates noise. The interaction thesis from Phase 1 should already name the three slots; this phase choreographs them in detail.

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

**Step 3: Define easing curves and timing** for the design:

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

**Gate**: At least one high-impact moment has a fully defined choreography including element order, easing curves, and timing values. Do NOT proceed without this.

### Phase 5: Hero Composition, Background & Atmosphere

**Goal**: Construct the first viewport as a single composition, then add depth and mood through layered effects. Flat solid-color backgrounds fail this phase because they produce no atmospheric depth -- every surface needs at least two layers.

**Step 0: Hero composition rules** (landing pages). The first viewport must read as one composition, not a grid of parts. Apply these hard rules before any background work:

- **One composition**. The first screen the user sees must read as a single unified image. If a new user cannot describe the hero in one sentence, it is not a composition yet.
- **No cards in the hero. Ever.** The hero is where the product speaks directly. Putting the hero content inside a rounded card with a drop shadow instantly converts a landing page into a generic dashboard tile.
- **Full-bleed hero by default**. The hero spans the full viewport width on landing pages. No content-width containers, no max-width wrapping, no sidebars stealing from the hero.
- **Brand-first composition**. On branded pages, the product name must be set at hero scale in the display typeface from Phase 2. The product name is the loudest thing in the first viewport.
- **One job per section**. The hero has one purpose, one takeaway, one CTA intent. If the hero is promising two things, cut one.
- **Hero image litmus**. Remove the hero image mentally. Does the page still work without it? If yes, the image was too weak and needs to be replaced, not decorated.

Apps and dashboards follow different rules; see "App vs Landing Page Rules" below.

**Step 1: Choose technique** from `references/background-techniques.md` based on aesthetic direction:
- **Layered radial gradients**: Atmospheric depth with soft colored glows (sophisticated, landing pages)
- **Geometric patterns**: Grid lines, dots, diagonal stripes (technical precision, developer tools)
- **Noise textures**: Grain overlays for tactile organic feel (portfolios, artisan brands)
- **Contextual effects**: IDE scanlines, paper texture, cursor spotlight (thematic immersion)
- **Multi-layer composition**: Combine 2-3 techniques for rich atmospheric depth

**Step 2: Implement** background CSS that matches the aesthetic direction. A good atmospheric background combines at minimum:
- Base surface color (never pure white or pure black)
- Gradient layer for depth and focus direction
- Pattern or texture layer for character

**Step 3: Verify** background does not compromise text readability. Check contrast ratios against WCAG AA minimums.

**Gate**: Background uses at least 2 layers creating visual depth and atmospheric mood. Solid single-color backgrounds fail this gate.

### App vs Landing Page Rules

The surface type classified in Phase 1 determines which rule set governs layout. Mixing the two rule sets is the fastest way to produce a page that feels generic in one direction and cluttered in the other.

**Landing page rules** (marketing, product promotion, portfolio intro):
- Full-bleed hero, single composition, brand-first scale
- Narrative section sequence: Hero → Supporting imagery → Product detail → Social proof → Final CTA
- Each section does one job; cut the section if it cannot decide on one takeaway
- Atmospheric backgrounds encouraged (gradients, textures, layered depth)
- Motion used to reveal and orchestrate the narrative

**App and dashboard rules** (operator tools, data consoles, admin surfaces):
- Default to Linear-style restraint: calm surface hierarchy, strong typography, tight spacing
- Few colors. Usually one accent, one or two functional hues, the rest is neutral
- Dense but readable information. Operators scan headings, labels, and numbers
- Cards only when the card is the interaction (a selectable item, a sortable row, a drag target). No cards for purely visual grouping
- Avoid dashboard-card mosaics where every region is wrapped in a bordered box
- Avoid decorative gradients, thick borders on every region, and multiple competing accent colors
- Motion is minimal and functional: a focus ring, a row expand, a drawer slide. Not ambient flourish

**App litmus test**. If an operator scans only the headings, labels, and numbers on the page, can they understand what the page is showing them immediately? If they need to read paragraphs of body copy or decode ornamental UI to figure out what they are looking at, the page is failing its job.

**Landing litmus test**. If the user spends three seconds on the first viewport, can they name the product and describe the promise in one sentence? If not, the hero is failing its job regardless of how polished it looks.

### Phase 6: Validation & Scoring

**Goal**: Objective quality assessment before any finalization. Validation must run before delivering specifications -- skipping it means flaws compound through every downstream implementation decision.

**Step 1: Run comprehensive validation**

```bash
# TODO: scripts/validate_design.py not yet implemented
# Manual alternative: review each validation check listed below against design choices
```

**Step 2: Review** validation report. The report checks:
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

**Step 3: Address issues** -- if overall score < 80:
1. Review each failed check in the report
2. Iterate on the specific problematic area (return to that phase)
3. Re-run validation after each fix
4. Do NOT proceed to specification output until score >= 80

**Gate**: Validation score >= 80 (Grade B or higher). Do NOT deliver specification output until this gate passes.

### Phase 7: Design Specification Output

**Goal**: Deliver a complete, implementable design specification. Only implement what was directly requested -- focus on distinctive aesthetics, not unnecessary abstractions or design system scaffolding unless the user explicitly asked for it.

**Step 1: Generate CSS custom properties** (design tokens) covering typography, colors, spacing, shadows, and animation values. Reference `references/implementation-examples.md` for comprehensive token template.

**Step 2: Create base styles** that apply tokens to:
- Typography hierarchy (display, heading, body, mono)
- Atmospheric background (layered gradients/patterns)
- Layout reset and defaults

**Step 3: Document design specification** as a structured document covering:
- Aesthetic direction and inspiration
- Typography system with font families, weights, and usage roles
- Color palette with dominance structure and hex values
- Animation strategy with timing specifications
- Background technique and implementation
- Validation score and grade

**Step 4: If implementation is requested**, provide framework-specific starter code. Reference `references/implementation-examples.md` for React+Tailwind config, HTML+CSS templates, and design system templates.

**Step 5: Clean up** temporary exploration artifacts (intermediate JSON files, draft palettes). Keep only the final specification and validation report.

**Gate**: Design specification document delivered with all sections complete and validation score included.

### Examples

#### Example 1: New Landing Page
User says: "Create a distinctive design for a developer tool landing page"
Actions:
1. Gather context: developer audience, technical but approachable emotion (PHASE 1)
2. Define directions: Neo-Brutalist Technical vs. Arctic Technical (PHASE 1)
3. Select fonts: geometric display + readable serif body from catalog (PHASE 2)
4. Build palette: warm concrete dominant, charcoal secondary, high-voltage yellow accent (PHASE 3)
5. Plan hero staggered reveal animation (PHASE 4)
6. Create layered gradient + grid background (PHASE 5)
7. Validate: score >= 80, no anti-patterns (PHASE 6)
8. Output design specification with CSS tokens (PHASE 7)
Result: Contextual, validated design specification ready for implementation

#### Example 2: Design Audit
User says: "This site looks too generic, review it for AI slop"
Actions:
1. Read existing CSS/design files to inventory current choices (PHASE 1)
2. Check fonts against banned list and `references/anti-patterns.json` (PHASE 2)
3. Analyze color palette for cliches and dominance issues (PHASE 3)
4. Review animation usage (too much or too little) (PHASE 4)
5. Evaluate background depth (flat solid colors?) (PHASE 5)
6. Run validation to score current design (PHASE 6)
7. Deliver report with specific replacement recommendations (PHASE 7)
Result: Actionable audit with specific fixes for each detected issue

## Reference Material

### Design Catalogs

These reference files contain the curated domain knowledge that drives design decisions:

- `${CLAUDE_SKILL_DIR}/references/font-catalog.json`: Curated fonts by aesthetic category (banned fonts excluded)
- `${CLAUDE_SKILL_DIR}/references/color-inspirations.json`: Cultural/contextual color palette sources
- `${CLAUDE_SKILL_DIR}/references/animation-patterns.md`: High-impact animation choreography patterns with CSS and React examples
- `${CLAUDE_SKILL_DIR}/references/background-techniques.md`: Atmospheric background creation methods with code snippets
- `${CLAUDE_SKILL_DIR}/references/anti-patterns.json`: Banned fonts, cliche colors, layout and component cliches
- `${CLAUDE_SKILL_DIR}/references/implementation-examples.md`: CSS tokens, base styles, framework templates, specification document templates
- `${CLAUDE_SKILL_DIR}/references/project-history.json`: Aesthetic choices across projects (auto-generated by validation)

## Error Handling

### Error: "Validation failed -- banned font detected"
Cause: Selected font is on the banned list (Inter, Roboto, Arial, Helvetica, system fonts, Space Grotesk) or appears in a CSS fallback stack
Solution:
1. Select alternative from `references/font-catalog.json` -- all catalog fonts are pre-approved
2. Verify fallback stacks do not include banned fonts (e.g., `sans-serif` alone is banned)
3. Re-run font validator to confirm resolution

### Error: "Cliche color scheme detected"
Cause: Palette analyzer flags purple gradient on white, generic blue primary, or evenly distributed colors
Solution:
1. Review `references/color-inspirations.json` for culturally-grounded alternatives
2. Ensure clear 60/30/10 dominance ratio -- if colors are evenly split, commit to a dominant
3. Choose inspiration from project context (audience, purpose, emotion), not convenience
4. Re-run palette analyzer to confirm resolution

### Error: "Low distinctiveness score (< 80)"
Cause: Design lacks personality, shows timid commitment to aesthetic direction, or has multiple marginal issues
Solution:
1. Review validation report for the specific weak areas
2. Strengthen contextual elements: add custom textures, commit fully to the aesthetic direction
3. Check if font + color + background form a cohesive story or feel disconnected
4. Iterate and re-validate -- max 3 attempts before reconsidering the aesthetic direction

## References

- `${CLAUDE_SKILL_DIR}/references/font-catalog.json`
- `${CLAUDE_SKILL_DIR}/references/color-inspirations.json`
- `${CLAUDE_SKILL_DIR}/references/animation-patterns.md`
- `${CLAUDE_SKILL_DIR}/references/background-techniques.md`
- `${CLAUDE_SKILL_DIR}/references/anti-patterns.json`
- `${CLAUDE_SKILL_DIR}/references/implementation-examples.md`
- `${CLAUDE_SKILL_DIR}/references/project-history.json`
