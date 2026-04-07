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

### Phase 1: Context Discovery

**Goal**: Understand the project deeply before making any aesthetic decisions.

**Step 1: Read and follow the repository CLAUDE.md**, then gather context by asking (adapt based on what is already known):

1. **Purpose**: What is this frontend for? (portfolio, SaaS product, creative showcase, documentation, landing page)
2. **Audience**: Who will use it? (developers, artists, enterprise users, general public, specific demographics)
3. **Emotion**: What should users feel? (professional, playful, sophisticated, rebellious, calm, energetic)
4. **Cultural context**: Any geographic, cultural, or thematic associations? (Japanese minimalism, industrial, retro, academic)
5. **Constraints**: Accessibility requirements, performance budgets, existing brand elements to preserve?
6. **Tech stack**: React, Vue, vanilla HTML/CSS, Next.js, framework preferences?
7. **Previous projects**: Any recent frontend work? (to avoid reusing the same aesthetic choices -- variety across projects is mandatory)

**Step 2: Define 3-5 distinct aesthetic directions** using `references/color-inspirations.json` and `references/font-catalog.json` as starting points. Providing multiple directions prevents anchoring on a first instinct, which is the primary source of generic "AI slop" output.

Example directions and what they mean:
- **Neo-Brutalist Technical**: Bold typography, harsh contrasts, geometric precision, industrial textures
- **Warm Artisan**: Handcrafted feel, organic colors, subtle textures, serif elegance
- **Midnight Synthwave**: Dark backgrounds, neon accents, retro-futurism, gradient glows
- **Botanical Minimal**: Natural greens, generous whitespace, serif elegance, organic shapes
- **Arctic Technical**: Cool blues, sharp geometry, monospace accents, clean precision

**Step 3: Output** `aesthetic_direction.json` with chosen direction(s) and contextual justification. Every direction must link back to project purpose, audience, and emotion -- context-driven justification is what separates distinctive design from arbitrary choices. See `references/implementation-examples.md` for template.

**Gate**: Aesthetic direction defined with contextual justification linking project purpose, audience, and emotion to chosen direction. Do NOT proceed without this gate passing.

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

**Step 1: Identify high-impact moments** worth investing animation effort:
- Initial page load (hero section reveal)
- Major state transitions (empty to filled, loading to success)
- Feature showcases (pricing reveal, testimonial carousel)
- User achievements (form submission success, milestone reached)

Moments NOT worth animating (resist the urge):
- Every hover state on every element
- Every button click feedback
- Low-importance UI elements (footers, metadata)
- Background elements that distract from content

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

### Phase 5: Background & Atmosphere

**Goal**: Create depth and mood through layered effects. Flat solid-color backgrounds fail this phase because they produce no atmospheric depth -- every surface needs at least two layers.

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
- Color dominance ratio meets 60/30/10 target
- Sufficient contrast ratios (WCAG AA minimum)
- Animation strategy is defined (not missing)
- Background atmosphere is present (not flat)

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
