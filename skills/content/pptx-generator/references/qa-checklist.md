# PPTX Visual QA Checklist

Criteria for the QA subagent to evaluate generated slide images. The subagent receives PNG renders of each slide and checks against this list.

## How to Use This Checklist

The QA subagent:
1. Receives slide PNGs (one per slide) and the original slide map
2. Evaluates each slide against ALL criteria below
3. Returns PASS or FAIL with specific issues per slide
4. Issues include the slide number, the failed criterion, and a fix instruction

## Criteria

### 1. Text Readability

| Check | Pass Condition | Common Failures |
|-------|---------------|-----------------|
| Text not clipped | All text visible within slide bounds | Text runs off right edge or bottom |
| Text not overlapping | No text overlaps other text or shapes | Headline overlaps body text |
| Font size adequate | Body text >= 18pt equivalent on screen | Tiny text that requires squinting |
| Contrast sufficient | Text legible against background | Light text on light background |
| No orphan words | Lines don't end with single-word orphans | "We need to / fix" |

### 2. Layout and Alignment

| Check | Pass Condition | Common Failures |
|-------|---------------|-----------------|
| Consistent margins | All slides use same margin spacing | Slide 3 has different left margin than others |
| Aligned elements | Text boxes aligned across slides | Title jumps position between slides |
| Visual balance | Content not bunched to one side | All content in top-left, bottom-right empty |
| White space appropriate | Breathing room around content | Either too cramped or too sparse |
| Grid alignment | Elements snap to implicit grid | Elements at arbitrary positions |

### 3. Color Usage

| Check | Pass Condition | Common Failures |
|-------|---------------|-----------------|
| Palette consistency | All colors from chosen palette | Random colors not in palette |
| Max 3 colors per slide | No more than 3 palette colors used per slide | Rainbow effect with 5+ colors |
| Contrast ratio adequate | Text vs background has sufficient contrast | Gray text on gray background |
| Accent used sparingly | Accent color for emphasis only, not dominant | Entire slide in accent color |

### 4. Content Accuracy

| Check | Pass Condition | Common Failures |
|-------|---------------|-----------------|
| Title matches slide map | Slide headline matches what was planned | Wrong title on slide |
| Content matches slide map | Bullet points match planned content | Missing or extra bullets |
| Slide order correct | Slides appear in planned sequence | Section divider after its content |
| Slide type correct | Layout matches planned type (title, content, etc.) | Content slide used for section divider |

### 5. Anti-AI-Slide Violations

See `anti-ai-slide-rules.md` for the full list. The QA subagent checks for ALL of these:

| Check | Fail Condition |
|-------|---------------|
| Accent line under title | ANY decorative line below a headline |
| Gradient on every slide | Gradient background on more than 1 slide |
| Identical layouts throughout | Same layout used for every content slide |
| Shadow on everything | Drop shadow on more than 2 elements per slide |
| Rounded rectangles everywhere | Rounded rect shapes used decoratively |
| Excessive icons | Geometric clip-art icons that serve no content purpose |
| Word art or gradient text | Any non-solid text coloring |

### 6. Structural Checks

| Check | Pass Condition | Common Failures |
|-------|---------------|-----------------|
| Slide count matches | Number of slides matches slide map | Extra or missing slides |
| Title slide present | First slide is a title slide | Content slide first |
| Closing slide present | Last slide is a closing/thank you slide (if planned) | Deck ends abruptly |
| Section dividers placed | Section dividers appear before their sections | Missing section breaks |

---

## QA Subagent Output Format

The subagent returns a structured assessment:

```
SLIDE QA RESULT: [PASS | FAIL]

Slides checked: N

Issues found: M

SLIDE 1: PASS
SLIDE 2: FAIL
  - [Text Readability] Title text clipped on right edge
    FIX: Reduce title font size to Pt(28) or shorten title text
  - [Anti-AI] Accent line under title detected
    FIX: Remove the decorative line shape below the title text box
SLIDE 3: PASS
...

OVERALL: FAIL (2 issues on 1 slide)
```

## Severity Levels

| Severity | Description | Action |
|----------|-------------|--------|
| **Blocker** | Text unreadable, content missing, wrong slide order | Must fix before delivery |
| **Major** | Alignment off, anti-AI violation, contrast issue | Should fix (counts toward 3-iteration limit) |
| **Minor** | Slightly suboptimal spacing, orphan word | Fix if within iteration budget |

Only **Blocker** and **Major** issues trigger a fix iteration. Minor issues are reported but don't require a fix cycle.
