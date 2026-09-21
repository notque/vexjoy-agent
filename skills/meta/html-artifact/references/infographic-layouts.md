# Infographic Layouts Reference

Layout taxonomy and visual style system for infographic generation. Covers 21 layout types and 22 visual styles with pre-tuned content-type pairings.

---

## Layout Types (21)

### Sequences

| Layout | Structure | When to use |
|---|---|---|
| `linear-progression` | Step-by-step flow, left to right | Processes, timelines under 8 steps |
| `comic-strip` | Panel-based narrative | Storytelling, cause-and-effect |
| `winding-roadmap` | Curving path with milestones | Journeys, multi-stage milestones |
| `circular-flow` | Cycle that loops back to start | Recurring processes, ecosystems |

### Hierarchies

| Layout | Structure | When to use |
|---|---|---|
| `hierarchical-layers` | Top-down tiers | Org charts, classification systems |
| `tree-branching` | Root with radiating branches | Taxonomies, decision trees |
| `funnel` | Wide-to-narrow progression | Conversion funnels, filtering steps |
| `story-mountain` | Tension arc: setup / rising / climax / falling / resolution | Narrative arcs |

### Comparisons

| Layout | Structure | When to use |
|---|---|---|
| `binary-comparison` | Two columns side by side | A vs B, before/after |
| `comparison-matrix` | Grid: items on both axes | Feature matrices, 3-6 items x 3-6 criteria |
| `venn-diagram` | Overlapping circles | Overlap between 2-3 groups |

### Spatial

| Layout | Structure | When to use |
|---|---|---|
| `isometric-map` | 3D-perspective grid | System architecture, city/place metaphors |
| `structural-breakdown` | Exploded view of a system | Anatomy of a product or system |
| `hub-spoke` | Central node with radiating connections | Ecosystems, central concepts |
| `jigsaw` | Interlocking pieces | Components that fit together |

### Data-Focused

| Layout | Structure | When to use |
|---|---|---|
| `dashboard` | Metric cards + charts in a grid | KPI overviews, 5-12 metrics |
| `periodic-table` | Element-card grid | Categorized collections, 9-25 items |
| `bento-grid` | Unequal-size tiles | Feature showcases, asymmetric content |
| `dense-modules` | Compact card grid | Knowledge cards, reference sheets, 20-50 items |

### Special

| Layout | Structure | When to use |
|---|---|---|
| `iceberg` | Visible portion above, hidden bulk below | "More than meets the eye" concepts |
| `bridge` | Two endpoints connected by an arch | Connecting two states or concepts |

---

## Visual Styles (22)

| Style | Aesthetic | Best for |
|---|---|---|
| `craft-handmade` | Hand-drawn textures, paper feel | Personal, warm, approachable |
| `cyberpunk-neon` | Dark bg, bright neon lines | Tech, futuristic, edgy |
| `kawaii` | Cute, pastel, rounded | Consumer apps, playful |
| `technical-schematic` | Blueprint, monochrome, precise | Engineering, technical docs |
| `retro-pop-grid` | 80s grid, bold colors | Nostalgic, energetic |
| `corporate-memphis` | Geometric shapes, bold outlines | Business, modern SaaS |
| `minimal-flat` | White space, simple shapes | Clean, professional |
| `isometric-3d` | 3D perspective, geometric | Architecture, product |
| `watercolor-editorial` | Soft washes, editorial feel | Creative, premium |
| `dark-premium` | Dark bg, gold accents | Luxury, sophisticated |
| `newspaper` | High contrast, serif fonts | Editorial, authoritative |
| `chalk-blackboard` | Dark bg, chalk texture | Educational, informal |
| `data-sci-notebook` | Jupyter-like, light bg | Data science, research |
| `vaporwave` | Gradient purples/pinks | Aesthetic, nostalgic |
| `sketchnote` | Handwritten + sketches | Learning, notes |
| `glassmorphism` | Frosted glass, blur | Modern UI, tech |
| `brutalist` | Raw, bold borders, harsh | Edgy, statement |
| `warm-editorial` | Warm tones, humanist | Lifestyle, wellness |
| `science-textbook` | Clean, labeled diagrams | Academic, educational |
| `comic-book` | Bold outlines, halftone | Fun, narrative |
| `art-deco` | Geometric ornament, gold | Elegant, historic |
| `y2k` | Chrome, gradients, pixel | Nostalgic, ironic |

---

## Content-Type to Layout Pairings

Pre-tuned recommendations. Use as starting point; adjust for content specifics.

| Content Type | Recommended Layout | Style Match |
|---|---|---|
| 5-step process | `linear-progression` | `corporate-memphis` or `minimal-flat` |
| Timeline (6-12 events) | `winding-roadmap` | `watercolor-editorial` |
| Recurring cycle | `circular-flow` | `isometric-3d` |
| A vs B comparison | `binary-comparison` | `minimal-flat` |
| Feature matrix (products) | `comparison-matrix` | `corporate-memphis` |
| Taxonomy (10-20 items) | `periodic-table` | `technical-schematic` |
| System architecture | `isometric-map` | `cyberpunk-neon` or `dark-premium` |
| KPI dashboard | `dashboard` | `data-sci-notebook` |
| Concept with hidden depth | `iceberg` | `dark-premium` |
| Central concept + ecosystem | `hub-spoke` | `glassmorphism` |

---

## Load Signal

Load when: shape = `data-viz` detected by `detect-shape.py`, OR request contains "infographic", "layout", "visual", "visualize data", or "chart type".
