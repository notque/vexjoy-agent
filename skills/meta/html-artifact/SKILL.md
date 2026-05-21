---
name: html-artifact
description: |
  Generate rich self-contained HTML artifacts instead of markdown. Auto-detects
  artifact shape (spec, code-review, prototype, report, editor, data-viz,
  diagram, deck) and loads shape-specific patterns. Bundles Birchline design system with 4 theme
  presets. Use for "make HTML", "as HTML", "HTML artifact", or auto-injected
  by router when output benefits from rich visualization.
user_invocable: true  # justification: users type "/html" directly for explicit
                      # HTML output; also auto-injected by /do router enhancement
command: /html
argument-hint: "[description of what to generate]"
routing:
  triggers:
    - HTML artifact
    - make HTML
    - as HTML
    - rich visualization
    - interactive document
    - HTML file
    - self-contained HTML
    - visual companion
  pairs_with:
    - pr-workflow
    - research-pipeline
    - planning
    - publish
  complexity: Medium
  category: meta
---

# /html - Self-Contained HTML Artifacts

Generate single self-contained `.html` files that replace markdown when the output needs color, interactivity, layout, or visualization. Auto-detect artifact shape from the request, load shape-specific patterns, generate, validate, deliver.

**Core constraint:** Every artifact is ONE `.html` file. All CSS in `<style>`, all JS in `<script>`. No CDN links, no frameworks, no build steps, no external dependencies. Works offline, opens in any browser.

---

## Instructions

### Overview

5-phase pipeline: DETECT SHAPE, LOAD CONTEXT, GENERATE, VALIDATE, DELIVER. Phase 1 classifies the request into one of 8 shapes via deterministic script. Phase 2 loads the Birchline design system plus shape-specific reference. Phase 3 dispatches a subagent to generate the HTML. Phase 4 validates structure. Phase 5 delivers the file path and offers browser preview. Phase 6 EXPORT (optional) renders to PDF when the user asks for one.

---

### Phase 1: DETECT SHAPE

Classify the user's request into one of 8 artifact shapes.

Run: `python3 skills/meta/html-artifact/scripts/detect-shape.py --request "{user_request}"`

The script outputs a shape name and confidence score.

| Shape | Trigger Signals | What It Produces |
|---|---|---|
| spec | plan, explore options, compare N approaches, brainstorm | Side-by-side grids, Pro/Con badges, SVG data-flow diagrams, risk tables |
| code-review | review PR, explain diff, annotate code, understand module | Diff rendering, severity colors, margin annotations, jump links |
| prototype | prototype, animation, tune, try options, component variants | Sliders, CSS var live update, animation sandbox, contact sheets |
| report | report, summarize, status update, explain how X works, incident | TL;DR box, collapsible sections, timeline, metric callouts, SVG diagrams |
| editor | reorder, triage, edit config, tune prompt, pick values | Drag-drop, kanban, toggle switches, split-pane, export buttons |
| data-viz | visualize, chart, dashboard, show data, trends | SVG charts, canvas, interactive tooltips, filter controls |
| diagram | diagram, flowchart, architecture, sequence, SVG, illustrate, figure | Inline SVG diagrams, annotated flowcharts, figure sheets, interactive node details |
| deck | slides, presentation, deck, talk, pitch | Arrow-key navigable slide deck, 16:9 aspect ratio, slide types, progress bar |

Gate: Shape detected with medium+ confidence.
-- because low-confidence classification produces artifacts that mix concerns and satisfy no shape well. Fallback to "report" (safest general-purpose shape) if confidence is low or ambiguous.

---

### Hybrid Shapes

Real content often combines two shapes — a report with embedded diagrams, a spec with data-viz charts. When `detect-shape.py` returns a primary shape with medium/high confidence but the request also contains signals for a secondary shape, use the hybrid pattern:

| Primary Shape | + Secondary | Result |
|---|---|---|
| report | + diagram | Report layout (TL;DR, collapsibles, TOC) with inline SVG diagrams between sections |
| report | + data-viz | Report layout with embedded SVG charts illustrating key metrics |
| spec | + diagram | Comparison grid with SVG flow diagrams showing each option's architecture |
| spec | + data-viz | Comparison grid with charts showing performance/cost per option |
| diagram | + report | Figure sheet with explanatory text sections between diagram groups |

**Detection:** After running `detect-shape.py`, check if the `secondary_shape` field is non-null. If so, load BOTH shape references in Phase 2.

**Generation rule:** Primary shape controls page layout (outer structure). Secondary shape provides embedded components (inner elements). The html-builder agent receives both shape patterns and uses primary for structure, secondary for visual elements within sections.

**Example:** "create a visual companion for my pipelines article with diagrams and explanations" → primary: `report` (explain, article), secondary: `diagram` (visual, diagrams). Load `shape-report-research.md` AND `shape-diagram-illustration.md`.

---

### Phase 2: ASSEMBLE TEMPLATE + LOAD CONTEXT

Two parallel steps: (A) run the template assembler to produce a pre-filled HTML skeleton, and (B) load principle-focused reference files for the builder agent.

**Step A -- Assemble template (deterministic):**

Run: `python3 skills/meta/html-artifact/scripts/assemble-template.py --shape {shape} --title "{title}" --components {components}`

The script reads CSS/JS from `templates/` and injects:
1. CSS reset (`templates/base-reset.css`)
2. Full theme tokens (`templates/themes/{theme}.css`)
3. Shape-specific layout CSS (`templates/shapes/{shape}.css`)
4. Component CSS + JS (`templates/components/{name}.{css,js}`)

Select components based on shape needs:

| Shape | Typical Components |
|---|---|
| spec | `tabs,copy-button,theme-toggle` |
| code-review | `collapsible,filter,keyboard-nav,theme-toggle` |
| prototype | `slider,copy-button,theme-toggle` |
| report | `collapsible,theme-toggle,copy-button` |
| editor | `drag-drop,filter,copy-button` |
| data-viz | `filter,theme-toggle` |
| diagram | `copy-button,theme-toggle` |
| deck | `keyboard-nav,theme-toggle` |

**Step B -- Load reference files (principles + guidance):**

**Always load:**
1. `references/design-system.md` -- Theme selection, token architecture, accessibility checklist, SVG conventions, anti-patterns
2. `references/interaction-patterns.md` -- Component descriptions, when-to-use guidance, accessibility rules, composition guide

**Load per detected shape:**

| Shape | Reference File | Key Content |
|---|---|---|
| spec | `references/shape-spec-exploration.md` | Layout descriptions, composition guide, common mistakes |
| code-review | `references/shape-code-review.md` | Severity system, interaction patterns, section ordering |
| prototype | `references/shape-design-prototype.md` | Control types, export requirements, layout patterns |
| report | `references/shape-report-research.md` | Section ordering, TL;DR placement, metric patterns |
| editor | `references/shape-custom-editor.md` | Editor types, export bar rules, anti-patterns |
| data-viz | `references/shape-data-visualization.md` | Chart types, coordinate system, color scales |
| diagram | `references/shape-diagram-illustration.md` | SVG construction rules, diagram types, interaction patterns |
| deck | `references/shape-slide-deck.md` | Slide types, navigation, print styles |

Gate: Template assembled + required references loaded.
-- because the template provides deterministic CSS/JS injection, and references provide the judgment guidance the builder needs.

---

### Phase 3: GENERATE

Dispatch the html-builder subagent with the pre-assembled template.

1. Read `agents/html-builder.md` for the subagent prompt
2. Dispatch with: pre-assembled template (from Step A), design system principles, interaction pattern guidance, shape-specific reference, user request
3. Agent fills in the content structure using CSS classes already defined in the template
4. Agent writes a single `.html` file to the project directory (or `/tmp/html-artifacts/` if no project context)

**Self-contained file constraints (inline here because they govern generation):**

| Constraint | Reason |
|---|---|
| All CSS in `<style>` tag | No external stylesheets -- file must work offline |
| All JS in `<script>` tag | No CDN imports -- no React, Vue, Tailwind CDN, Bootstrap CDN |
| Vanilla JS only | Single file, no build step, no transpilation |
| Must include `<title>` | Browser tab identification, validation requirement |
| Must include `<meta charset="utf-8">` | Consistent rendering across platforms |
| Must include `<meta name="viewport">` | Responsive on mobile/tablet |
| Semantic HTML sections | `<header>`, `<main>`, `<section>`, `<footer>` for structure |
| SVG inline, not `<img src>` | No external file references |
| Max 500KB file size | Keeps generation time reasonable, prevents bloated inline assets |

Constraint: No framework boilerplate.
-- because React/Vue/Svelte require build steps and external imports that violate the single-file self-contained requirement. Vanilla JS handles all 8 shapes adequately.

Constraint: Generate HTML directly, never generate markdown then convert.
-- because markdown-to-HTML conversion loses the shape-specific layout, interactivity, and visual structure that justifies using HTML in the first place.

Gate: `.html` file exists on disk.
-- because Phase 4 validation reads the file; a missing file means generation failed silently.

---

### Phase 4: VALIDATE

Run deterministic validation on the generated file.

Run: `python3 skills/meta/html-artifact/scripts/validate-artifact.py {html_file_path}`

The script checks:

| Check | Fails When |
|---|---|
| Valid HTML structure | Missing `<html>`, `<head>`, or `<body>` |
| No external dependencies | Any `src=` or `href=` pointing to external URLs |
| Has `<title>` | Missing or empty `<title>` tag |
| Has charset meta | Missing `<meta charset>` |
| Has viewport meta | Missing viewport meta tag |
| File size under 500KB | Excessive inline assets or animation keyframes |
| No broken internal refs | `href="#id"` pointing to nonexistent `id` attributes |

Gate: All validation checks pass.
-- because an HTML file with external dependencies fails offline, missing meta tags render inconsistently across browsers, and missing structure breaks accessibility.

**If validation fails:** Read the specific failures from script output, fix the identified issues in the HTML file, re-run validation. Maximum 3 fix attempts before showing the user the remaining issues and asking for guidance.

---

### Phase 5: DELIVER

1. Print the absolute file path
2. Print a 1-line summary of what was generated (shape + key features)
3. Ask user: "Open in browser?"
4. If yes: run `open {file}` (macOS) or `xdg-open {file}` (Linux)

Constraint: Detect headless/SSH environments before offering browser open.
-- because `xdg-open` fails without a display server, producing confusing errors. Check `$DISPLAY` on Linux or `$SSH_TTY` presence. If headless, print path only and skip the open offer.

---

### Phase 6: EXPORT (optional)

Render the generated HTML to PDF. Opt-in only — HTML stays the default deliverable.

Fires when the user message contains any of: `"PDF"`, `"export PDF"`, `"make a PDF"`, `"as PDF"`, `"send as PDF"`, `"save as PDF"`, `"PDF version"`, `"PDF export"`. Without one of those signals, this phase stays dormant.

Runs:

```bash
python3 skills/meta/html-artifact/scripts/to-pdf.py \
    --input <generated.html> \
    --output <generated.pdf> \
    --json
```

The script auto-detects shape from `<body data-shape="...">` (the assembler adds it in Phase 2). Page size, orientation, and margins come from a per-shape map: deck renders 13.333in × 7.5in landscape with no margin; spec, code-review, prototype, data-viz, and diagram render Letter landscape; report and editor render Letter portrait. Falls back to Letter portrait when shape is unknown.

Delivers both file paths to the user. The JSON output reports `{"output", "page_count", "shape", "bytes"}` — `page_count` reflects slide count for decks, 0 otherwise.

If Playwright is unavailable, exit code 2 surfaces install instructions: `pip install -e ".[pdf]" && playwright install chromium`. Pass that hint along to the user instead of failing silently.

See `references/pdf-export.md` for the full page-size table, troubleshooting (font fallback, image timing, install failures), and per-shape print stylesheet inventory.

---

## Error Handling

| Error | Cause | Solution |
|---|---|---|
| detect-shape.py returns low confidence | Ambiguous request mapping to multiple shapes | Fall back to "report" shape -- safest general-purpose format |
| Generated HTML has external dependencies | Builder included CDN links or external `src` refs | Regenerate with explicit constraint: "no external deps, all CSS/JS inline" |
| File exceeds 500KB | Excessive inline SVGs or animation keyframes | Simplify SVG paths, reduce keyframe count, compress data |
| Browser won't open | No display server (headless, SSH, WSL without WSLg) | Print path only, suggest `scp` or `python3 -m http.server` |
| Validation fails repeatedly (3+ attempts) | Structural issue the builder cannot self-correct | Show validation output to user, ask for guidance |
| Shape misclassified | Auto-detection picked wrong shape for request | User overrides with `/html --shape=<name> <request>` |

---

## Preferred Patterns

### Pattern 1: CDN and Framework Imports

**What it looks like:** `<link href="https://cdn.jsdelivr.net/...">` or `<script src="https://unpkg.com/react@18/...">` in the generated HTML.

**Why wrong:** Breaks the self-contained contract. File fails offline, introduces version drift, adds weight the user didn't ask for.

**Do instead:** Inline all CSS in `<style>`. Write vanilla JS in `<script>`. The Birchline design system in `references/design-system.md` provides the full token set.

### Pattern 2: Markdown-to-HTML Conversion

**What it looks like:** Generating a markdown document first, then running it through a converter or wrapping it in `<pre>` tags.

**Why wrong:** Loses shape-specific layout, interactivity, SVG diagrams, and responsive grid structures. Produces "markdown in a browser" instead of a native HTML artifact.

**Do instead:** Generate HTML directly using shape-specific patterns from references. The HTML structure IS the output format, not a rendering layer on top of text.

### Pattern 3: Monolithic Unstructured HTML

**What it looks like:** One giant `<div>` with inline styles on every element, no semantic structure, no comments.

**Why wrong:** Unreadable source, hard to debug, impossible for the user to modify. Accessibility tools cannot navigate it.

**Do instead:** Use semantic HTML (`<header>`, `<main>`, `<section>`, `<footer>`). Define CSS classes in `<style>`. Add section comments. Group related elements logically.

### Pattern 4: Over-Engineering Simple Requests

**What it looks like:** Generating a full interactive dashboard when the user asked for a simple comparison table.

**Why wrong:** 2-4x generation time for features the user didn't request. Complexity without value.

**Do instead:** Match artifact complexity to request complexity. A comparison of 3 options needs a grid with cards, not a filterable dashboard with animations.

---

## Anti-Rationalization

| Rationalization | Why Wrong | Required Action |
|---|---|---|
| "Markdown is fine for this" | If shape detection triggered, the request has visual/interactive needs markdown can't serve | Generate HTML; user opts out with "as markdown" |
| "I'll add Tailwind CDN for faster styling" | Breaks self-contained requirement, fails offline | Use Birchline tokens from design-system.md |
| "The HTML looks right, skip validation" | Visual inspection misses missing meta tags, broken internal links, external deps | Run validate-artifact.py every time |
| "Report shape works for everything" | Each shape has distinct layout and interaction patterns; report is a fallback, not a default | Use the detected shape; report only when confidence is genuinely low |

---

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| Any html-artifact invocation | `references/design-system.md` | Theme selection, token architecture, accessibility, anti-patterns |
| Any html-artifact invocation | `references/interaction-patterns.md` | Component descriptions, when-to-use, accessibility rules |
| Shape = spec | `references/shape-spec-exploration.md` | Layout descriptions, composition guide, common mistakes |
| Shape = code-review | `references/shape-code-review.md` | Severity system, interaction patterns, section ordering |
| Shape = prototype | `references/shape-design-prototype.md` | Control types, export requirements, layout patterns |
| Shape = report | `references/shape-report-research.md` | Section ordering, TL;DR placement, metric patterns |
| Shape = editor | `references/shape-custom-editor.md` | Editor types, export bar rules, anti-patterns |
| Shape = data-viz | `references/shape-data-visualization.md` | Chart types, coordinate system, color scales |
| Shape = diagram | `references/shape-diagram-illustration.md` | SVG construction rules, diagram types, interaction patterns |
| Shape = deck | `references/shape-slide-deck.md` | Slide types, navigation, print styles |
| Request mentions scroll, reveal, animate on scroll, progressive | `references/scrollytelling-patterns.md` | IntersectionObserver scroll animations, stagger, counters, progress bar |
| Request mentions PDF, export PDF, as PDF, PDF version | `references/pdf-export.md` | Phase 6 trigger conditions, page-size table, troubleshooting, install instructions |

---

## Shared Patterns

This skill uses:
- [Anti-Rationalization](../../shared-patterns/anti-rationalization-core.md) -- Prevents shortcut rationalizations
- [Verification Checklist](../../shared-patterns/verification-checklist.md) -- Pre-completion checks
- [Gate Enforcement](../../shared-patterns/gate-enforcement.md) -- Phase transitions

---

## Reference Files

- `references/design-system.md`: Theme selection, token architecture, accessibility checklist, SVG conventions, anti-patterns
- `references/interaction-patterns.md`: Component descriptions, when-to-use guidance, accessibility rules, composition guide
- `references/shape-spec-exploration.md`: Spec shape -- layout, composition guide, common mistakes
- `references/shape-code-review.md`: Code review shape -- severity system, interaction patterns, section ordering
- `references/shape-design-prototype.md`: Prototype shape -- control types, export requirements, layout patterns
- `references/shape-report-research.md`: Report shape -- section ordering, TL;DR placement, metric patterns
- `references/shape-custom-editor.md`: Editor shape -- editor types, export bar rules, anti-patterns
- `references/shape-data-visualization.md`: Data viz shape -- chart types, coordinate system, color scales
- `references/shape-diagram-illustration.md`: Diagram shape -- SVG construction rules, diagram types, interaction patterns
- `references/shape-slide-deck.md`: Deck shape -- slide types, navigation, print styles
- `agents/html-builder.md`: Subagent prompt for HTML generation
- `references/scrollytelling-patterns.md`: IntersectionObserver scroll animation patterns
- `references/pdf-export.md`: Phase 6 EXPORT — trigger conditions, page-size table, print stylesheet inventory, troubleshooting
- `scripts/detect-shape.py`: Deterministic shape classification from user request
- `scripts/assemble-template.py`: Template assembly with theme, shape, and component CSS/JS injection
- `scripts/validate-artifact.py`: HTML structure and self-containment validation
- `scripts/to-pdf.py`: Playwright-based PDF rendering with per-shape page sizing
- `templates/`: CSS/JS template files organized by themes/, shapes/, components/, print/
