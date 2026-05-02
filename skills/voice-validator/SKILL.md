---
name: voice-validator
description: "Critique-and-rewrite loop for voice fidelity validation."
user-invocable: false
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
  - Skill
routing:
  triggers:
    - "validate voice"
    - "check voice fidelity"
    - "voice critique"
    - "voice fidelity"
    - "writing style check"
  category: voice
  pairs_with:
    - voice-writer
    - anti-ai-editor
    - joy-check
---

# Voice Validator Skill

## Overview

Critique-and-rewrite enforcement loop for voice fidelity. Scans content against voice-specific negative prompt checklists, documents violations with evidence, fixes them preserving intent, and rescans to confirm. Maximum 3 iterations.

**Workflow**: scan -> document violations -> revise -> rescan.

**Critical**: Never revise without first scanning the full checklist. Every violation must cite a specific quote. After 3 failed iterations, output with flagged concerns.

---

## Instructions

### Phase 1: IDENTIFY TARGET

**Goal**: Determine voice, mode, and content to validate.

1. Identify target voice from context or user instruction
2. Identify mode if applicable (casual modes have additional checks)
3. Reference the target voice's checklist (ask user if unclear)
4. Read the content to validate; note length (longer content drifts more)

**Gate**: Voice target and mode identified. Content loaded.

### Phase 2: SCAN

**Goal**: Run full checklist against content, identify all violations with evidence.

**Step 1: Run negative prompt checklist**

Check all categories against the target voice's checklist:

- **Tone**: Matches voice profile? (too polished, too corporate, missing warmth)
- **Structure**: Matches? (front-loaded constraints, clean outlines, wrap-ups)
- **Sentences**: Patterns match? (dramatic short sentences, rhetorical flourishes, symmetrical structure)
- **Language**: Banned words? (amazing, terrible, revolutionary, perfect, game-changing, transformative, incredible, outstanding, exceptional, groundbreaking), marketing/hype, unnecessary superlatives
- **Emotion**: Handling matches? (explicitly named emotions, venting, moralizing)
- **Questions**: Patterns match? (open-ended brainstorming, vague curiosity)
- **Metaphors**: Patterns match? (journey/path, biological/growth, narrative/story)

**Step 2: Check pass conditions**

- Feels like the person actually wrote it
- Voice-specific patterns present (thinking out loud, warmth, precision, etc.)
- Could NOT be posted on LinkedIn without edits (catches ~80% of violations for casual voices)
- Does NOT sound AI-written
- Mode-specific patterns present

**Step 3: Document violations**

For each violation record:
1. Category (tone, structure, sentence, language, emotion, question, metaphor)
2. Quoted text from content
3. Specific fix recommendation

Only scan here; save revisions for Phase 3.

**Gate**: Full checklist scanned. All violations documented with evidence.

### Phase 3: REVISE

**Goal**: Fix all violations preserving content intent and substance.

1. Address each violation with the smallest change that resolves it
2. Preserve original meaning and information
3. Fixes must not create new violations
4. Do not strip necessary content or change substance (scope creep)

**Gate**: All documented violations addressed. Intent preserved.

### Phase 4: VERIFY

**Goal**: Confirm revised content passes all checks.

**Step 1**: Rescan revised content against full Phase 2 checklist. "Should be fine" is rationalization — always rescan.

**Step 2**: Evaluate:
- PASS: Output final content with validation report
- FAIL, iteration < 3: Return to Phase 3 with new violations
- FAIL, iteration = 3: Output with flagged remaining concerns

**Step 3**: Output validation report:

```
VOICE VALIDATION: [Voice Name] Mode [mode]
SCAN RESULT: [PASS/FAIL]
VIOLATIONS DETECTED: [N]
ITERATION: [1-3]

[If violations:]
1. [Category]: "[quoted violation]"
   Fix: [specific correction]

REVISED OUTPUT:
[Corrected content]

RESCAN RESULT: [PASS/FAIL]
```

**Gate**: Content passes all checks, or max iterations reached with flagged concerns.

---

## Error Handling

### Error: "Voice Target Unclear"
Cause: No voice specified and context is ambiguous.
Solution: Check context for voice mentions, look for voice-specific patterns to infer target, ask user if still unclear.

### Error: "Violations Persist After 3 Iterations"
Cause: Fundamental mismatch between content and voice requirements.
Solution: Output with flagged violations, list resistant checklist items, suggest regeneration from scratch with correct voice skill.

### Error: "Revision Introduced New Violations"
Cause: Fixing one category created violations in another.
Solution: Address new violations next iteration. If oscillating between types, fix both simultaneously. Prioritize tone/language over structural.

---

## References

- `voice-{name}` - Generates content in a specific voice (validate output with this skill)
- `anti-ai-editor` - Complementary anti-AI pattern detection
- `voice-writer` - Unified voice content generation pipeline that invokes this skill
