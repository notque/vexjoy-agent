# html-artifact Evaluation Cases

Repeatable evaluation cases for the html-artifact skill. Used by `skill-eval` to measure shape detection accuracy, generation quality, and routing correctness.

---

## Should-Trigger Prompts

Requests that MUST activate html-artifact and produce the expected shape.

| # | Prompt | Expected Shape | Key Assertion |
|---|---|---|---|
| 1 | "Explore 3 different approaches to implement rate limiting" | spec | Comparison grid with 3 columns, pro/con per option, recommendation section |
| 2 | "Help me review PR #42, annotate the diff" | code-review | Diff with line numbers, severity-colored annotations, file jump links |
| 3 | "Prototype a checkout button animation with sliders to tune it" | prototype | Interactive sliders, live preview, export/copy button |
| 4 | "Write a weekly status report for the team" | report | TL;DR box at top, collapsible sections, metric callouts if applicable |
| 5 | "I need to reprioritize these 30 tickets across Now/Next/Later/Cut" | editor | Drag-drop or form controls, state persistence, export buttons (Markdown + JSON + Prompt) |
| 6 | "Show me test coverage trends over the last 6 months" | data-viz | SVG chart, legend, tooltips, filter controls |
| 7 | "Make an HTML artifact explaining how our auth flow works" | report | Explicit trigger via "HTML artifact"; report shape for explanatory content |
| 8 | "Create an interactive feature flag editor" | editor | Form-based editing, toggle switches, export buttons |

---

## Should-NOT-Trigger Prompts

Requests that must NOT activate html-artifact.

| # | Prompt | Why Not | Correct Route |
|---|---|---|---|
| 1 | "Fix the bug in auth.ts" | Code fix, not visualization | typescript-frontend-engineer |
| 2 | "Run the tests" | Test execution, not output generation | test runner / quick |
| 3 | "Write this as markdown" | Explicit markdown request | Standard markdown output |
| 4 | "Create an interactive essay about caching" | Full Vite+React project | interactive-essay skill |
| 5 | "Make a slide deck for the conference" | Presentation deck | frontend-slides skill |
| 6 | "Build a React component for the login page" | Framework component | typescript-frontend-engineer |

---

## Behavioral Expectations Per Shape

### spec

| Must Have | Must NOT Have |
|---|---|
| N-column comparison grid (2-5 columns) | External dependencies or build steps |
| Pro/Con section per option | Generic "Option A / Option B" without substance |
| Metadata badges (complexity, risk, timeline) | Hardcoded colors or spacing |
| Recommendation section at bottom | Missing mobile layout (stacked columns) |

### code-review

| Must Have | Must NOT Have |
|---|---|
| Diff with line numbers | Broken syntax highlighting |
| Severity-colored annotations (critical/warning/info) | External CDN for highlight.js or similar |
| File navigation / jump links | Missing line number alignment |
| Risk map overview | Diff without context lines |

### prototype

| Must Have | Must NOT Have |
|---|---|
| Interactive controls (sliders, selectors, toggles) | Missing export/copy button |
| Live preview that updates with controls | Controls that do not update preview |
| Export/Copy button | Framework imports |
| Responsive layout | Hardcoded animation values without control |

### report

| Must Have | Must NOT Have |
|---|---|
| TL;DR box visible without scrolling | Wall of unstyled text |
| Collapsible sections (default collapsed) | All sections expanded by default |
| Metric callouts for key numbers (if applicable) | Numbers buried in paragraphs |
| Table of contents with jump links | Missing section structure |

### editor

| Must Have | Must NOT Have |
|---|---|
| Drag-drop or form-based editing | No export mechanism |
| State persistence (survives re-ordering) | State loss on interaction |
| Export buttons: Markdown + JSON + Prompt (min 2 formats) | Single export format only |
| Visual feedback on state changes | Silent state changes |

### data-viz

| Must Have | Must NOT Have |
|---|---|
| SVG charts (unless >1000 data points) | Canvas for simple datasets |
| Legend with labels | External charting libraries (Chart.js, D3 CDN) |
| Tooltips on data points | Charts without axis labels |
| Filter controls (if multiple series) | Static image with no interactivity |

---

## Quality Checks (All Shapes)

These checks apply to every generated artifact regardless of shape.

| Check | Method | Pass Criterion |
|---|---|---|
| Structural validity | `validate-artifact.py` | Exit code 0 |
| File size | `validate-artifact.py` | < 500KB |
| No external deps | `validate-artifact.py` | No `src=` or `href=` to external URLs |
| Has `<title>` | `validate-artifact.py` | Non-empty, descriptive title |
| Has charset meta | `validate-artifact.py` | `<meta charset="utf-8">` present |
| Has viewport meta | `validate-artifact.py` | `<meta name="viewport">` present |
| Responsive | Manual / browser test | Renders at 375px and 1440px without horizontal scroll |
| Keyboard accessible | Manual / browser test | Tab through all interactive elements |
| No console errors | Browser DevTools | Zero errors on load and interaction |
| Design tokens used | Grep source | CSS custom properties, not hardcoded values |
| Reduced motion | Grep source | `prefers-reduced-motion` media query present |

---

## Shape Detection Accuracy

Test `detect-shape.py` independently with these inputs:

| Input | Expected | Notes |
|---|---|---|
| "explore 3 auth approaches" | spec | Primary signal: "explore", "approaches" |
| "compare rate limiting strategies" | spec | Primary signal: "compare" |
| "review the diff for PR 42" | code-review | Primary signal: "review", "diff", "PR" |
| "annotate this code change" | code-review | Primary signal: "annotate", "code" |
| "prototype a button hover effect" | prototype | Primary signal: "prototype" |
| "tune the animation timing" | prototype | Primary signal: "tune" |
| "weekly team status update" | report | Primary signal: "status", "report" |
| "explain how the auth flow works" | report | Primary signal: "explain" |
| "triage these 20 bugs by priority" | editor | Primary signal: "triage", "priority" |
| "reorder the feature backlog" | editor | Primary signal: "reorder" |
| "chart our deploy frequency" | data-viz | Primary signal: "chart" |
| "show error rate trends" | data-viz | Primary signal: "trends" |
