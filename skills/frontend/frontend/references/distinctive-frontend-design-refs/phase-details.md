## Step Details

Depth for DISTINCTIVE mode steps. The core judgment lives in `skills/shared-patterns/ui-design-judgment.md`; this file adds values and examples. Every item is a default: override it when you can name the reason it does not fit.

### Step 2: Choosing a direction

Derive the direction from the brand, audience, and content, then name it in a few words. Examples of how a direction translates into choices:

| Direction | Type | Color | Surface |
|---|---|---|---|
| Calm product launch | One neutral sans, large bold headline | Tinted neutrals, one brand accent | Solid, generous spacing |
| Technical developer tool | Neutral sans plus mono for code | Dark or light neutral, one accent | Solid, grid-aligned |
| Warm craft brand | Humanist sans or book serif | Earth-tinted neutrals | Photography carries warmth |
| Loud event or campaign | Condensed or heavy display face | High-contrast brand pair | One bold graphic device |

Anti-examples: purple-to-blue gradient on white (generic default), and serif display with cream background and grain on every project (overcorrection). Both are picks made without a brand reason. See the core doc's "Tells of generated UI" table.

Brand-first on branded pages: set the product name at hero scale in the display face.

### Step 3: Choosing type

1. Pick the category in `font-catalog.json` that matches the direction. For tools, use `product_ui_neutral`.
2. Choose one display and one text face, or one family with weight variation. Two families is the default ceiling; a third needs a reason.
3. Check hierarchy with real content at the core doc's scale (for example 14, 16, 20, 24, 32, 48).
4. Variety across projects is a weak signal. Fit to this brand matters more than being different from the last project.

### Step 4: Palette checks

- Source the accent from the brand. Without a brand, use `color-inspirations.json` for a starting hue.
- Pure white backgrounds are fine in light mode. Avoid pure black under pure white text in dark mode.
- Report colors as exact values (hex or OKLCH) with their contrast ratio against the surfaces they sit on.

### Step 5: Motion slots

A good budget is one motion per slot, 2-3 in total:

1. **Entrance**: one hero reveal on load (headline, media, or a short stagger).
2. **Scroll**: one scroll-linked or sticky effect.
3. **Interaction**: one hover, reveal, or layout transition on the primary action.

Litmus: remove the motion mentally. If the page means the same thing without it, cut it. More motion is fine when each one explains a change (core doc section 7).

Not worth animating: every hover on every element, footers and metadata, background elements behind text.

Easing:
- Entrances: `cubic-bezier(0.22, 1, 0.36, 1)`
- Exits: `cubic-bezier(0.4, 0, 1, 1)`
- Interactions: `cubic-bezier(0.4, 0, 0.2, 1)`
- Playful overshoot (celebrations only): `cubic-bezier(0.68, -0.55, 0.265, 1.55)`

Duration:
- Hover, focus, press: 150-250 ms
- Component transitions (card, modal, drawer): 250-400 ms
- One-time hero entrance: 500-800 ms, stagger 80-150 ms
- Never over 1000 ms for UI

### Step 5: Hero composition (brand pages)

- One composition: a new user can describe the first viewport in one sentence.
- One job, one primary action.
- Full-bleed by default. A hero inside a rounded shadowed card reads as a dashboard tile; use it only when the card is the product (for example, a device mockup).
- Image litmus: if the page works as well without the hero image, replace the image rather than decorating it.

### Step 5: Backgrounds

Start with a solid surface. Add one technique from `background-techniques.md` only when it carries the brand:

| Technique | Fits |
|---|---|
| Soft radial gradient in the brand hue | Launch pages that need a focal glow behind the product |
| Grid, dot, or line pattern | Technical and developer brands |
| Grain or paper texture | Craft or print brands, never by default |
| Photograph or product render | Anything with strong real imagery; usually the best choice |

Check text contrast on the busiest part of the background.

### Step 6: Design stamp

The first line of generated CSS records the build so a later run can re-audit and the variety check can recover the macro id:

```
/* vexjoy-design: macro=<id> theme=<name> contrast=<pass|fail> nav=<id> footer=<id> mobile=<pass|fail> */
```

| field | value |
|---|---|
| `macro` | the Step 2 `macro:*` id |
| `theme` | palette name from Step 4 |
| `contrast` | `pass` if text meets WCAG AA against its background, else `fail` |
| `nav` | navigation pattern id (for example `top-bar`, `sidebar`, `none`) |
| `footer` | footer pattern id (for example `slim`, `sitemap`, `none`) |
| `mobile` | `pass` if verified at 375 px in Step 7, else `fail` |

The stamp is a claim, not proof. `scripts-distinctive-frontend-design/css_slop_rules.py` re-scans the rendered CSS, and Step 7 checks the render.
