---
name: distinctive-frontend-design
description: |
  Context-driven aesthetic exploration with anti-cliche validation: typography,
  color, animation, atmosphere. Use when starting a frontend needing distinctive
  aesthetics, refreshing generic designs, or auditing for "AI slop" patterns.
  Use for "distinctive frontend", "unique aesthetics", "avoid generic design",
  "creative frontend". Do NOT use for quick prototypes, strict brand compliance,
  backend projects, or data visualization.
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
---

# Distinctive Frontend Design Skill

## Operator Context

This skill operates as an operator for frontend design workflows, configuring Claude's behavior for creative aesthetic development that systematically avoids generic outputs. It implements the **Exploration-First** architectural pattern -- full context analysis and aesthetic exploration before any implementation.

### Hardcoded Behaviors (Always Apply)

- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before execution
- **Over-Engineering Prevention**: Only implement what is directly requested; keep solutions focused on distinctive aesthetics, not unnecessary abstractions or design system scaffolding
- **Exploration-First Workflow**: ALWAYS complete aesthetic exploration (Phase 1) before any implementation; never jump to code with first-instinct choices
- **Anti-Pattern Prevention**: NEVER use banned fonts (Inter, Roboto, Arial, Helvetica, system fonts, Space Grotesk), purple gradients on white, or other cliches from `references/anti-patterns.json`
- **Context-Driven Decisions**: ALL design choices must be justified by project context, not convenience or defaults
- **Validation Required**: MUST run validation scripts before finalizing design specifications
- **Variety Enforcement**: NEVER reuse the same aesthetic choices across different projects; check project history

### Default Behaviors (ON unless disabled)

- **Concise Reporting**: Show validation results rather than describing them; be specific about aesthetic choices with hex values and font names
- **Temporary File Cleanup**: Remove exploration artifacts at completion; keep only final specifications and validation reports
- **Diverse Options**: Provide 3-5 distinct aesthetic directions during exploration phase
- **Cultural Research**: Research and incorporate cultural/thematic inspiration relevant to project context
- **Typography Excellence**: Prioritize beautiful, unexpected font combinations from curated catalog
- **Animation Orchestration**: Plan choreographed sequences for high-impact moments only; resist animating everything
- **Atmospheric Backgrounds**: Create depth through layered effects; never use flat solid colors

### Optional Behaviors (OFF unless enabled)

- **Design System Generation**: Create comprehensive design tokens and component library
- **Accessibility Auditing**: Full WCAG compliance checking beyond basic contrast
- **Performance Profiling**: Detailed animation performance analysis and optimization
- **Dark Mode Variants**: Automatic dark theme generation with adjusted glow/pattern opacities

## What This Skill CAN Do

- Guide systematic aesthetic exploration before implementation
- Validate design choices against anti-pattern database
- Generate diverse font recommendations by aesthetic category
- Create context-driven color palettes from cultural/thematic sources
- Plan high-impact animation choreography with easing curves
- Design atmospheric backgrounds with layered gradient/pattern/texture effects
- Audit existing designs for generic patterns and "AI slop" signals
- Provide concrete CSS/React/Tailwind implementation guidance
- Score designs on distinctiveness metrics with actionable feedback

## What This Skill CANNOT Do

- Generate pixel-perfect mockups (provides specifications and code, not visual design files)
- Replace human creativity (guides and validates, but requires creative direction from user)
- Guarantee uniqueness against all existing designs on the internet
- Auto-generate complete design systems (focuses on aesthetic distinctiveness, not comprehensive systems)
- Handle backend, API, or data visualization concerns
- Validate against specific brand guidelines without those guidelines provided

---

## Instructions

### Phase 1: Context Discovery

**Goal**: Understand the project deeply before making any aesthetic decisions.

**Step 1: Gather context** by asking (adapt based on what is already known):

1. **Purpose**: What is this frontend for? (portfolio, SaaS product, creative showcase, documentation, landing page)
2. **Audience**: Who will use it? (developers, artists, enterprise users, general public, specific demographics)
3. **Emotion**: What should users feel? (professional, playful, sophisticated, rebellious, calm, energetic)
4. **Cultural context**: Any geographic, cultural, or thematic associations? (Japanese minimalism, industrial, retro, academic)
5. **Constraints**: Accessibility requirements, performance budgets, existing brand elements to preserve?
6. **Tech stack**: React, Vue, vanilla HTML/CSS, Next.js, framework preferences?
7. **Previous projects**: Any recent frontend work? (to ensure variety across projects)

**Step 2: Define 2-3 aesthetic directions** using `references/color-inspirations.json` and `references/font-catalog.json` as starting points.

Example directions and what they mean:
- **Neo-Brutalist Technical**: Bold typography, harsh contrasts, geometric precision, industrial textures
- **Warm Artisan**: Handcrafted feel, organic colors, subtle textures, serif elegance
- **Midnight Synthwave**: Dark backgrounds, neon accents, retro-futurism, gradient glows
- **Botanical Minimal**: Natural greens, generous whitespace, serif elegance, organic shapes
- **Arctic Technical**: Cool blues, sharp geometry, monospace accents, clean precision

**Step 3: Output** `aesthetic_direction.json` with chosen direction(s) and contextual justification. See `references/implementation-examples.md` for template.

**Gate**: Aesthetic direction defined with contextual justification linking project purpose, audience, and emotion to chosen direction. Do NOT proceed without this gate passing.

### Phase 2: Typography Selection

**Goal**: Select distinctive, contextual font pairings that define the design's personality.

**Step 1: Load** `references/font-catalog.json`. All fonts in catalog are pre-approved; banned fonts (Inter, Roboto, Arial, Helvetica, system fonts, Space Grotesk) are excluded from catalog.

**Step 2: Select font pairing** using this process:
1. Identify 3-5 candidate fonts from the appropriate aesthetic category
2. Eliminate any that feel "obvious" or overused for this context
3. Test combinations: Display font + Body font, or single font family with weight variation
4. Verify the pairing creates clear visual hierarchy
5. Check against project history for variety

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

Manually verify: no banned fonts in selection, pairing not recently used, aesthetic match with direction.

**Step 4: Document** typography specification with font families, weights, usage roles, and rationale for each selection. See `references/implementation-examples.md` for template.

**Gate**: Font validation passes (no banned fonts, no recent reuse, aesthetic match confirmed). Do NOT proceed until gate passes.

### Phase 3: Color Palette

**Goal**: Create a contextual palette with clear dominance hierarchy, not a random collection of colors.

**Step 1: Research** cultural/contextual inspiration using `references/color-inspirations.json`. Inspiration sources include:
- **Cultural aesthetics**: Japanese indigo, Scandinavian earth tones, Mediterranean warmth
- **IDE themes**: Dracula, Nord, Gruvbox, Tokyo Night, Catppuccin
- **Natural phenomena**: Desert sunsets, deep ocean, autumn forests, arctic twilight
- **Historical periods**: Art Deco, Mid-century modern, Victorian industrial
- **Artistic movements**: Bauhaus, De Stijl, Impressionism

Select an inspiration source that resonates with the project context from Phase 1.

**Step 2: Build palette** with strict dominance structure:
- **Dominant** (60-70%): Base background and major surfaces -- this sets the mood
- **Secondary** (20-30%): Supporting elements, containers, navigation -- provides structure
- **Accent** (5-10%): High-impact moments, CTAs, highlights -- demands attention sparingly
- **Functional**: Success, warning, error, info states -- consistent across all designs

**Step 3: Check against anti-patterns** in `references/anti-patterns.json`:
- No purple (#8B5CF6, #A855F7) as accent on white background
- No evenly distributed colors without clear dominance
- No generic blue (#3B82F6) as primary on white
- No pastels without saturation variation
- No pure black (#000000) or pure white (#FFFFFF) as dominant color

**Step 4: Validate**

```bash
# TODO: scripts/palette_analyzer.py not yet implemented
# Manual alternative: check palette against anti-patterns in references/anti-patterns.json
```

Manually verify: no cliche patterns (purple on white, generic blue), clear 60/30/10 dominance ratio, sufficient contrast for accessibility.

**Gate**: Palette passes cliche detection and demonstrates clear 60/30/10 dominance ratio. Do NOT proceed until gate passes.

### Phase 4: Animation Strategy

**Goal**: Design choreography for high-impact moments only. Restraint is a feature.

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

**Goal**: Create depth and mood through layered effects. Never use flat solid colors as backgrounds.

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

**Goal**: Objective quality assessment through validation scripts before any finalization.

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

**Goal**: Deliver a complete, implementable design specification.

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

**Gate**: Design specification document delivered with all sections complete and validation score included.

---

## Examples

### Example 1: New Landing Page
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

### Example 2: Design Audit
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

---

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

---

## Anti-Patterns

### Anti-Pattern 1: Skipping Aesthetic Exploration
**What it looks like**: Jumping to CSS/React implementation with first-instinct font and color choices
**Why wrong**: Produces generic, unconsidered design with no contextual justification; most "AI slop" originates here
**Do instead**: Complete Phase 1 context discovery and direction selection before touching implementation

### Anti-Pattern 2: Using Banned Fonts
**What it looks like**: `font-family: 'Inter', sans-serif` or `font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI'`
**Why wrong**: Overused to the point of invisibility; instant "AI slop" aesthetic signal; fails validation immediately
**Do instead**: Select from `references/font-catalog.json`, run font validator, choose unexpected pairings

### Anti-Pattern 3: Purple Gradients on White
**What it looks like**: `background: linear-gradient(135deg, #667eea, #764ba2)` with white surfaces and purple accents
**Why wrong**: Most cliched color scheme in modern web design; signals generic SaaS template; no contextual justification possible
**Do instead**: Research cultural/contextual color inspiration, create palette with 60/30/10 dominance structure

### Anti-Pattern 4: Evenly Distributed Colors
**What it looks like**: Five accent colors used in roughly equal proportion across the design
**Why wrong**: Creates visual chaos without hierarchy; no dominant aesthetic emerges; looks like color picker experimentation
**Do instead**: Follow 60/30/10 rule strictly (dominant/secondary/accent), validate dominance ratio

### Anti-Pattern 5: Implementing Without Validation
**What it looks like**: Writing CSS/React implementation without ever running design validation
**Why wrong**: May build entire frontend on flawed design foundations; wastes time on rework; no objective quality measure
**Do instead**: Run validation in Phase 6, ensure score >= 80 before proceeding to specification output

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "Inter is clean and readable" | Clean = invisible; readable != distinctive | Select from curated catalog |
| "Purple gradient looks modern" | Modern = cliched; every SaaS uses this | Research contextual inspiration |
| "I'll validate later" | Later = never; flaws compound through phases | Validate at each phase gate |
| "Simple solid background is fine" | Solid = flat; depth creates atmosphere | Add at least 2 background layers |
| "Same fonts worked last time" | Worked != distinctive; variety is required | Check project history, choose new |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/font-catalog.json`: Curated fonts by aesthetic category (banned fonts excluded)
- `${CLAUDE_SKILL_DIR}/references/color-inspirations.json`: Cultural/contextual color palette sources
- `${CLAUDE_SKILL_DIR}/references/animation-patterns.md`: High-impact animation choreography patterns with CSS and React examples
- `${CLAUDE_SKILL_DIR}/references/background-techniques.md`: Atmospheric background creation methods with code snippets
- `${CLAUDE_SKILL_DIR}/references/anti-patterns.json`: Banned fonts, cliche colors, layout and component cliches
- `${CLAUDE_SKILL_DIR}/references/implementation-examples.md`: CSS tokens, base styles, framework templates, specification document templates
- `${CLAUDE_SKILL_DIR}/references/project-history.json`: Aesthetic choices across projects (auto-generated by validation)
