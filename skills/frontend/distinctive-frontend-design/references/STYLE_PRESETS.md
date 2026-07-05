# STYLE_PRESETS -- Frontend Slides Reference

> **Load this file during Phase 3 (DISCOVER STYLE) and Phase 4 (BUILD).**

## Assembly

Combine base CSS with a named preset:

```bash
python3 skills/frontend/frontend-slides/scripts/assemble-styles.py --preset obsidian-gold
```

Use `--list` to see all 12 presets with metadata, mood mapping, and animation details.
Use `--mood <word>` to find presets matching a mood (e.g., `--mood focused`).

## Template Files

| File | Purpose |
|------|---------|
| `templates/base.css` | Mandatory base CSS (box-sizing, deck, slide, reduced-motion) |
| `templates/presets/*.css` | 12 named preset CSS files with `:root` variables |

## Available Presets

| Preset | Mood | Use Case |
|--------|------|----------|
| obsidian-gold | impressed, authoritative | executive briefings, board presentations |
| arctic-minimal | focused, clean, technical | engineering talks, developer conferences |
| carbon-ember | energized, bold, startup | product launches, startup pitches |
| sage-paper | inspired, thoughtful | thought leadership, narrative-heavy decks |
| void-neon | futuristic, tech | developer tools, AI launches, hackathons |
| slate-coral | contemporary, SaaS | SaaS demos, sales enablement |
| chalk-board | educational, approachable | workshops, onboarding, training |
| glacier-blue | trusted, corporate | financial, legal, healthcare |
| rose-noir | artistic, luxury | fashion, design portfolios |
| solar-sand | warm, community | non-profit, community talks |
| steel-wire | industrial, data-heavy | data science, infrastructure, DevOps |
| lavender-mist | calm, wellness | mental health, wellness, meditation |

## CSS Gotchas

| Gotcha | Wrong | Right |
|--------|-------|-------|
| Negated clamp | `-clamp(...)` | `calc(-1 * clamp(...))` |
| Viewport height | `100vh` only | `100vh; height: 100dvh` |
| Font display | omitted | `font-display: swap` |
| Fixed inner heights | `height: 300px` | `max-height: min(50vh, 300px)` |
| display:none on slides | `display: none` | `opacity: 0; pointer-events: none; position: absolute` |

## Density Limits

| Slide Type | Limit |
|------------|-------|
| Title | 1 heading + 1 subtitle (max 12 words) |
| Content | 4-6 bullets (max 10 words each) |
| Feature grid | 6 cards max |
| Code | 8-10 lines |
| Quote | 1 quote (max 30 words) + attribution |
| Image | 1 image (constrained) + caption (max 10 words) |
| Section break | 1 word or short phrase |
