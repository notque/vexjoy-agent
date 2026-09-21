# Shape: Report / Research

> **Shape**: report | **Signal words**: report, summarize, status update, explain, incident, research
> CSS layout classes: `templates/shapes/report.css` (injected by assemble-template.py)

---

## Layout Description

Linear document flow optimized for reading. Key constraint: TL;DR box must be visible without scrolling. Collapsible sections for detail. Metric callouts for numbers. Timeline for chronological events.

---

## Key CSS Classes (from templates/shapes/report.css)

| Class | Purpose |
|---|---|
| `.tldr` | Highlighted summary box at top (accent-colored label) |
| `.metric-row` | 4-column grid of metric cards (responsive to 2-col then 1-col) |
| `.metric-card` | KPI card with label, value, delta |
| `.metric-delta` | Colored change indicator (`.positive`, `.negative`, `.neutral`) |
| `.timeline` | Vertical timeline with dot markers and connecting line |
| `.milestone` | Timeline entry (`.completed`, `.current`, `.upcoming` states) |
| `.milestone-marker` | Colored dot: green=completed, accent=current, gray=upcoming |
| `.risk-table` | Table with severity-colored row borders |
| `.risk-level` | Inline badge (`.high`, `.med`, `.low`) |

---

## Composition Guide

| Request | Sections |
|---|---|
| "Summarize/report" | Header + TL;DR + Metric Cards + Collapsible Sections |
| "Status update" | Header + TL;DR + Timeline + Risk Table |
| "Incident report" | Header + TL;DR + Timeline + Root Cause + Impact Metrics |
| "Research summary" | Header + TL;DR + Key Findings (collapsible) + Data Tables |

### Section Ordering
1. Header with title + metadata
2. TL;DR (always visible, never inside a collapsible)
3. Metric callouts (if quantitative data exists)
4. Main content (collapsible sections or timeline)
5. Risk table (if applicable)
6. Footer with timestamp

---

## Common Mistakes

| Mistake | Fix |
|---|---|
| TL;DR below the fold | Place immediately after header, before any content |
| Collapsibles default to open | Default to collapsed; reader scans then expands |
| Metrics without context | Include delta (change from previous period) and direction indicator |
| Timeline without status markers | Use `.completed`, `.current`, `.upcoming` milestone classes |
| Risk table without row coloring | Use left border colors via severity classes |

---

## Accessibility Checklist

- [ ] Collapsible sections use `<details>/<summary>` or `aria-expanded` + `aria-controls`
- [ ] Metric values are real text (not images)
- [ ] Timeline markers have text labels, not color alone
- [ ] Risk levels have text + color (not color alone)
- [ ] SVG diagrams have `role="img"` and `aria-label`
- [ ] Focus-visible on all interactive elements
