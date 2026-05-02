---
name: pptx-generator
description: "PPTX presentation generation with visual QA: slides, pitch decks."
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
routing:
  triggers:
    - presentation
    - powerpoint
    - pptx
    - slide deck
    - pitch deck
    - slides
    - create slides
    - generate presentation
    - make a deck
    - conference talk slides
  pairs_with:
    - workflow
    - gemini-image-generator
  complexity: Medium-Complex
  category: content-generation
---

# PPTX Presentation Generator

6-phase pipeline: content decisions (LLM) → slide construction (script) → visual validation (fresh-eyes subagent). Separates generation from QA to prevent rationalizing away visual defects.

---

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| tasks related to this reference | `anti-ai-slide-rules.md` | Loads detailed guidance from `anti-ai-slide-rules.md`. |
| tasks related to this reference | `dependencies.md` | Loads detailed guidance from `dependencies.md`. |
| tasks related to this reference | `design-system.md` | Loads detailed guidance from `design-system.md`. |
| errors, error handling | `error-handling.md` | Loads detailed guidance from `error-handling.md`. |
| example-driven tasks | `examples.md` | Loads detailed guidance from `examples.md`. |
| checklist-driven work | `qa-checklist.md` | Loads detailed guidance from `qa-checklist.md`. |
| tasks related to this reference | `script-reference.md` | Loads detailed guidance from `script-reference.md`. |
| tasks related to this reference | `slide-layouts.md` | Loads detailed guidance from `slide-layouts.md`. |

## Instructions

### Phase 1: GATHER

**Goal**: Collect content, determine structure and presentation type.

**Step 1: Parse the user request**

Extract: topic, audience (executives/engineers/students/general), tone (formal/casual/technical/inspirational), slide count (default 8-12), presentation type (pitch deck, tech talk, status update, educational, general).

**Step 2: Extract content**

- Source material provided: extract key points, data, quotes; organize into sections; map content to slide types (data→table, insight→quote, comparison→two-column)
- No source material: develop outline with user via clarifying questions
- Existing .pptx template: read with python-pptx, plan modifications

**Step 3: Determine slide structure**

Follow layout rhythm from `references/slide-layouts.md`:

| Deck Size | Rhythm Pattern |
|-----------|----------------|
| Short (5-8) | Title, Content, Content, Two-Column, Content, Closing |
| Medium (8-12) | Title, Content, Content, Quote, Section, Content, Two-Column, Content, Closing |
| Long (12+) | Title, Content, Content, Quote, Section, Content, Image+Text, Content, Section, Two-Column, Table, Content, Closing |

**GATE**: Content outline with 1+ key point per slide. Type identified. Count determined. If content too thin, suggest smaller deck.

---

### Phase 2: DESIGN

**Goal**: Select palette, produce slide map, get user approval before generation. Design changes after generation require full regeneration.

**Step 1: Select color palette** (from `references/design-system.md`)

| Presentation Type | Recommended Palette | Fallback |
|-------------------|--------------------|---------|
| Business / Finance | Corporate | Minimal |
| Engineering / Dev talk | Tech | Minimal |
| Creative / Workshop | Warm | Sunset |
| Healthcare / Sustainability | Ocean | Forest |
| Dark theme keynote | Midnight | Tech |
| Environmental / Nonprofit | Forest | Ocean |
| Startup / Energy | Sunset | Warm |
| Unknown / General | Minimal | Corporate |

User preference overrides. Default: **Minimal**.

**Step 2: Plan layout rhythm**

Available layouts: `title`, `section`, `content`, `two_column`, `image_text`, `quote`, `table`, `closing`. See `references/slide-layouts.md`.

Rules:
- Max 3 consecutive same-type slides -- identical layouts are the #1 AI-slide tell
- 10+ slide decks: at least 3 distinct layout types
- Break repetition with quote, two-column, or section divider

**Step 3: Produce the slide map**

JSON array, one element per slide. Supported types and required fields:
- `title`: `title`, `subtitle`
- `content`: `title`, `bullets` (max 6 items, max 10 words each)
- `two_column`: `title`, `left` (header + bullets), `right` (header + bullets)
- `quote`: `quote`, `attribution`
- `table`: `title`, `headers`, `rows`
- `section`: `title`
- `closing`: `title`, `subtitle`

**Step 4: Validate against anti-AI rules** (`references/anti-ai-slide-rules.md`)

- [ ] 2-3+ distinct layout types
- [ ] No 4+ consecutive same-layout slides
- [ ] Max 6 bullets, 10 words each
- [ ] Title first, closing last
- [ ] Section dividers before new sections (8+ slide decks)

**Step 5: Present slide map for user approval**

Show numbered list with layout type, title, bullet count. Get explicit approval before generation.

**GATE**: User approves slide map.

---

### Phase 3: GENERATE

**Goal**: Run the deterministic script to produce the .pptx file.

**Step 1: Check dependencies**

```bash
python3 -c "from pptx import Presentation; print('python-pptx OK')"
```

If missing: `pip install python-pptx Pillow`

**Step 2: Write slide map and design config to JSON**

Save to `/tmp/slide_map.json` and `/tmp/design_config.json`. Use absolute paths. See `references/script-reference.md` for format.

**Step 3: Run generation**

```bash
python3 /path/to/skills/pptx-generator/scripts/generate_pptx.py \
  --slide-map /tmp/slide_map.json \
  --design /tmp/design_config.json \
  --output /absolute/path/to/output.pptx
```

Exit codes: 0=success, 1=missing python-pptx, 2=invalid input, 3=generation failed.

**Generation constraints**:
- **Blank Layout Only**: `slide_layouts[6]` -- template layouts inherit unpredictable formatting
- **Safe Fonts Only**: Calibri and Arial -- custom fonts break on other machines
- **Widescreen**: 16:9 (13.333 x 7.5 inches)

**Step 4: Structural validation**

```bash
python3 /path/to/skills/pptx-generator/scripts/validate_structure.py \
  --input /absolute/path/to/output.pptx \
  --slide-map /tmp/slide_map.json
```

Validates: slide count, text content per slide, title slide exists, no empty slides.

**GATE**: .pptx exists with non-zero size AND validation passes. Max 2 retries before escalating.

---

### Phase 4: CONVERT (Requires LibreOffice)

**Goal**: Convert .pptx to per-slide PNGs for visual QA. The QA subagent needs rendered images -- visual defects are only visible in rendered output.

**Step 1: Check LibreOffice**

```bash
soffice --version 2>/dev/null
```

If unavailable: skip Phase 5, proceed to Phase 6, note visual QA was skipped.

**Step 2: Convert**

```bash
python3 /path/to/skills/pptx-generator/scripts/convert_slides.py \
  --input /absolute/path/to/output.pptx \
  --output-dir /tmp/pptx_qa_images/ \
  --dpi 150
```

Exit codes: 0=success, 1=no LibreOffice, 2=conversion failed, 3=invalid input.

**Step 3: Verify** one PNG per slide exists. Note any missing.

**GATE**: (a) one PNG per slide, proceed to Phase 5, or (b) LibreOffice unavailable, skip to Phase 6.

---

### Phase 5: QA (Visual Inspection Loop)

**Goal**: Fresh-eyes subagent inspects rendered slides. Fix and re-render up to 3 times. Max 3 because persistent issues indicate a design problem, not implementation.

**Step 1: Dispatch QA subagent**

Launch via Task tool with slide PNGs, slide map, and `references/qa-checklist.md`. Evaluates: text readability, layout alignment, color usage, content accuracy, anti-AI violations, structural checks.

**Step 2: Process QA results**

- PASS: proceed to Phase 6
- FAIL (Blocker/Major): fix slide map, re-run Phases 3-4, re-dispatch QA. Minor issues reported only.

Track: `QA Iteration N/3: X issues (Y Blocker, Z Major)`

**GATE**: QA PASS, or 3 iterations exhausted. Remaining issues go in output report.

---

### Phase 6: OUTPUT

**Goal**: Deliver .pptx, report, clean up.

**Step 1**: Copy final .pptx to user-specified path or `./[topic-slug].pptx`.

**Step 2**: Print summary: file path, slide count, palette, format (16:9), file size, slide map, QA result, remaining issues. See `references/script-reference.md` for template.

**Step 3**: Remove `/tmp/slide_map.json`, `/tmp/design_config.json`, `/tmp/pptx_qa_images/`.

---

## Error Handling

Full details: `references/error-handling.md`. Common errors:
- `python-pptx` missing: `pip install python-pptx Pillow`
- LibreOffice missing: skip Phases 4-5, note in report
- Slide map JSON invalid: check `type` field on every slide
- QA loop > 3: stop, report remaining issues, deliver best version

---

## References

- `references/design-system.md` -- palettes, typography, spacing
- `references/slide-layouts.md` -- 8 layouts with JSON examples and rhythm guidelines
- `references/anti-ai-slide-rules.md` -- 10 anti-patterns with detection criteria
- `references/qa-checklist.md` -- visual QA criteria, severity levels, output format
- `references/script-reference.md` -- CLI args, config format, exit codes
- `references/dependencies.md` -- required/optional packages
- `references/examples.md` -- 3 worked examples

### Complementary Skills
- `skills/workflow/references/research-to-article.md` -- research feeds slide content
- `skills/gemini-image-generator/SKILL.md` -- generate images for slides
