#!/usr/bin/env python3
"""Regenerate the html-artifact gallery in tmp/html-artifact-gallery/.

Calls assemble-template.py for each of the 8 shapes, fills in shape-appropriate
content that exercises the layout primitives (especially the 2026-05-20 fixes:
deck slide variants, spec [data-count] + alternatives + architecture diagram,
prototype controls panel without overflow/min-width). Validates each artifact
post-write.

Usage:
    python3 skills/meta/html-artifact/scripts/build-gallery.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# This file lives at <repo>/skills/meta/html-artifact/scripts/build-gallery.py,
# so the repo root is five levels up from __file__.
REPO_ROOT = Path(__file__).resolve().parents[4]
GALLERY = REPO_ROOT / "tmp" / "html-artifact-gallery"
ASSEMBLE = REPO_ROOT / "skills" / "meta" / "html-artifact" / "scripts" / "assemble-template.py"
VALIDATE = REPO_ROOT / "skills" / "meta" / "html-artifact" / "scripts" / "validate-artifact.py"

# (shape, title, components, body_html). The body_html is injected after the
# theme-toggle button, replacing the assembler's <header><main><footer>
# placeholders by string-finding the empty <header></header> markers.
SHAPES: list[tuple[str, str, str, str]] = []

# --- spec --------------------------------------------------------------------
SPEC_BODY = """
  <header>
    <h1>Cache Invalidation Strategies</h1>
    <p class="subtitle">Four approaches for keeping a read-heavy product cache fresh without a stampede. Pick by write frequency, staleness tolerance, and ops budget.</p>
  </header>
  <main>
    <section class="recommendation" aria-label="TL;DR" style="margin-top: 0; margin-bottom: var(--sp-7);">
      <h2>TL;DR</h2>
      <p>For most product caches: <strong>TTL + background refresh</strong>. Switch to event-driven only when staleness must be sub-second. Manual purge stays as the break-glass tool. Write-through is the right answer only when the cache and primary share a transaction boundary.</p>
    </section>

    <figure class="architecture-diagram">
      <svg viewBox="0 0 720 220" role="img" aria-label="Cache invalidation flow comparison">
        <defs>
          <marker id="arr" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
            <path d="M0,0 L8,3 L0,6" fill="currentColor"/>
          </marker>
        </defs>
        <rect x="40" y="80" width="120" height="60" rx="8" fill="rgba(64,128,200,0.12)" stroke="rgba(64,128,200,1)" stroke-width="1.5"/>
        <text x="100" y="115" text-anchor="middle" font-size="13" fill="currentColor">Client</text>
        <line x1="160" y1="110" x2="240" y2="110" stroke="currentColor" stroke-width="1.5" marker-end="url(#arr)"/>
        <rect x="240" y="80" width="160" height="60" rx="8" fill="rgba(150,200,100,0.12)" stroke="rgba(150,200,100,1)" stroke-width="1.5"/>
        <text x="320" y="115" text-anchor="middle" font-size="13" fill="currentColor">Cache</text>
        <line x1="400" y1="110" x2="480" y2="110" stroke="currentColor" stroke-width="1.5" marker-end="url(#arr)"/>
        <rect x="480" y="80" width="160" height="60" rx="8" fill="rgba(220,140,80,0.12)" stroke="rgba(220,140,80,1)" stroke-width="1.5"/>
        <text x="560" y="115" text-anchor="middle" font-size="13" fill="currentColor">Primary store</text>
      </svg>
      <figcaption>Figure 1 &middot; The shared cache topology under evaluation.</figcaption>
    </figure>

    <!-- Top 3 approaches: full cards in 3-column grid -->
    <section class="comparison-grid" data-count="3" aria-label="Cache approaches">
      <article class="approach-card">
        <header class="approach-header"><span class="approach-number">01</span><h3>TTL + background refresh</h3><span class="approach-tag">Recommended</span></header>
        <p>Each entry has a TTL; a background job refreshes hot keys before expiry to hide miss latency.</p>
        <div class="pros-cons">
          <div class="pros"><h4>Pros</h4><ul><li>Predictable load shape</li><li>No tight coupling to producers</li><li>Works for any data source</li></ul></div>
          <div class="cons"><h4>Cons</h4><ul><li>Bounded staleness, never zero</li><li>Refresh job complexity</li></ul></div>
        </div>
        <div class="badges"><span class="badge">Complexity: Medium</span><span class="badge">Staleness: 30s-5m</span></div>
      </article>
      <article class="approach-card">
        <header class="approach-header"><span class="approach-number">02</span><h3>Event-driven invalidation</h3></header>
        <p>Producers emit change events; cache subscribers invalidate the affected keys synchronously.</p>
        <div class="pros-cons">
          <div class="pros"><h4>Pros</h4><ul><li>Sub-second staleness</li><li>Bandwidth-efficient</li></ul></div>
          <div class="cons"><h4>Cons</h4><ul><li>Producer coupling</li><li>Lost-event recovery is hard</li></ul></div>
        </div>
        <div class="badges"><span class="badge">Complexity: High</span><span class="badge">Staleness: &lt;1s</span></div>
      </article>
      <article class="approach-card">
        <header class="approach-header"><span class="approach-number">03</span><h3>Write-through</h3></header>
        <p>Every write hits the cache and the primary in the same transaction.</p>
        <div class="pros-cons">
          <div class="pros"><h4>Pros</h4><ul><li>Cache always consistent</li><li>Simple mental model</li></ul></div>
          <div class="cons"><h4>Cons</h4><ul><li>Adds latency to writes</li><li>Cache outage breaks writes</li></ul></div>
        </div>
        <div class="badges"><span class="badge">Complexity: Low</span><span class="badge">Staleness: 0</span></div>
      </article>
    </section>

    <!-- Demoted alternative: compact card -->
    <section class="alternatives" aria-label="Alternatives considered">
      <h2>Other approaches considered</h2>
      <div class="alternatives-grid">
        <article class="approach-card">
          <header class="approach-header"><span class="approach-number">04</span><h3>Manual purge only</h3></header>
          <p>Operators trigger invalidation when needed.</p>
          <div class="pros-cons"><div class="cons"><h4>Cons</h4><ul><li>Stale data between purges</li><li>Requires human in loop</li></ul></div></div>
        </article>
        <article class="approach-card">
          <header class="approach-header"><span class="approach-number">05</span><h3>No cache</h3></header>
          <p>Hit primary store every read.</p>
          <div class="pros-cons"><div class="cons"><h4>Cons</h4><ul><li>10-100x latency</li><li>Primary store load</li></ul></div></div>
        </article>
      </div>
    </section>

    <section><table class="tradeoff-matrix">
      <thead><tr><th>Dimension</th><th>TTL+Refresh</th><th>Event-driven</th><th>Write-through</th></tr></thead>
      <tbody>
        <tr><th scope="row">Staleness floor</th><td><span class="cell-warning">30s</span></td><td><span class="cell-success">&lt;1s</span></td><td><span class="cell-success">0</span></td></tr>
        <tr><th scope="row">Producer coupling</th><td><span class="cell-success">None</span></td><td><span class="cell-danger">Tight</span></td><td><span class="cell-warning">Transactional</span></td></tr>
        <tr><th scope="row">Recovery complexity</th><td><span class="cell-success">Self-heals on TTL</span></td><td><span class="cell-danger">Lost-event audit</span></td><td><span class="cell-success">N/A</span></td></tr>
      </tbody>
    </table></section>

    <section class="recommendation" aria-label="Recommendation">
      <h2>Recommended: TTL + background refresh</h2>
      <p>Adopts in 1 sprint, no producer changes, predictable load. The 30s-5m staleness window is acceptable for our content surface; revisit if pricing or inventory enters the cache and sub-second staleness becomes a requirement.</p>
    </section>
  </main>
  <footer>Authored 2026-05-20 &middot; @platform</footer>
"""

SHAPES.append(("spec", "Cache Invalidation Strategies", "tabs,copy-button", SPEC_BODY))

# --- deck --------------------------------------------------------------------
DECK_BODY = """
  <main>
    <div class="slide-deck" role="region" aria-label="Resilient APIs deck" aria-roledescription="carousel">
      <section class="slide slide-title active" role="group" aria-roledescription="slide" aria-label="Slide 1 of 6: Title">
        <h1>Building Resilient APIs</h1>
        <p class="slide-subtitle">Patterns for graceful degradation at scale</p>
        <p class="slide-meta">Engineering Team &middot; May 2026</p>
      </section>

      <section class="slide" role="group" aria-roledescription="slide" aria-label="Slide 2 of 6: Principles">
        <h2>Key Principles</h2>
        <ul>
          <li>Fail fast, recover faster</li>
          <li>Degrade gracefully under load</li>
          <li>Circuit breakers on all external calls</li>
          <li>Retry with exponential backoff</li>
        </ul>
      </section>

      <section class="slide slide-split" role="group" aria-roledescription="slide" aria-label="Slide 3 of 6: Before / After">
        <div class="split-text">
          <h2>Before &amp; After</h2>
          <ul>
            <li>p99 latency: 2.4s &rarr; 180ms</li>
            <li>Error rate: 4.2% &rarr; 0.1%</li>
            <li>Uptime: 99.2% &rarr; 99.97%</li>
          </ul>
        </div>
        <div class="split-visual">
          <svg viewBox="0 0 280 200" role="img" aria-label="Latency improvement chart">
            <rect x="20" y="40" width="80" height="140" fill="rgba(220,140,80,0.6)"/>
            <rect x="160" y="160" width="80" height="20" fill="rgba(150,200,100,0.7)"/>
            <text x="60" y="30" text-anchor="middle" font-size="11" fill="currentColor">Before</text>
            <text x="200" y="150" text-anchor="middle" font-size="11" fill="currentColor">After</text>
          </svg>
        </div>
      </section>

      <section class="slide slide-code" role="group" aria-roledescription="slide" aria-label="Slide 4 of 6: Circuit breaker">
        <h2>Circuit Breaker</h2>
        <pre><code>class CircuitBreaker {
  constructor(threshold = 5, resetMs = 30000) {
    this.failures = 0;
    this.state = 'closed';
  }
  async call(fn) {
    if (this.state === 'open') throw new Error('Circuit open');
    try { const r = await fn(); this.onSuccess(); return r; }
    catch (e) { this.onFailure(); throw e; }
  }
}</code></pre>
      </section>

      <section class="slide slide-quote" role="group" aria-roledescription="slide" aria-label="Slide 5 of 6: Quote">
        <blockquote>
          <p>&ldquo;Everything fails all the time.&rdquo;</p>
          <cite>Werner Vogels, CTO Amazon</cite>
        </blockquote>
      </section>

      <section class="slide slide-section" role="group" aria-roledescription="slide" aria-label="Slide 6 of 6: Closing">
        <p class="eyebrow">Wrap</p>
        <h2>Questions?</h2>
      </section>
    </div>
  </main>
  <footer>
    <nav class="slide-nav no-print" aria-label="Slide navigation">
      <button type="button" class="slide-prev" aria-label="Previous slide">&#8249;</button>
      <span class="slide-counter" aria-live="polite">1/6</span>
      <button type="button" class="slide-next" aria-label="Next slide">&#8250;</button>
    </nav>
    <div class="progress-bar" role="progressbar" aria-label="Deck progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="17">
      <div class="progress-fill" style="width: 17%;"></div>
    </div>
  </footer>
"""

SHAPES.append(("deck", "Building Resilient APIs", "keyboard-nav", DECK_BODY))

# --- prototype ---------------------------------------------------------------
PROTO_BODY = """
  <header>
    <h1>Card Padding &amp; Radius Tuner</h1>
    <p>Adjust spacing and corner tokens; copy CSS variables when ready.</p>
  </header>
  <main class="prototype-layout">
    <aside class="controls-panel" aria-label="Controls">
      <h2>Spacing</h2>
      <div class="control-row">
        <label for="pad-x">Horizontal</label>
        <input id="pad-x" type="range" min="8" max="48" value="20"
               oninput="document.querySelector('.demo-card').style.setProperty('--demo-px', this.value+'px'); this.parentElement.querySelector('.value-display').textContent = this.value+'px';">
        <span class="value-display" aria-live="polite">20px</span>
      </div>
      <div class="control-row">
        <label for="pad-y">Vertical</label>
        <input id="pad-y" type="range" min="8" max="48" value="16"
               oninput="document.querySelector('.demo-card').style.setProperty('--demo-py', this.value+'px'); this.parentElement.querySelector('.value-display').textContent = this.value+'px';">
        <span class="value-display" aria-live="polite">16px</span>
      </div>

      <div class="control-group-label">Shape</div>
      <div class="control-row">
        <label for="radius">Radius</label>
        <input id="radius" type="range" min="0" max="24" value="8"
               oninput="document.querySelector('.demo-card').style.setProperty('--demo-radius', this.value+'px'); this.parentElement.querySelector('.value-display').textContent = this.value+'px';">
        <span class="value-display" aria-live="polite">8px</span>
      </div>
      <div class="control-row">
        <label for="elevation">Elevation</label>
        <select id="elevation" onchange="document.querySelector('.demo-card').dataset.elevation = this.value;">
          <option value="0">Flat</option>
          <option value="1" selected>Soft</option>
          <option value="2">Lifted</option>
          <option value="3">Floating</option>
        </select>
        <span class="value-display">soft</span>
      </div>

      <button class="export-btn" type="button" onclick="copyCSS()" aria-label="Copy CSS variables">Copy CSS Variables</button>
    </aside>
    <section class="preview-panel">
      <div class="preview-surface" aria-label="Live preview">
        <div class="demo-card" data-elevation="1" style="--demo-px:20px; --demo-py:16px; --demo-radius:8px; padding: var(--demo-py) var(--demo-px); border-radius: var(--demo-radius); background: var(--bg-page); box-shadow: 0 2px 6px rgba(0,0,0,0.1); max-width: 320px;">
          <h3 style="margin-bottom: 8px;">Tunable card</h3>
          <p>Adjust the controls on the left to see this card update live.</p>
        </div>
      </div>
    </section>
  </main>
  <script>
    function copyCSS() {
      const px = document.getElementById('pad-x').value;
      const py = document.getElementById('pad-y').value;
      const r = document.getElementById('radius').value;
      const css = ':root {\\n  --card-px: ' + px + 'px;\\n  --card-py: ' + py + 'px;\\n  --card-radius: ' + r + 'px;\\n}';
      navigator.clipboard.writeText(css).then(() => {
        const btn = document.querySelector('.export-btn');
        btn.textContent = 'Copied!';
        btn.classList.add('copied');
        setTimeout(() => { btn.textContent = 'Copy CSS Variables'; btn.classList.remove('copied'); }, 1500);
      });
    }
  </script>
"""

SHAPES.append(("prototype", "Card Padding & Radius Tuner", "slider,copy-button", PROTO_BODY))

# --- report ------------------------------------------------------------------
REPORT_BODY = """
  <header>
    <h1>Q2 Reliability Review</h1>
    <p class="subtitle">Incident counts down 38%, p99 down 22%, on-call pages down 51%.</p>
  </header>
  <main>
    <section class="tldr" aria-label="TL;DR">
      <h2>TL;DR</h2>
      <p>The reliability investment paid off. Every leading indicator improved without a corresponding feature-velocity penalty. The two open risks are dependency drift and cold-start latency, both tracked.</p>
    </section>

    <section class="metric-row" aria-label="Headline metrics">
      <div class="metric-card"><div class="metric-value">38%</div><div class="metric-label">Incident reduction</div></div>
      <div class="metric-card"><div class="metric-value">180ms</div><div class="metric-label">p99 latency</div></div>
      <div class="metric-card"><div class="metric-value">99.97%</div><div class="metric-label">Uptime</div></div>
      <div class="metric-card"><div class="metric-value">51%</div><div class="metric-label">Pages reduced</div></div>
    </section>

    <details class="collapsible">
      <summary>What we shipped</summary>
      <div class="collapsible-body">
        <ul>
          <li>Circuit breakers on all external calls</li>
          <li>Retry budgets with exponential backoff</li>
          <li>Read-through cache with background refresh</li>
          <li>Graceful degradation contracts on three top endpoints</li>
        </ul>
      </div>
    </details>

    <details class="collapsible">
      <summary>Open risks</summary>
      <div class="collapsible-body">
        <table class="risk-table">
          <thead><tr><th>Risk</th><th>Likelihood</th><th>Impact</th><th>Owner</th></tr></thead>
          <tbody>
            <tr><td>Dependency drift</td><td>Medium</td><td>Medium</td><td>Platform</td></tr>
            <tr><td>Cold-start latency</td><td>High</td><td>Low</td><td>API</td></tr>
          </tbody>
        </table>
      </div>
    </details>
  </main>
  <footer>Authored 2026-05-20 &middot; @reliability</footer>
"""

SHAPES.append(("report", "Q2 Reliability Review", "collapsible,copy-button", REPORT_BODY))

# --- code-review -------------------------------------------------------------
CR_BODY = """
  <nav class="file-nav" aria-label="Files in this review">
    <ul>
      <li><a href="#file-1">api/handlers.go</a></li>
      <li><a href="#file-2">api/middleware.go</a></li>
    </ul>
  </nav>
  <main>
    <section class="pr-summary">
      <h1>PR #847: Add rate limiter middleware</h1>
      <p>Two files, ~80 lines added. One blocking concern (race in token bucket); two suggestions.</p>
    </section>
    <section class="risk-map" aria-label="Risk overview">
      <span class="risk-tag risk-blocking">1 Blocking</span>
      <span class="risk-tag risk-suggestion">2 Suggestions</span>
    </section>
    <article id="file-1" class="diff-file">
      <h2>api/handlers.go</h2>
      <pre class="diff"><code>+func (h *Handler) Limited(w http.ResponseWriter, r *http.Request) {
+    if !h.bucket.Allow() {
+        http.Error(w, &quot;rate limited&quot;, 429)
+        return
+    }
+    h.next.ServeHTTP(w, r)
+}</code></pre>
      <aside class="annotation severity-blocking">
        <strong>Blocking:</strong> <code>h.bucket.Allow()</code> reads and decrements without a lock; concurrent requests will both pass when only one should. Wrap in a mutex or use atomic operations.
      </aside>
    </article>
    <article id="file-2" class="diff-file">
      <h2>api/middleware.go</h2>
      <pre class="diff"><code>+func NewBucket(rate, burst int) *Bucket {
+    return &amp;Bucket{rate: rate, tokens: burst}
+}</code></pre>
      <aside class="annotation severity-suggestion">
        <strong>Suggestion:</strong> Add a defaults guard for <code>rate &lt;= 0</code> &mdash; today it would silently never refill.
      </aside>
    </article>
  </main>
"""

SHAPES.append(("code-review", "PR #847 Review", "collapsible,filter,keyboard-nav", CR_BODY))

# --- editor ------------------------------------------------------------------
EDITOR_BODY = """
  <header>
    <h1>Feature Flag Triage</h1>
    <p>Drag to reorder. Click a flag to toggle. Export the new ordering as JSON.</p>
  </header>
  <main>
    <ul class="kanban" id="flags" aria-label="Feature flags">
      <li class="card-flat" draggable="true" data-flag="dark-mode">dark-mode <span class="badge">on</span></li>
      <li class="card-flat" draggable="true" data-flag="new-search">new-search <span class="badge">off</span></li>
      <li class="card-flat" draggable="true" data-flag="checkout-v2">checkout-v2 <span class="badge">on</span></li>
      <li class="card-flat" draggable="true" data-flag="experimental-ai">experimental-ai <span class="badge">off</span></li>
    </ul>
  </main>
  <footer class="export-bar">
    <span class="pending-badge">0 changes</span>
    <button type="button" onclick="window.location.reload()">Reset</button>
    <button class="copy-button" type="button" onclick="copyOrdering()">Copy JSON</button>
  </footer>
  <script>
    function copyOrdering() {
      const items = Array.from(document.querySelectorAll('#flags > li')).map(li => li.dataset.flag);
      navigator.clipboard.writeText(JSON.stringify(items, null, 2));
    }
  </script>
"""

SHAPES.append(("editor", "Feature Flag Triage", "drag-drop,filter,copy-button", EDITOR_BODY))

# --- data-viz ----------------------------------------------------------------
DV_BODY = """
  <header class="dash-header">
    <h1>API Latency Dashboard</h1>
    <p class="subtitle">Last 24 hours, all endpoints</p>
  </header>
  <main>
    <section class="metric-row">
      <div class="metric-card"><div class="metric-value">142ms</div><div class="metric-label">p50</div></div>
      <div class="metric-card"><div class="metric-value">380ms</div><div class="metric-label">p95</div></div>
      <div class="metric-card"><div class="metric-value">820ms</div><div class="metric-label">p99</div></div>
      <div class="metric-card"><div class="metric-value">0.04%</div><div class="metric-label">Error rate</div></div>
    </section>
    <section class="dash-charts">
      <figure>
        <svg viewBox="0 0 480 200" role="img" aria-label="Latency over 24 hours">
          <polyline points="20,150 60,140 100,120 140,130 180,110 220,90 260,100 300,80 340,95 380,70 420,75 460,60" fill="none" stroke="currentColor" stroke-width="2"/>
          <line x1="20" y1="180" x2="460" y2="180" stroke="currentColor" stroke-width="0.5"/>
        </svg>
        <figcaption>p99 latency, 24h</figcaption>
      </figure>
    </section>
    <table class="risk-table">
      <thead><tr><th>Endpoint</th><th>p50</th><th>p99</th><th>RPS</th></tr></thead>
      <tbody>
        <tr><td>/v1/search</td><td>180ms</td><td>1.2s</td><td>240</td></tr>
        <tr><td>/v1/items</td><td>120ms</td><td>610ms</td><td>410</td></tr>
        <tr><td>/v1/users/me</td><td>40ms</td><td>110ms</td><td>980</td></tr>
      </tbody>
    </table>
  </main>
"""

SHAPES.append(("data-viz", "API Latency Dashboard", "filter", DV_BODY))

# --- diagram -----------------------------------------------------------------
DIAGRAM_BODY = """
  <header>
    <h1>Request Flow: Authenticated API Call</h1>
    <p class="subtitle">Client to primary store via API gateway, auth, and read cache.</p>
  </header>
  <main>
    <figure class="diagram-container">
      <svg viewBox="0 0 720 280" role="img" aria-label="Authenticated API request flow diagram">
        <defs>
          <marker id="ar" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
            <path d="M0,0 L8,3 L0,6" fill="currentColor"/>
          </marker>
        </defs>
        <rect x="20" y="120" width="120" height="60" rx="8" fill="rgba(64,128,200,0.12)" stroke="rgba(64,128,200,1)" stroke-width="1.5"/>
        <text x="80" y="155" text-anchor="middle" font-size="13" fill="currentColor">Client</text>
        <line x1="140" y1="150" x2="200" y2="150" stroke="currentColor" stroke-width="1.5" marker-end="url(#ar)"/>
        <rect x="200" y="120" width="120" height="60" rx="8" fill="rgba(220,140,80,0.12)" stroke="rgba(220,140,80,1)" stroke-width="1.5"/>
        <text x="260" y="155" text-anchor="middle" font-size="13" fill="currentColor">API Gateway</text>
        <line x1="320" y1="150" x2="380" y2="150" stroke="currentColor" stroke-width="1.5" marker-end="url(#ar)"/>
        <rect x="380" y="120" width="120" height="60" rx="8" fill="rgba(150,200,100,0.12)" stroke="rgba(150,200,100,1)" stroke-width="1.5"/>
        <text x="440" y="155" text-anchor="middle" font-size="13" fill="currentColor">Cache</text>
        <line x1="500" y1="150" x2="560" y2="150" stroke="currentColor" stroke-width="1.5" marker-end="url(#ar)"/>
        <rect x="560" y="120" width="140" height="60" rx="8" fill="rgba(160,120,200,0.12)" stroke="rgba(160,120,200,1)" stroke-width="1.5"/>
        <text x="630" y="155" text-anchor="middle" font-size="13" fill="currentColor">Primary store</text>
      </svg>
      <figcaption>Figure 1 &middot; Cache-first read path</figcaption>
    </figure>
    <aside class="diagram-legend">
      <strong>Layers:</strong>
      <span><span class="dot" style="background: rgba(64,128,200,1);"></span> Client</span>
      <span><span class="dot" style="background: rgba(220,140,80,1);"></span> API</span>
      <span><span class="dot" style="background: rgba(150,200,100,1);"></span> Cache</span>
      <span><span class="dot" style="background: rgba(160,120,200,1);"></span> Primary</span>
    </aside>
  </main>
"""

SHAPES.append(("diagram", "Request Flow Diagram", "copy-button", DIAGRAM_BODY))


def assemble(shape: str, title: str, components: str) -> str:
    """Run assemble-template.py and return the assembled HTML string."""
    cmd = [
        sys.executable,
        str(ASSEMBLE),
        "--shape",
        shape,
        "--title",
        title,
    ]
    if components:
        cmd.extend(["--components", components])
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return proc.stdout


def inject_body(html: str, body: str) -> str:
    """Replace the assembler's empty <header><main><footer> with our body content."""
    # The base-template.html has placeholders we replace.
    html = html.replace(
        "<header><!-- CONTENT: header --></header>\n  <main>\n    <!-- CONTENT -->\n  </main>\n  <footer><!-- CONTENT: footer --></footer>",
        body.strip(),
    )
    return html


def validate(path: Path, shape: str) -> tuple[bool, str]:
    """Run validate-artifact.py; return (valid, output)."""
    cmd = [sys.executable, str(VALIDATE), str(path), "--shape", shape, "--json-compact"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode == 0, proc.stdout.strip()


def main() -> int:
    GALLERY.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    for shape, title, components, body in SHAPES:
        out_path = GALLERY / f"{shape}.html"
        html = assemble(shape, title, components)
        html = inject_body(html, body)
        out_path.write_text(html, encoding="utf-8")
        valid, output = validate(out_path, shape)
        status = "OK" if valid else "FAIL"
        print(f"[{status}] {shape:12s} -> {out_path.name}")
        if not valid:
            print(f"        {output}")
            failures.append(shape)

    print(f"\n{len(SHAPES) - len(failures)}/{len(SHAPES)} valid")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
