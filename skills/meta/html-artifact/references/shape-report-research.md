# Shape: Report / Research

> **Shape**: report | **Signal words**: report, summarize, status update, explain, incident, research
> CSS layout classes: `templates/shapes/report.css` (injected by assemble-template.py)
> Components: `collapsible`, `theme-toggle`, `copy-button`

Reports are SCANNABLE. Reader hits TL;DR first, then chooses where to go. Information density is high; decorative whitespace earns its keep. One section, one job.

---

## Layout Description

Linear top-to-bottom document flow on a single column. **TL;DR must be visible without scrolling** — first content block after the header. Below the fold: metric callouts (if quantitative), main content as collapsibles or timeline, optional risk table, footer with timestamp.

Optional sticky TOC (left rail, desktop only) for long-form explainers — collapses to top on mobile. Otherwise prefer a single-column flow; reports are read, not navigated.

---

## Canonical Markup Order (load-bearing rule)

| Order | Region | Purpose |
|---|---|---|
| 1 | `<header>` with `<h1>` + meta line | Title + date / author / version |
| 2 | `.tldr` block | One-paragraph summary; never inside a collapsible |
| 3 | `.metric-row` (optional) | KPI grid; place BEFORE detail, not after |
| 4 | Detail sections (collapsibles, prose, timeline) | Default-collapsed unless content is primary |
| 5 | `.risk-table` (optional) | Status updates and plans only |
| 6 | `<footer>` | Timestamp, source links |

Why this order: a reader scans top-to-bottom and stops as soon as their question is answered. Putting metrics before TL;DR forces interpretation before context. Putting risk table before detail buries the why.

### Skeleton

```html
<body data-shape="report" data-theme="birchline">
  <header>
    <h1>Q2 Reliability Review</h1>
    <p class="report-meta">May 5, 2026 · Platform team</p>
  </header>
  <main>
    <section class="tldr" aria-label="Summary">
      <strong>TL;DR</strong>
      <p>p99 latency dropped 92% after the rate-limiter rollout; one minor incident, no customer impact.</p>
    </section>
    <section class="metric-row" aria-label="Key metrics">
      <!-- .metric-card * 4 -->
    </section>
    <section aria-label="Detail">
      <!-- <details> blocks -->
    </section>
    <section aria-label="Risks">
      <!-- .risk-table -->
    </section>
  </main>
  <footer>Generated 2026-05-05 14:00 UTC</footer>
</body>
```

CSS lives in `templates/shapes/report.css` — do not redefine `.tldr`, `.metric-*`, `.timeline`, `.risk-*` inline.

---

## Section Types (worked examples)

### TL;DR block

```html
<section class="tldr" role="region" aria-label="Summary">
  <strong>TL;DR</strong>
  <p>Rate-limiter rollout completed on schedule. p99 latency 2.4s → 180ms.
     One minor incident (rollback within 20 min), no customer impact.
     Next milestone: regional failover drill, June 12.</p>
</section>
```

Use for: every report, every time. Place immediately after `<header>`. Keep to 2-3 sentences. Never put TL;DR inside a `<details>` — it must read without expanding anything.

### Metric callouts

```html
<section class="metric-row" role="region" aria-label="Key metrics">
  <div class="metric-card">
    <span class="metric-label">PRs Merged</span>
    <span class="metric-value">14</span>
    <span class="metric-delta positive">↑ 3 vs prior week</span>
  </div>
  <div class="metric-card">
    <span class="metric-label">Incidents</span>
    <span class="metric-value">1</span>
    <span class="metric-delta negative">↑ 1 vs prior week</span>
  </div>
  <div class="metric-card">
    <span class="metric-value">99.97%</span>
    <span class="metric-label">Uptime</span>
    <span class="metric-delta neutral">— flat</span>
  </div>
  <div class="metric-card">
    <span class="metric-value">3</span>
    <span class="metric-label">Open blockers</span>
    <span class="metric-delta positive">↓ 2</span>
  </div>
</section>
```

Use for: status reports, weekly updates, postmortems. Always 4 cards (the grid is `repeat(4, 1fr)`); fewer wastes the row, more wraps awkwardly. Each card needs label + value + delta. Delta must include direction (`↑` `↓` `—`) AND text — color alone is not an indicator.

### Collapsible detail section

```html
<details class="report-detail">
  <summary>Step 1 · Configure the rate limiter</summary>
  <div>
    <p>Rate limit windows are 60 seconds with a burst capacity of 20.</p>
    <pre><code>rate_limit:
  window: 60s
  max_requests: 100
  burst: 20</code></pre>
  </div>
</details>
```

Default is **collapsed**. Open only when content is primary (the user came for it). Native `<details>/<summary>` is preferred — zero JS, browser-native keyboard support. Reach for the `collapsible` component only when smooth height animation is required.

### Incident timeline

```html
<section aria-label="Incident timeline">
  <h2>Timeline</h2>
  <ol class="timeline">
    <li class="milestone completed">
      <span class="milestone-marker" aria-hidden="true"></span>
      <h4>14:32 UTC · Alert fired</h4>
      <p>p99 latency exceeded 2s. PagerDuty triggered, on-call ack within 3 min.</p>
    </li>
    <li class="milestone completed">
      <span class="milestone-marker" aria-hidden="true"></span>
      <h4>14:38 UTC · Root cause identified</h4>
      <p>Connection pool exhaustion correlated with deploy at 14:28.</p>
    </li>
    <li class="milestone current">
      <span class="milestone-marker" aria-hidden="true"></span>
      <h4>14:52 UTC · Rollback deployed</h4>
      <p>Reverted to previous release; pool recovered within 2 min.</p>
    </li>
    <li class="milestone upcoming">
      <span class="milestone-marker" aria-hidden="true"></span>
      <h4>Next: postmortem write-up</h4>
      <p>Owner: @ops. Due: May 9.</p>
    </li>
  </ol>
</section>
```

Use for: incident reports, project plans, changelogs. Status classes (`.completed`, `.current`, `.upcoming`) drive marker color — but each item also needs text status in the heading or body. Color alone is not an indicator.

### Risk table

```html
<table class="risk-table">
  <thead>
    <tr><th>Risk</th><th>Likelihood</th><th>Impact</th><th>Mitigation</th></tr>
  </thead>
  <tbody>
    <tr>
      <td>Regional failover untested at scale</td>
      <td><span class="risk-level high">High</span></td>
      <td><span class="risk-level high">High</span></td>
      <td>Drill scheduled June 12</td>
    </tr>
    <tr>
      <td>Token bucket assumes single AZ</td>
      <td><span class="risk-level med">Med</span></td>
      <td><span class="risk-level med">Med</span></td>
      <td>Cross-AZ design doc in review</td>
    </tr>
  </tbody>
</table>
```

Use for: status reports, plans, postmortem follow-ups. Severity uses `.risk-level.{high,med,low}` — text + color, never color alone.

---

## Composition Guide

| Request | Sections |
|---|---|
| "Summarize / report" | Header + TL;DR + Metrics + Collapsibles |
| "Status update" | Header + TL;DR + Metrics + Timeline + Risks |
| "Incident report" | Header + TL;DR + Timeline + Root Cause (collapsibles) + Impact metrics |
| "Research summary" | Header + TL;DR + Findings (collapsibles) + Tables |
| "How X works" (explainer) | Header + TL;DR + TOC + numbered Collapsibles + FAQ |
| "Changelog" | Header + Timeline grouped by version |

---

## ARIA / Accessibility

| Element | Required attributes | Why |
|---|---|---|
| `.tldr` | `role="region"`, `aria-label="Summary"` | Landmark for jump-to-summary |
| `.metric-row` | `role="region"`, `aria-label="Key metrics"` | Groups related KPIs |
| `.metric-delta` | `aria-label` describing direction + magnitude | Icon `↑` / `↓` is decorative; AT needs text |
| `<details>` | Native — no extra ARIA | `<summary>` already announces expanded/collapsed |
| `.timeline` | `<ol>` (ordered) not `<ul>` | Sequence is meaningful |
| `.milestone-marker` | `aria-hidden="true"` | Decorative; status is in text heading |
| `.risk-level` | Text inside element ("High") | Color alone fails WCAG; text label is required |
| TOC links | `<a href="#id">` to sections with matching `id` | Keyboard-navigable jump links |
| Print | All `<details>` rendered open in print stylesheet | Reader has no way to expand on paper |

---

## Common Mistakes

| Mistake | Fix |
|---|---|
| TL;DR below the fold (after metrics or images) | Move immediately after `<header>`, before any other section |
| TL;DR inside a `<details>` block | TL;DR must read without expanding anything |
| Collapsibles default to `open` | Default closed; the reader scans summaries, then expands selectively |
| Metric card with value but no delta | Always include delta — even "— flat" is more useful than nothing |
| Delta shown as colored arrow only | Pair color with `↑` `↓` `—` glyph and text |
| Timeline using `<ul>` | Sequence matters; use `<ol>` |
| Status conveyed by `.milestone-marker` color alone | Status must also appear in the heading text |
| Risk table without `.risk-level` badges (raw "High") | Use the badge — text + colored background, never color alone |
| Inline `<style>` redefining `.tldr` / `.metric-*` | Lives in `templates/shapes/report.css` — touching it creates drift |
| Sticky TOC on a 2-section report | Skip TOC unless there are 5+ sections; otherwise it's noise |
| Print stylesheet missing | Reports are commonly saved as PDF; print stylesheet ships with the template |

---

## Shape Selection

Use **report** when the request matches: report, summarize, status update, explain, incident, research, postmortem, weekly review, changelog, how-to, tutorial, FAQ.

Do **not** use report when:

- The user wants to compare N approaches side-by-side (use **spec**)
- The user wants to tune parameters interactively (use **prototype**)
- The user wants to triage / reorder / edit content (use **editor**)
- The user wants charts from raw data as the primary view (use **data-viz**)
- The user wants a slide-by-slide presentation (use **deck**)

Hybrid OK: `report + diagram` for explainers with inline SVG; `report + data-viz` for status reports with embedded charts.
