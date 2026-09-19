# Macrostructure Catalog

Named page structures. Pick exactly one `macro:*` id in Phase 1, before aesthetic
directions, and emit it as the `macrostructure` field in the spec. The macrostructure
is the categorical shape of the page — the order and role of its sections — chosen
before any color, type, or motion decision. Choosing structure first prevents every
page from collapsing into the same hero-then-three-cards template.

These are OUR names, deliberately distinct from any external catalog and from the
component terms in `vocabulary.md` (Hero, Full-bleed, Surface type). Those describe
parts; these describe whole-page skeletons.

**Lazy loading:** load only the one entry you picked, addressed by its heading anchor
(e.g. `#macrostat-led`). Reading the whole catalog wastes context — the chosen entry
carries every rule the build needs.

**Variety rule:** `validate_design.py` penalizes a macrostructure that matches either
of the last two projects (mirrors the font/palette step-down). Vary the structural
axis across consecutive builds, not just the colors.

| id | one-line when-to-use |
|---|---|
| `macro:stat-led` | a single number or proof point is the whole argument |
| `macro:long-document` | dense reading: docs, essays, legal, changelogs |
| `macro:bento` | many small features of unequal weight, shown at a glance |
| `macro:manifesto` | a point of view to argue, not a product to sell |
| `macro:split-hero` | product and its proof sit side by side, equally weighted |
| `macro:gallery-grid` | the work is visual and the images are the pitch |
| `macro:timeline` | sequence or progression is the core idea |
| `macro:comparison` | the decision is "this versus that" |
| `macro:single-focus` | one action, nothing else; capture or convert |
| `macro:dashboard` | an operator surface for live data and controls |

---

## macro:stat-led

**When to use:** one metric, result, or proof point carries the entire argument
(uptime, dollars saved, users served). Lead with the number, justify it after.

**Layout skeleton:**
1. Oversized stat block — the figure set larger than the headline, with a one-line claim under it.
2. Context strip — two or three supporting figures or a short sentence that frames the big number.
3. Evidence — how the number is earned (method, source, customer).
4. Narrative body — the story behind the figure, scannable.
5. Single call to action tied to the claim.

**Anti-cliche note:** the stat must be a real measured figure, set as type, not a
spinning odometer or count-up animation on scroll. A fabricated round number ("10x
faster") with no source reads as filler; show the actual figure and where it came from.

---

## macro:long-document

**When to use:** the value is in dense, sustained reading — documentation, an essay,
legal text, a detailed changelog. Comprehension and navigation beat visual drama.

**Layout skeleton:**
1. Title block — title, one-line summary, last-updated date.
2. Sticky table of contents (sidebar on wide screens, collapsible on mobile).
3. Body sections with stable heading anchors and generous measure (60-75ch).
4. Inline asides or callouts for warnings and tips.
5. Prev/next or related-document footer.

**Anti-cliche note:** resist breaking a reading page into floating cards or a grid.
Long-form reading wants one calm column with strong typographic hierarchy, not a
dashboard of boxes. Line length and vertical rhythm do the work here.

---

## macro:bento

**When to use:** several features of unequal importance, shown together so the eye
grasps the whole offering at a glance. The grid itself communicates relative weight.

**Layout skeleton:**
1. Short framing headline.
2. Bento grid — tiles of mixed sizes; the largest tile holds the lead feature, smaller tiles hold secondary ones.
3. Each tile: one icon-or-visual, a short label, one sentence. One job per tile.
4. Single closing action below the grid.

**Anti-cliche note:** vary tile sizes to express priority — a uniform grid of equal
cards is the templated look this structure exists to avoid. If every tile is the same
size, it is a card grid, not a bento. Give the lead feature visibly more room.

---

## macro:manifesto

**When to use:** there is a point of view to argue, a stance to take, a belief to
state — not a product to demo. Editorial weight over conversion mechanics.

**Layout skeleton:**
1. Statement — a single bold claim, full width, set large.
2. Argument sections — short numbered or titled positions, each one paragraph.
3. Pull quotes or emphasized lines that carry the through-line.
4. Signature or attribution.
5. One quiet action (subscribe, read more) — low-pressure.

**Anti-cliche note:** keep chrome minimal. Manifestos lose force when wrapped in
product-marketing furniture (badge rows, logo walls, "trusted by"). The words are the
design; let typography and whitespace carry the conviction.

---

## macro:split-hero

**When to use:** the product and its proof deserve equal weight in the first viewport —
a screenshot beside the pitch, a demo beside the claim. Neither dominates.

**Layout skeleton:**
1. Two-column first viewport: left holds headline, subhead, action; right holds the product visual or live demo.
2. Below the fold: alternating split rows, each pairing one claim with one supporting visual.
3. Proof band — logos or a single testimonial, full width.
4. Closing action.

**Anti-cliche note:** the right-hand visual must be real product, not a generic
floating-laptop mockup or abstract gradient blob. A split hero with a stock device
frame and placeholder UI signals the page has nothing real to show.

---

## macro:gallery-grid

**When to use:** the work is inherently visual — photography, design, art, physical
product — and the images themselves are the argument. Text is caption, not pitch.

**Layout skeleton:**
1. Minimal title bar — name and one line, nothing more.
2. Image grid or masonry — the dominant element; let images run large.
3. Optional filter or category strip.
4. Per-item detail on click or hover — title, short note.
5. Contact or inquiry action in the footer.

**Anti-cliche note:** let the images breathe at full strength; avoid burying them under
heavy overlays, uniform hover-zoom, or text scrims on every tile. If the grid needs
explanatory copy on each image to make sense, the images are not carrying their job.

---

## macro:timeline

**When to use:** sequence or progression is the core idea — a roadmap, a history, a
process, a journey. The order of events is the message.

**Layout skeleton:**
1. Framing headline naming the span (years, stages, steps).
2. Spine — a vertical or horizontal axis with dated or numbered nodes.
3. Each node: a moment with a short title, one-line description, optional visual.
4. Direction is unmistakable (top-to-bottom or left-to-right, never both at once).
5. Closing node that points at the present or the next step.

**Anti-cliche note:** the sequence must carry real meaning — dates, ordered stages,
causal steps. A timeline used to decorate unordered features (where the order is
arbitrary) misleads the reader; use `macro:bento` for unordered features instead.

---

## macro:comparison

**When to use:** the reader's decision is "this versus that" — plans, us-versus-them,
before-and-after. The structure exists to make the difference legible.

**Layout skeleton:**
1. Headline naming the choice.
2. Comparison table or paired columns — shared rows, one column per option.
3. Each row is one dimension; differences are visually marked, not just listed.
4. A recommended or highlighted option, clearly but fairly indicated.
5. Action per option.

**Anti-cliche note:** keep the comparison honest. A table engineered so one column wins
every row (strawman competitor, cherry-picked rows) reads as manipulative and erodes
trust. Show real trade-offs; a fair comparison persuades better than a rigged one.

---

## macro:single-focus

**When to use:** exactly one action matters — sign up, download, book, subscribe.
Everything on the page serves that one conversion; nothing competes with it.

**Layout skeleton:**
1. One headline stating the single promise.
2. One supporting line.
3. One form or one button — the only interactive focus.
4. Minimal proof (one line, one logo row) only if it lifts conversion.
5. No secondary navigation that leads away.

**Anti-cliche note:** resist adding a second competing call to action or a full nav bar
— they leak attention from the one job. If a second action feels necessary, the page is
probably trying to be two pages; split it or pick the one action that matters most.

---

## macro:dashboard

**When to use:** an operator surface — live data, controls, status. Function over
persuasion. Follows app rules, not landing-page rules (see `app-vs-landing-rules.md`).

**Layout skeleton:**
1. Top bar — product, primary context switcher, account.
2. Left navigation — sections of the app.
3. Main region — data tables, charts, or the primary work surface, dense but readable.
4. Detail panel or drawer for the selected item.
5. Status and system feedback in a consistent, quiet location.

**Anti-cliche note:** apply Linear-style restraint — calm surfaces, few colors, strong
typography, tight spacing. Decorative gradients, marketing-style hero blocks, and card
mosaics belong on landing pages; on a dashboard they add noise and hide the data the
operator came for.
