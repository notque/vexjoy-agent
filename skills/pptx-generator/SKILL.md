---
name: pptx-generator
description: "PPTX presentation generation with visual QA: slides, pitch decks."
version: 1.0.0
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
    - workflow-orchestrator
    - research-to-article
    - gemini-image-generator
  complexity: Medium-Complex
  category: content-generation
---

# PPTX Presentation Generator

## Overview

This skill generates polished PowerPoint decks through a 6-phase pipeline that separates content decisions (LLM) from slide construction (deterministic script) from visual validation (fresh-eyes subagent). The core principle: **"Slides are visual documents, not text dumps. Generate mechanically, validate visually."**

This separation prevents the common failure mode where the generator rationalizes away visual defects it introduced. The visual QA subagent has zero generation context and sees slides as viewers would.

---

## Instructions

### Phase 1: GATHER

**Goal**: Collect content, determine presentation structure, identify the presentation type.

**Why this phase exists**: Jumping straight to slide design without understanding the content produces a generic deck that doesn't serve the audience. Gathering first ensures every slide has a purpose.

**Step 1: Parse the user request**

Extract from the user's input:
- **Topic**: What is the presentation about?
- **Audience**: Who will view it? (executives, engineers, students, general public)
- **Tone**: Formal, casual, technical, inspirational?
- **Slide count**: Explicit request or estimate from content volume. Default: 8-12 slides.
- **Presentation type**: Classify as one of:
  - **Pitch deck**: Investor/stakeholder persuasion
  - **Tech talk**: Engineering audience, architecture, code
  - **Status update**: Progress report, metrics, next steps
  - **Educational**: Teaching, workshop, tutorial
  - **General**: Does not fit above categories

**Step 2: Extract content**

If the user provides source material (document, outline, notes, article):
- Extract key points, data, and quotes
- Organize into logical sections
- Identify content that maps to specific slide types (data -> table, key insight -> quote, comparison -> two-column)

If no source material is provided:
- Work with the user to develop an outline
- Ask clarifying questions about scope and depth

If the user provides an existing .pptx as a template:
- Read it with python-pptx to understand the existing structure
- Plan which slides to modify vs. add

**Step 3: Determine slide structure**

Based on content volume and presentation type, plan the slide sequence. Follow the layout rhythm guidelines in `references/slide-layouts.md`:

| Deck Size | Rhythm Pattern |
|-----------|----------------|
| Short (5-8) | Title, Content, Content, Two-Column, Content, Closing |
| Medium (8-12) | Title, Content, Content, Quote, Section, Content, Two-Column, Content, Closing |
| Long (12+) | Title, Content, Content, Quote, Section, Content, Image+Text, Content, Section, Two-Column, Table, Content, Closing |

**GATE**: Content outline exists with at least 1 key point per planned slide. Presentation type identified. Slide count determined. If the user's content is too thin for the requested slide count, flag this and suggest a smaller deck rather than padding with filler.

---

### Phase 2: DESIGN

**Goal**: Select palette and typography, produce the slide map, get user approval before generation.

**Why this phase exists**: Design decisions made after generation are expensive -- they require regenerating the entire deck. Making them upfront and getting user approval saves iteration budget for visual fixes, not content rework.

**Step 1: Select color palette**

Use the palette selection heuristic from `references/design-system.md`:

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

If the user specifies a palette preference, use it. When in doubt, use **Minimal**.

**Step 2: Plan layout rhythm**

Select layout types for each slide. Use at least 2-3 distinct layout types to avoid the "AI-generated sameness" anti-pattern. See `references/slide-layouts.md` for all layout types.

Available layouts: `title`, `section` (divider), `content` (bullets), `two_column`, `image_text`, `quote` (callout), `table`, `closing`

Layout rhythm rules:
- Use a different layout after 3 consecutive slides of the same type in a row. (Reason: Identical layouts are the most obvious AI-slide tell. Real presentations have visual rhythm with varied layouts.)
- For 10+ slide decks, use at least 3 distinct layout types
- Insert a different layout type (quote, two-column, section divider) to break repetition

**Step 3: Produce the slide map**

Create a JSON array where each element represents one slide:

```json
[
  {
    "type": "title",
    "title": "Presentation Title",
    "subtitle": "Subtitle or author"
  },
  {
    "type": "content",
    "title": "Slide Headline",
    "bullets": ["Point 1", "Point 2", "Point 3"]
  },
  {
    "type": "two_column",
    "title": "Comparison",
    "left": {"header": "Option A", "bullets": ["Pro 1", "Pro 2"]},
    "right": {"header": "Option B", "bullets": ["Pro 1", "Pro 2"]}
  },
  {
    "type": "quote",
    "quote": "Key insight or memorable statement",
    "attribution": "Speaker Name"
  },
  {
    "type": "table",
    "title": "Data Overview",
    "headers": ["Column A", "Column B", "Column C"],
    "rows": [["r1c1", "r1c2", "r1c3"], ["r2c1", "r2c2", "r2c3"]]
  },
  {
    "type": "closing",
    "title": "Thank You",
    "subtitle": "contact@example.com"
  }
]
```

**Step 4: Validate the slide map against anti-AI rules**

Before presenting to the user, check:
- [ ] At least 2-3 distinct layout types used (not all `content`)
- [ ] No more than 3 consecutive slides with the same layout
- [ ] Max 6 bullets per content slide, max 10 words per bullet (Reason: 9 bullets is a document paragraph, not a slide. Readability degrades sharply past 6.)
- [ ] Title slide is first, closing slide is last (if appropriate)
- [ ] Section dividers placed before new sections (for 8+ slide decks)

See `references/anti-ai-slide-rules.md` for the full checklist.

**Step 5: Present slide map for user approval**

Show the user the planned deck structure:
```
SLIDE MAP (10 slides, Corporate palette):

  1. [Title] "Q4 Revenue Analysis"
  2. [Content] "Executive Summary" (4 bullets)
  3. [Content] "Revenue by Region" (5 bullets)
  4. [Quote] Key insight from CFO
  5. [Section] "Deep Dive: EMEA"
  6. [Two-Column] EMEA vs APAC comparison
  7. [Content] "Contributing Factors" (4 bullets)
  8. [Table] Quarterly figures
  9. [Content] "Recommendations" (3 bullets)
  10. [Closing] "Questions?"

Approve this structure, or suggest changes?
```

**GATE**: User approves the slide map. If the user requests changes, update the slide map and re-present. Get explicit user approval before proceeding to generation. Why: regeneration costs iteration budget that should be reserved for visual QA fixes.

---

### Phase 3: GENERATE

**Goal**: Execute the deterministic Python script to produce the .pptx file.

**Why this phase exists**: Slide construction is mechanical work -- given a slide map and design config, the output is deterministic. This belongs in a script, not in LLM-generated inline code. Scripts are testable, reproducible, and consistent. (Reason: Inline code is not testable, wastes tokens on boilerplate, and risks inconsistency. The script encapsulates palette application, layout selection, font sizing, spacing rules, and all design system constraints.)

**Step 1: Check dependencies**

```bash
python3 -c "from pptx import Presentation; print('python-pptx OK')"
```

If python-pptx is not installed, install it:
```bash
pip install python-pptx Pillow
```

**Step 2: Write the slide map and design config to JSON files**

Save the approved slide map and design config to temporary files (use absolute paths for all file arguments):

```bash
# Write slide map JSON to temp file
python3 -c "
import json
slide_map = [...]  # the approved slide map
with open('/tmp/slide_map.json', 'w') as f:
    json.dump(slide_map, f, indent=2)
"

# Write design config JSON
python3 -c "
import json
design = {'palette': 'corporate'}  # whichever palette was selected
with open('/tmp/design_config.json', 'w') as f:
    json.dump(design, f, indent=2)
"
```

**Step 3: Run the generation script**

```bash
python3 /path/to/skills/pptx-generator/scripts/generate_pptx.py \
  --slide-map /tmp/slide_map.json \
  --design /tmp/design_config.json \
  --output /absolute/path/to/output.pptx
```

Exit codes: 0 = success, 1 = missing python-pptx, 2 = invalid input, 3 = generation failed.

**Constraints applied during generation**:
- **Blank Layout Only**: Always use `slide_layouts[6]` (blank) as the base layout. Why: using template-specific layouts (title, content) inherits unpredictable formatting from whatever default template python-pptx ships. Blank gives us full control.
- **Safe Fonts Only**: Use Calibri and Arial exclusively. Why: presentations are shared documents. Custom fonts cause rendering failures on machines that lack them. Portability trumps aesthetics.
- **Widescreen Format**: 16:9 (13.333 x 7.5 inches). This is the universal modern presentation format.

**Step 4: Run structural validation**

```bash
python3 /path/to/skills/pptx-generator/scripts/validate_structure.py \
  --input /absolute/path/to/output.pptx \
  --slide-map /tmp/slide_map.json
```

This validates: slide count matches, each slide has text content, title slide exists, no empty slides.

**GATE**: .pptx file exists with non-zero size AND structural validation passes. If validation fails, diagnose the issue (usually a slide map JSON problem), fix, and re-run. Max 2 retries at this gate before escalating to the user.

---

### Phase 4: CONVERT (Requires LibreOffice)

**Goal**: Convert the .pptx to per-slide PNG images for visual QA.

**Why this phase exists**: The QA subagent cannot read .pptx files. It needs rendered images to evaluate visual quality -- text clipping, color contrast, alignment, and anti-AI violations are only visible in rendered output.

**Step 1: Check LibreOffice availability**

```bash
soffice --version 2>/dev/null
```

If LibreOffice is not installed:
- Log: "LibreOffice not available. Skipping visual QA, using structural validation only."
- Skip Phase 5 (QA) and proceed directly to Phase 6 (OUTPUT)
- Note in the output report that visual QA was skipped

**Step 2: Run the conversion script**

```bash
python3 /path/to/skills/pptx-generator/scripts/convert_slides.py \
  --input /absolute/path/to/output.pptx \
  --output-dir /tmp/pptx_qa_images/ \
  --dpi 150
```

Exit codes: 0 = success, 1 = no LibreOffice, 2 = conversion failed, 3 = invalid input.

**Step 3: Verify conversion output**

Check that one PNG exists per slide. If fewer PNGs than slides, some slides may have failed to render. Note which slides are missing.

**GATE**: Either (a) one PNG per slide exists, proceed to Phase 5, or (b) LibreOffice unavailable, skip to Phase 6 with a note. If conversion partially fails (some PNGs missing), proceed to QA with available images and note the gaps.

---

### Phase 5: QA (Visual Inspection Loop)

**Goal**: A fresh-eyes subagent inspects the rendered slides and identifies visual issues. Fix and re-render up to 3 times.

**Why a subagent**: The generating agent has context bias -- it "knows" what the slide should look like and will rationalize visual problems. A fresh-eyes subagent with zero generation context sees the slide as a viewer would. This is the same anti-bias pattern as the voice-validator: the generator and the validator must be separate.

**Why max 3 iterations**: If visual issues persist after 3 fix cycles, the design is wrong, not the implementation. Looping further produces diminishing returns and wastes context. (Reason: Stop iterating after 3 attempts. This signals that the design approach is wrong, not the implementation. More iterations burn context without convergence.)

**Step 1: Dispatch QA subagent**

Launch a subagent (via Task tool) with:
- The slide PNG images (one per slide)
- The original slide map for content comparison
- The QA checklist from `references/qa-checklist.md`

The subagent checks each slide against these categories:

1. **Text Readability**: Not clipped, not overlapping, sufficient contrast, adequate font size
2. **Layout and Alignment**: Consistent margins, aligned elements, visual balance
3. **Color Usage**: Palette consistency, max 3 colors per slide, adequate contrast
4. **Content Accuracy**: Titles and bullets match the slide map
5. **Anti-AI Violations**: All 10 rules from `references/anti-ai-slide-rules.md` (avoid accent lines under titles, gradient backgrounds, identical layouts, shadows on everything, rounded rectangles everywhere, clip art icons, gradient text)
6. **Structural Checks**: Slide count, title slide present, closing slide present

Subagent prompt structure:
```
You are a visual QA inspector for a PowerPoint presentation. You have ZERO
context about how these slides were generated. Evaluate each slide image
against the QA checklist.

For each slide, check:
1. Text readability (not clipped, not overlapping, adequate size, sufficient contrast)
2. Layout and alignment (consistent margins, aligned elements, visual balance)
3. Color usage (palette consistency, max 3 colors per slide)
4. Content accuracy (title matches expected, content present)
5. Anti-AI violations (accent lines under titles, gradient backgrounds, identical layouts,
   shadows on everything, rounded rectangles everywhere, clip art icons, gradient text)

Return per-slide results:
SLIDE QA RESULT: [PASS | FAIL]
Slides checked: N
Issues found: M

SLIDE 1: PASS | FAIL
  - [Category] Issue description
    FIX: Specific fix instruction
...
OVERALL: PASS | FAIL (N issues on M slides)
```

**Step 2: Process QA results**

If QA returns PASS: proceed to Phase 6.

If QA returns FAIL with Blocker or Major issues:
1. Parse the fix instructions
2. Modify the slide map JSON to address each issue (e.g., shorten a title, reduce bullet count, change layout type)
3. Re-run Phase 3 (GENERATE) and Phase 4 (CONVERT)
4. Re-dispatch the QA subagent

Severity levels:
- **Blocker**: Must fix (text unreadable, content missing, wrong slide order)
- **Major**: Should fix (alignment off, anti-AI violation, contrast issue)
- **Minor**: Report but report without requiring a fix cycle (slightly suboptimal spacing)

Only Blocker and Major issues trigger a fix iteration.

Track iteration count:
```
QA Iteration 1/3: 2 issues found (1 Blocker, 1 Major)
QA Iteration 2/3: 1 issue found (1 Minor)
QA Iteration 3/3: PASS (0 Blocker, 0 Major)
```

**GATE**: QA subagent returns PASS, OR 3 iterations exhausted. If iterations exhausted with remaining issues, include them in the output report. Stop after 3 iterations.

---

### Phase 6: OUTPUT

**Goal**: Deliver the final .pptx file with a summary report. Clean up intermediate files.

**Step 1: Move the final .pptx to the user's working directory**

Copy from temp location to a sensible output path:
- If user specified an output path, use it
- Otherwise: `./presentation.pptx` or `./[topic-slug].pptx`

**Step 2: Generate the output report**

```
===============================================================
 PRESENTATION GENERATED
===============================================================

 File: /absolute/path/to/presentation.pptx
 Slides: 10
 Palette: Corporate
 Format: 16:9 widescreen
 Size: 45,230 bytes

 Slide Map:
   1. [Title] "Q4 Revenue Analysis"
   2. [Content] "Executive Summary"
   3. [Content] "Revenue by Region"
   4. [Quote] CFO insight
   5. [Section] "Deep Dive: EMEA"
   6. [Two-Column] EMEA vs APAC
   7. [Content] "Contributing Factors"
   8. [Table] Quarterly figures
   9. [Content] "Recommendations"
  10. [Closing] "Questions?"

 QA Result: PASS (2 iterations, 3 issues fixed)

 Notes:
   - [any remaining minor issues or caveats]

===============================================================
```

**Step 3: Clean up intermediate files**

Remove:
- `/tmp/slide_map.json`
- `/tmp/design_config.json`
- `/tmp/pptx_qa_images/` directory (PNG renders and PDFs)

Keep only the final .pptx file. (Reason: Cleanup is a default behavior to remove intermediate files after final output.)

---

## Examples

### Example 1: Tech Talk from Outline
User says: "Create a 10-slide presentation about our new microservices architecture"
Actions:
1. GATHER: Topic = microservices migration, audience = engineering team, type = tech talk, 10 slides
2. DESIGN: Select Tech palette, build slide map with title, 6 content slides, 1 two-column (monolith vs micro), 1 section divider, closing. Present for approval.
3. GENERATE: Run `generate_pptx.py` with slide map and Tech palette
4. CONVERT: PPTX to PNGs via LibreOffice
5. QA: Subagent inspects 10 slide images, finds title text clipped on slide 4, fixes in iteration 2
6. OUTPUT: `microservices-architecture.pptx`, 10 slides, Tech palette, QA passed

### Example 2: Pitch Deck from Document
User says: "Turn this business plan into a pitch deck" (attaches document)
Actions:
1. GATHER: Extract key sections from business plan (problem, solution, market, traction, team, ask), type = pitch deck, 12 slides
2. DESIGN: Select Sunset palette for startup energy, build slide map with standard pitch structure. Present for approval.
3. GENERATE: Run script with slide map
4. CONVERT: PPTX to PNGs
5. QA: Subagent catches identical layout on 4 consecutive slides, fixes by inserting quote and two-column layouts
6. OUTPUT: `pitch-deck.pptx`, 12 slides, Sunset palette, QA passed after 2 iterations

### Example 3: Status Update (No LibreOffice)
User says: "Quick status update slides for the weekly standup, 5 slides"
Actions:
1. GATHER: Topic = weekly status, audience = team, type = status update, 5 slides
2. DESIGN: Select Minimal palette, build compact slide map. Present for approval.
3. GENERATE: Run script, structural validation passes
4. CONVERT: LibreOffice not available, skip visual QA
5. QA: Skipped
6. OUTPUT: `weekly-status.pptx`, 5 slides, Minimal palette, visual QA skipped

---

## Error Handling

### Error: python-pptx Not Installed
**Cause**: The `python-pptx` package is missing from the Python environment.
**Solution**: Run `pip install python-pptx Pillow`. This is a hard dependency -- the skill cannot function without it. Verify with `python3 -c "from pptx import Presentation; print('OK')"`.

### Error: LibreOffice Not Available
**Cause**: `soffice` binary not found on the system. Required for the visual QA loop (Phases 4-5).
**Solution**: This is a soft dependency. The skill degrades gracefully:
1. Log that visual QA is unavailable
2. Skip Phases 4-5
3. Rely on structural validation from `validate_structure.py`
4. Note in the output report that visual QA was skipped

Install with: `apt install libreoffice-impress` (Debian/Ubuntu) or `brew install --cask libreoffice` (macOS).

### Error: Slide Map JSON Invalid
**Cause**: Malformed JSON, missing `type` field, or unsupported layout type.
**Solution**:
1. Validate JSON syntax before passing to the script
2. Check that every slide object has a `type` field
3. Supported types: `title`, `section`, `content`, `two_column`, `quote`, `table`, `image_text`, `closing`
4. Unknown types fall back to `content` layout

### Error: Generated PPTX Empty or Corrupt
**Cause**: Script error during generation, typically from invalid slide data (null values, missing arrays).
**Solution**:
1. Run `validate_structure.py` to identify the specific failure
2. Check the slide map JSON for null or missing fields
3. Fix and re-generate. Max 2 retries before escalating.

### Error: QA Loop Exceeds 3 Iterations
**Cause**: Visual issues persist despite fixes. Usually indicates a fundamental design problem.
**Solution**: Stop iterating after 3 attempts. Report remaining issues, suggest the user simplify content or change layout approach, deliver the best available version with caveats.

---

## Blocker Criteria

STOP and ask the user (stop and resolve before proceeding autonomously) when:

| Situation | Why Stop | Ask This |
|-----------|----------|----------|
| Content too thin for requested slide count | Padding produces empty slides that waste audience time | "You have content for about 5 slides but requested 12. Create a 5-slide deck or add more content?" |
| No clear topic or audience | Cannot select palette or structure without context | "Who is the audience, and what is the key message?" |
| User provides a .pptx template to modify | Template editing has different constraints than blank-slate generation | "Should I modify your existing deck, or create a new one using your template's styling?" |
| QA finds structural issues (wrong slide count) | Structural failures indicate a slide map problem, not a visual fix | "The generated deck has 8 slides but the map specified 10. Regenerate or adjust the map?" |
| Multiple valid palette choices | Aesthetic preference is personal | "I'd suggest [Palette] for this type of presentation. Want that, or prefer something else?" |

### Confirm With User
- Audience and tone (business vs technical vs casual changes everything)
- Whether to use dark theme (Midnight palette) -- strong aesthetic choice
- Whether to include images (user must provide assets or explicitly request generation)
- Slide count when user is vague ("a few slides" -- ask for a number)
- Content that the user hasn't provided (build the deck from user-provided content only). Reason: Build the deck the user asked for. No speculative slides, no "bonus" content, no unsolicited animations or transitions.

---

## Retry Limits and Recovery

**Retry Limits**:
- Phase 3 (GENERATE): Max 2 retries for script failures before escalating to user
- Phase 5 (QA): Max 3 iterations of the fix-and-recheck cycle
- Slide map revision: Max 2 rounds of user feedback before freezing the map

**Recovery Protocol**:
1. **Detection**: Same QA issue reappearing after a fix attempt, generation script failing on the same input repeatedly, or slide map revisions not converging
2. **Intervention**: Simplify the deck. Reduce slide count, use only `content` and `title` layouts, drop complex layouts (table, two-column) that may be causing issues
3. **Prevention**: Validate the slide map JSON against the schema before generation. Check that bullet counts are within limits. Verify image paths exist before including `image_text` slides.

---

## Dependencies

### Required
| Dependency | Type | Purpose | Install |
|------------|------|---------|---------|
| `python-pptx` | pip | PPTX generation and manipulation | `pip install python-pptx` |

### Optional (enhances capability)
| Dependency | Type | Purpose | Install |
|------------|------|---------|---------|
| LibreOffice | system | PDF/PNG conversion for visual QA loop | `apt install libreoffice-impress` |
| `Pillow` | pip | Image handling for embedded images | `pip install Pillow` |
| `pdftoppm` (poppler-utils) | system | Higher-quality PDF-to-PNG conversion | `apt install poppler-utils` |
| `markitdown` | pip | Extract text from existing PPTX for content reuse | `pip install markitdown` |

### Out-of-Scope Tools
| Tool | Why Not |
|------|---------|
| `pptxgenjs` / Node.js | Foreign ecosystem; python-pptx covers our needs |
| Raw XML unzip/rezip | python-pptx + lxml handles this natively |
| Headless browser | LibreOffice handles conversion |

---

## Script Reference

### generate_pptx.py

**Purpose**: Deterministic slide construction. Reads slide map JSON + design config JSON, produces .pptx.

| Argument | Required | Description |
|----------|----------|-------------|
| `--slide-map` | Yes | Path to slide map JSON file |
| `--design` | Yes | Path to design config JSON file |
| `--output` | Yes | Output .pptx file path |

**Design config format**:
```json
{
  "palette": "minimal",
  "template_path": null
}
```

Exit codes: 0 = success, 1 = missing python-pptx, 2 = invalid input, 3 = generation failed.

### convert_slides.py

**Purpose**: PPTX to PDF to per-slide PNG conversion for visual QA.

| Argument | Required | Description |
|----------|----------|-------------|
| `--input` | Yes | Path to .pptx file |
| `--output-dir` | Yes | Directory for output PNG files |
| `--dpi` | No | PNG resolution (default: 150) |
| `--keep-pdf` | No | Keep intermediate PDF file |

Exit codes: 0 = success, 1 = no LibreOffice, 2 = conversion failed, 3 = invalid input.

### validate_structure.py

**Purpose**: Validate .pptx structural integrity against the slide map.

| Argument | Required | Description |
|----------|----------|-------------|
| `--input` | Yes | Path to .pptx file |
| `--expected-slides` | No | Expected slide count |
| `--slide-map` | No | Path to slide map JSON for content validation |
| `--json` | No | Output results as JSON |

Exit codes: 0 = passed, 1 = missing python-pptx, 2 = validation failed, 3 = invalid input.

---

## References

For detailed information:
- **Design System**: [references/design-system.md](references/design-system.md) -- color palettes with hex codes, typography rules, spacing guidelines, python-pptx color usage
- **Slide Layouts**: [references/slide-layouts.md](references/slide-layouts.md) -- 8 layout types with python-pptx code, positioning specs, and rhythm guidelines
- **Anti-AI Slide Rules**: [references/anti-ai-slide-rules.md](references/anti-ai-slide-rules.md) -- 10 patterns to avoid, detection criteria, and the summary checklist
- **QA Checklist**: [references/qa-checklist.md](references/qa-checklist.md) -- visual QA criteria for the subagent, severity levels, and output format

### Complementary Skills
- [research-to-article](../research-to-article/SKILL.md) -- research output can feed slide content
- [gemini-image-generator](../gemini-image-generator/SKILL.md) -- generate images for slides
- [workflow-orchestrator](../workflow-orchestrator/SKILL.md) -- orchestrate multi-step pipelines
