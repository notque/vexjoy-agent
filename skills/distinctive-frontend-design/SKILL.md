---
name: distinctive-frontend-design
description: "Context-driven aesthetic exploration with anti-cliche validation."
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
  pairs_with:
    - threejs-builder
    - webgl-card-effects
    - frontend-slides
---

# Distinctive Frontend Design Skill

Systematic aesthetic exploration producing contextual, validated design specifications. Every design choice flows from project context -- purpose, audience, emotion -- not defaults. The workflow enforces exploration before implementation: no CSS until you have a validated aesthetic direction, typography, color palette, animation strategy, and atmospheric background.

Optional capabilities (off unless user enables): design system generation, full WCAG auditing, animation performance profiling, dark mode variants.

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| implementation patterns | `animation-patterns.md` | Loads detailed guidance from `animation-patterns.md`. |
| tasks related to this reference | `app-vs-landing-rules.md` | Loads detailed guidance from `app-vs-landing-rules.md`. |
| tasks related to this reference | `background-techniques.md` | Loads detailed guidance from `background-techniques.md`. |
| implementation patterns | `css-audit-patterns.md` | Loads detailed guidance from `css-audit-patterns.md`. |
| errors, error handling | `error-handling.md` | Loads detailed guidance from `error-handling.md`. |
| example-driven tasks | `examples.md` | Loads detailed guidance from `examples.md`. |
| game UI, AAA game, polished game, Steam game, roguelike UI, Slay the Spire | `game-ui-polish.md` | Loads game-native polish rules that prevent website-like surfaces, excessive gradients, nested boxes, and fake-premium chrome. |
| placeholder, missing assets, placeholder image, no imagery | `honest-placeholders.md` | Striped placeholder pattern for missing assets that prevents false design decisions |
| example-driven tasks | `implementation-examples.md` | Loads detailed guidance from `implementation-examples.md`. |
| color palette, harmony, oklch, perceptual, color generation | `oklch-color-harmony.md` | oklch() technique for perceptually uniform color palette generation |
| performance work | `performance-budgets.md` | Loads detailed guidance from `performance-budgets.md`. |
| tasks related to this reference | `phase-details.md` | Loads detailed guidance from `phase-details.md`. |
| tasks related to this reference | `vocabulary.md` | Loads detailed guidance from `vocabulary.md`. |

## Instructions

### Vocabulary

See `references/vocabulary.md` for term definitions (Hero, Full-bleed, Narrative brief, Surface type, Linear-style restraint, Decorative-only motion, Brand override). Read once before Phase 1.

### Phase 1: Context Discovery

**Goal**: Understand the project deeply before making aesthetic decisions.

**Step 1**: Read and follow the repository CLAUDE.md, then gather context (adapt based on what is already known):

1. **Purpose**: What is this frontend for? (portfolio, SaaS, creative showcase, docs, landing page)
2. **Surface type**: Landing page or app/dashboard? Design rules diverge sharply. Landing pages: full-bleed hero, narrative sequence. Apps: Linear-style calm surfaces, strong typography, few colors, dense information. Classify up front -- every downstream decision depends on it.
3. **Audience**: Who will use it?
4. **Emotion**: What should users feel? (professional, playful, sophisticated, rebellious, calm, energetic)
5. **Cultural context**: Geographic, cultural, or thematic associations?
6. **Constraints**: Accessibility, performance budgets, existing brand elements?
7. **Tech stack**: React, Vue, vanilla, Next.js?
8. **Real content**: Gather actual copy, product name, imagery. Placeholder text produces placeholder thinking. At minimum: hero headline, product name, first-viewport promise.
9. **Previous projects**: Check for overlapping choices with recent work -- variety is mandatory.

**Step 2**: Define 3-5 distinct aesthetic directions using `references/color-inspirations.json` and `references/font-catalog.json`. Multiple directions prevent anchoring on first instinct. See `references/phase-details.md` for examples.

**Step 3**: Output `aesthetic_direction.json` with direction(s) and contextual justification linking purpose, audience, and emotion. See `references/implementation-examples.md` for template.

**Step 4**: Write the narrative brief: visual thesis, content plan, interaction thesis. See `references/phase-details.md` for definition with examples.

**Gate**: Aesthetic direction defined with contextual justification. Narrative brief written with all three theses. Proceed only after both pass.

**Skip-if-answered**: If the request already provides surface type, product name, and hero promise, ask only for missing context.

### Phase 2: Typography Selection

**Goal**: Select distinctive, contextual font pairings.

**Step 1**: Load `references/font-catalog.json`. Avoid these overused fonts (signal generic output): Inter, Roboto, Arial, Helvetica, system fonts, Space Grotesk. Keep them out of selections and fallback stacks.

**Step 2**: Select font pairing per `references/phase-details.md` (5-step process, two-typefaces-maximum, brand-first rule).

**Step 3**: Validate against banned list. See `references/phase-details.md` for validation and manual verification.

**Step 4**: Document typography specification with families, weights, usage roles, and rationale. See `references/implementation-examples.md` for template.

**Gate**: No banned fonts, no recent reuse, confirmed aesthetic match. Proceed only after gate passes.

### Phase 3: Color Palette

**Goal**: Create a contextual palette with clear dominance hierarchy.

**Step 1**: Research cultural/contextual inspiration using `references/color-inspirations.json`. See `references/phase-details.md` for categories. Palette must trace to project context -- not convenience.

**Step 2**: Build palette with strict dominance:
- **Dominant** (60-70%): Base background and major surfaces
- **Secondary** (20-30%): Supporting elements, containers, navigation
- **Accent** (5-10%): High-impact moments, CTAs, highlights
- **Functional**: Success, warning, error, info

The 60/30/10 ratio is non-negotiable. **One accent color, not two.** A second accent is usually a functional color or a weight variation.

**Step 3**: Check against cliche list in `references/preferred-patterns.json`. See `references/phase-details.md` for the reference set.

**Step 4**: Validate. See `references/phase-details.md` for validation and manual verification.

**Gate**: Passes cliche detection. Clear 60/30/10 dominance. Proceed only after gate passes.

### Phase 4: Animation Strategy

**Goal**: Choreography for high-impact moments only. Restraint is a feature.

**The 2-to-3 rule**: Two or three intentional motions per page. The interaction thesis from Phase 1 names the slots; this phase choreographs them.

**Step 1**: Fill three motion slots (entrance, scroll, interaction). See `references/phase-details.md` for definitions, moments NOT worth animating, decorative-only litmus, recommended stack.

**Step 2**: Design choreography per `references/animation-patterns.md` and `references/phase-details.md`.

**Step 3**: Define easing curves and timing. See `references/phase-details.md` for easing-by-purpose and duration-by-scope tables.

**Gate**: At least one high-impact moment fully defined with element order, easing, and timing. Proceed only after defined.

### Phase 5: Hero Composition, Background & Atmosphere

**Goal**: Construct the first viewport as a single composition, then add depth through layered effects. Flat solid-color backgrounds fail this phase.

**Step 0**: Hero composition rules (landing pages). First viewport: one composition, not a grid of parts. See `references/phase-details.md` for hard rules (no cards in hero, full-bleed default, brand-first, one job per section, hero image litmus). Apps: see `references/app-vs-landing-rules.md`.

**Step 1**: Choose technique from `references/background-techniques.md` by aesthetic direction. See `references/phase-details.md` for technique-by-aesthetic mapping.

**Step 2**: Implement background CSS. See `references/phase-details.md` for minimum layers (base surface, gradient, pattern/texture).

**Step 3**: Verify text readability against WCAG AA contrast minimums.

**Gate**: Background uses at least 2 layers creating visual depth. Solid single-color backgrounds fail.

### App vs Landing Page Rules

See `references/app-vs-landing-rules.md` for full rule sets, app litmus test, and landing litmus test. Surface type from Phase 1 determines which governs layout.

### Phase 6: Validation & Scoring

**Goal**: Objective quality assessment before finalization.

**Step 1**: Run validation:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/validate_design.py design-spec.json
```

**Step 2**: Review report. See `references/phase-details.md` for full check list.

**Step 3**: If score < 80: review failed checks, iterate on that phase, re-run. Repeat until score >= 80.

**Gate**: Validation score >= 80 (Grade B+). Deliver specification only after gate passes.

### Phase 7: Design Specification Output

**Goal**: Complete, implementable design specification. Only implement what was requested.

**Step 1**: Generate CSS custom properties (design tokens) covering typography, colors, spacing, shadows, animations. See `references/implementation-examples.md`.

**Step 2**: Create base styles applying tokens to typography hierarchy, atmospheric background, layout defaults.

**Step 3**: Document specification: aesthetic direction, typography system, color palette with dominance, animation strategy with timing, background technique, validation score.

**Step 4**: If implementation requested, provide framework-specific starter code. See `references/implementation-examples.md`.

**Step 5**: Clean up temporary exploration artifacts. Keep final specification and validation report.

**Gate**: Design specification delivered with all sections and validation score.

### Examples

See `references/examples.md` for two worked examples (new landing page, design audit) showing the phase sequence end-to-end.

## Reference Material

### Design Catalogs

- `${CLAUDE_SKILL_DIR}/references/font-catalog.json`: Curated fonts by aesthetic category
- `${CLAUDE_SKILL_DIR}/references/color-inspirations.json`: Cultural/contextual palette sources
- `${CLAUDE_SKILL_DIR}/references/animation-patterns.md`: High-impact animation choreography with CSS and React examples
- `${CLAUDE_SKILL_DIR}/references/background-techniques.md`: Atmospheric background methods with code
- `${CLAUDE_SKILL_DIR}/references/preferred-patterns.json`: Banned fonts, cliche colors, layout/component cliches
- `${CLAUDE_SKILL_DIR}/references/implementation-examples.md`: CSS tokens, base styles, framework templates, spec templates
- `${CLAUDE_SKILL_DIR}/references/project-history.json`: Aesthetic choices across projects (auto-generated)
- `${CLAUDE_SKILL_DIR}/references/vocabulary.md`: Term definitions used as hard rules
- `${CLAUDE_SKILL_DIR}/references/phase-details.md`: Selection processes, validation blocks, easing/timing tables, hero rules, validation checks
- `${CLAUDE_SKILL_DIR}/references/app-vs-landing-rules.md`: Landing vs app surface type rule sets
- `${CLAUDE_SKILL_DIR}/references/examples.md`: Worked examples
- `${CLAUDE_SKILL_DIR}/references/error-handling.md`: Recovery for banned fonts, cliche palettes, low scores
- `${CLAUDE_SKILL_DIR}/references/game-ui-polish.md`: Game-native UI polish rules
- `${CLAUDE_SKILL_DIR}/references/css-audit-patterns.md`: grep/rg detection commands for banned fonts, hardcoded colors, over-animation, flat backgrounds
- `${CLAUDE_SKILL_DIR}/references/performance-budgets.md`: CSS render costs, compositor promotion, layout thrashing detection, frame budgets
- `${CLAUDE_SKILL_DIR}/references/oklch-color-harmony.md`: oklch() perceptually uniform palette generation
- `${CLAUDE_SKILL_DIR}/references/honest-placeholders.md`: Striped placeholder pattern for missing assets

## Error Handling

See `references/error-handling.md` for recovery: banned fonts, cliche palettes, low distinctiveness scores.

## References

- `${CLAUDE_SKILL_DIR}/references/font-catalog.json`
- `${CLAUDE_SKILL_DIR}/references/color-inspirations.json`
- `${CLAUDE_SKILL_DIR}/references/animation-patterns.md`
- `${CLAUDE_SKILL_DIR}/references/background-techniques.md`
- `${CLAUDE_SKILL_DIR}/references/preferred-patterns.json`
- `${CLAUDE_SKILL_DIR}/references/implementation-examples.md`
- `${CLAUDE_SKILL_DIR}/references/project-history.json`
- `${CLAUDE_SKILL_DIR}/references/game-ui-polish.md`
- `${CLAUDE_SKILL_DIR}/references/css-audit-patterns.md`
- `${CLAUDE_SKILL_DIR}/references/performance-budgets.md`
- `${CLAUDE_SKILL_DIR}/references/oklch-color-harmony.md`
- `${CLAUDE_SKILL_DIR}/references/honest-placeholders.md`
