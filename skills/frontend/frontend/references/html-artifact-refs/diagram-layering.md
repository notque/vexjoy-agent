# Diagram Layering Reference

SVG layering technique for architecture diagrams and flowcharts. Produces dark-theme, readable diagrams where arrows appear between components without endpoint bleed-through.

---

## Dark Design System Constants

| Token | Value | Use |
|---|---|---|
| Background | `#0f172a` | Page background, masking rectangles |
| Grid overlay | `#1e293b` | Subtle dashed grid lines |
| Font | JetBrains Mono | Code-style labels; Google Fonts fallback acceptable |

---

## Semantic Color Palette

| Category | Name | Hex | Use for |
|---|---|---|---|
| Primary | Cyan | `#06b6d4` | Frontend, entry points, user-facing components |
| Secondary | Emerald | `#10b981` | Backend services, APIs |
| Tertiary | Violet | `#8b5cf6` | Databases, storage |
| Accent | Amber | `#f59e0b` | Cloud services, external integrations |
| Alert | Rose | `#f43f5e` | Security, auth components |
| Connector | Orange | `#f97316` | Queues, message brokers |
| Neutral | Slate | `#64748b` | Utilities, shared services |
| Active | Blue | `#3b82f6` | Currently active state indicator |

Apply at 15-20% opacity for box fills; use full hex for borders and text.

---

## SVG Layering Order

Render exactly these 7 layers in sequence. Rendering out of order causes arrow endpoints to bleed through component boxes.

| Step | Layer | How |
|---|---|---|
| 1 | Background rectangle | `fill: #0f172a`, full SVG width x height |
| 2 | Grid overlay | Dashed lines, stroke `#1e293b`, low opacity |
| 3 | Region/boundary outlines | Dashed, `stroke-dasharray`, group containers only |
| 4 | Connection arrows | Drawn BEFORE boxes so boxes can cover endpoints |
| 5 | Opaque masking rectangles | Same fill as background (`#0f172a`), one per component position |
| 6 | Component boxes | Semi-transparent fill (color at 15-20% opacity), solid colored border |
| 7 | Text labels and legends | Color matches component category |

---

## The Masking Rectangle Technique

**Problem:** Semi-transparent component boxes let arrow endpoints show through the fill, producing a visible stab at each connection point.

**Solution:** After drawing all arrows (step 4), place a solid opaque rectangle at every component location using the background color. Draw the component box on top in step 6. The arrow is hidden under the mask at the component but fully visible between components.

```xml
<!-- Step 4: arrow connecting two components -->
<line x1="220" y1="70" x2="360" y2="70"
      stroke="#06b6d4" stroke-width="1.5" marker-end="url(#arrowCyan)"/>

<!-- Step 5: masking rect covers the arrow endpoint at the destination -->
<rect x="360" y="50" width="120" height="40" fill="#0f172a"/>

<!-- Step 6: component box on top of the mask -->
<rect x="360" y="50" width="120" height="40"
      fill="#06b6d420" stroke="#06b6d4" stroke-width="1.5" rx="4"/>
<text x="420" y="74" fill="#06b6d4"
      font-family="JetBrains Mono, monospace" font-size="11"
      text-anchor="middle">API Gateway</text>
```

The same technique works for curved paths (`<path>`) and diagonal lines.

---

## Typography Scale

| Element | Size | Color | Notes |
|---|---|---|---|
| Title | 16px | `#e2e8f0` (slate-200) | Single diagram title |
| Component labels | 11px | Matches component color | Centered in component box |
| Annotations | 7-8px | `#94a3b8` (slate-400) | Callout notes, port labels |
| Legend | 9px | `#94a3b8` | Bottom-left legend entries |

---

## Arrow Markers

Define one `<marker>` per category color at the top of `<defs>`. Reference by color name in `marker-end` attributes to keep arrows semantically matched to their source component.

```xml
<defs>
  <marker id="arrowCyan" markerWidth="10" markerHeight="7"
          refX="9" refY="3.5" orient="auto">
    <polygon points="0 0, 10 3.5, 0 7" fill="#06b6d4"/>
  </marker>
  <!-- Repeat for each category color -->
</defs>
```

---

## Load Signal

Load when: shape = `diagram` detected by `detect-shape.py`, OR request contains "SVG", "architecture diagram", "flowchart", or "sequence diagram".
