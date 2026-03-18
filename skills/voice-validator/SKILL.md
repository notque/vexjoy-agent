---
name: voice-validator
description: |
  Critique-and-rewrite enforcement loop for voice fidelity. Validates generated
  content against negative prompt checklists and forces revision until it passes.
  Use when content has been generated in a target voice, voice output feels off,
  long-form content risks voice drift, or before final delivery of voice content.
  Use for "validate voice", "check voice", "voice feels wrong", "voice drift",
  or "rewrite for voice". Do NOT use for initial voice generation, voice profile
  creation, or content that has no voice target.
version: 2.0.0
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
---

# Voice Validator Skill

## Operator Context

This skill operates as an operator for voice validation workflows, configuring Claude's behavior for rigorous critique-and-rewrite enforcement. It implements the **Iterative Refinement** architectural pattern -- scan content, identify violations, revise, rescan -- with **Domain Intelligence** embedded in voice-specific negative prompt checklists and pass/fail criteria.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before validating
- **Over-Engineering Prevention**: Fix only voice violations. No content rewriting beyond voice fidelity
- **Scan Before Revise**: NEVER revise content without first scanning against the full checklist
- **Evidence Required**: Every violation must cite a specific quote from the content
- **Maximum 3 Iterations**: If still failing after 3 rewrites, output with flagged concerns
- **Preserve Intent**: Revisions fix voice violations only -- never alter meaning or substance

### Default Behaviors (ON unless disabled)
- **Full Checklist Scan**: Run all categories (tone, structure, sentence, language, emotion, questions, metaphors)
- **Violation Report**: Output structured validation report with quoted violations and fixes
- **Auto-Revise on Fail**: Automatically produce revised version when violations detected
- **Rescan After Revision**: Re-run checklist against revised content to confirm pass
- **LinkedIn Test**: Apply quick "could this be posted on LinkedIn without edits?" heuristic
- **Mode Detection**: Identify voice mode (1-5) for mode-specific checks

### Optional Behaviors (OFF unless enabled)
- **Script Validation**: Run `voice_validator.py` for deterministic banned-pattern detection
- **Inline Validation**: Silent self-check within conversation without full report
- **Cross-Voice Comparison**: Compare output against wrong-voice patterns to verify distinctness

## What This Skill CAN Do
- Validate content against voice-specific negative prompt checklists
- Identify specific violations with quoted evidence and category labels
- Revise content to fix voice violations while preserving intent
- Enforce iterative scan-revise-rescan loops up to 3 iterations
- Distinguish between different voice profiles with mode-specific criteria

## What This Skill CANNOT Do
- Generate content in a target voice from scratch (use the appropriate voice skill instead)
- Create or modify voice profiles (use voice_analyzer.py instead)
- Edit content for non-voice concerns like grammar or accuracy (use anti-ai-editor instead)
- Skip the scan phase and go straight to rewriting
- Validate voices that have no defined checklist

---

## Instructions

### Phase 1: IDENTIFY TARGET

**Goal**: Determine the voice, mode, and content to validate.

**Step 1: Identify voice target**
- Determine target voice from context or user instruction
- Identify mode if applicable -- casual modes may have additional specific checks

**Step 2: Load content**
- Read the content to validate
- Note content length -- longer content is more prone to drift

**Gate**: Voice target and mode identified. Content loaded. Proceed only when gate passes.

### Phase 2: SCAN

**Goal**: Run full checklist against content and identify all violations.

**Step 1: Run negative prompt checklist**

Check all categories against the target voice's checklist:
- **Tone**: Does the tone match the voice profile? (e.g., too polished, too corporate, missing warmth)
- **Structure**: Does the structure match? (e.g., front-loaded constraints, clean outlines, wrap-ups)
- **Sentences**: Do sentence patterns match? (e.g., dramatic short sentences, rhetorical flourishes, symmetrical structure)
- **Language**: Any banned words? (amazing, terrible, revolutionary, perfect, game-changing, transformative, incredible, outstanding, exceptional, groundbreaking), marketing/hype, inspirational, unnecessary superlatives
- **Emotion**: Does emotion handling match? (e.g., explicitly named emotions, venting/ranting, moralizing)
- **Questions**: Do question patterns match? (e.g., open-ended brainstorming, vague curiosity)
- **Metaphors**: Do metaphor patterns match? (e.g., journey/path, biological/growth, narrative/story)

**Step 2: Check pass conditions**

Verify the content matches the target voice's positive identity markers. Common pass conditions include:
- Feels like the person actually wrote it
- Voice-specific patterns are present (thinking out loud, warmth, precision, etc.)
- Could NOT be posted on LinkedIn without edits (for casual voices)
- Does NOT sound like AI wrote it
- Mode-specific patterns are present (casual modes: no preamble, no wrap-up; formal modes: structured flow)

**Step 3: Document violations**

For each violation, record:
1. Category (tone, structure, sentence, language, emotion, question, metaphor)
2. Quoted text from the content
3. Specific fix recommendation

**Gate**: Full checklist scanned. All violations documented with evidence. Proceed only when gate passes.

### Phase 3: REVISE

**Goal**: Fix all violations while preserving content intent and substance.

**Step 1: Apply fixes**
- Address each violation with the smallest change that resolves it
- Preserve the original meaning and information
- Maintain natural flow -- fixes should not create new violations

**Step 2: Verify no overcorrection**
- Ensure revisions did not strip necessary content
- Confirm the substance and technical accuracy remain intact

**Gate**: All documented violations addressed. Intent preserved. Proceed only when gate passes.

### Phase 4: VERIFY

**Goal**: Confirm revised content passes all checks.

**Step 1: Rescan revised content**

Run the full checklist from Phase 2 against the revised version.

**Step 2: Evaluate result**
- If PASS: Output final content with validation report
- If FAIL and iteration < 3: Return to Phase 3 with new violations
- If FAIL and iteration = 3: Output content with flagged remaining concerns

**Step 3: Output validation report**

```
VOICE VALIDATION: [Voice Name] Mode [mode]
SCAN RESULT: [PASS/FAIL]
VIOLATIONS DETECTED: [N]
ITERATION: [1-3]

[If violations:]
1. [Category]: "[quoted violation]"
   Fix: [specific correction]

2. [Category]: "[quoted violation]"
   Fix: [specific correction]

REVISED OUTPUT:
[Corrected content]

RESCAN RESULT: [PASS/FAIL]
```

**Gate**: Content passes all checks, or maximum iterations reached with flagged concerns. Validation complete.

---

## Examples

### Example 1: Technical Voice Validation
User says: "Validate this draft is in the right voice"
Actions:
1. Identify target voice from context, determine mode from content style (IDENTIFY TARGET)
2. Run full 7-category negative prompt checklist, find 2 violations (SCAN)
3. Fix "I'm excited to share" (named emotion) and "This changes everything" (dramatic short sentence) (REVISE)
4. Rescan revised content, confirm PASS (VERIFY)
Result: Clean content with validation report

### Example 2: Community Voice Validation
User says: "Does this sound like the right voice?"
Actions:
1. Identify target voice from context (IDENTIFY TARGET)
2. Scan against voice checklist, find missing warmth and no sensory details (SCAN)
3. Add experiential language and warmth while preserving substance (REVISE)
4. Rescan, confirm warmth and sensory details present, PASS (VERIFY)
Result: Content matches voice profile

---

## Error Handling

### Error: "Voice Target Unclear"
Cause: Content doesn't specify which voice to validate against, or context is ambiguous
Solution:
1. Check conversation context for voice mentions
2. Look for voice-specific patterns to infer target
3. If still unclear, ask user to specify voice name and mode

### Error: "Violations Persist After 3 Iterations"
Cause: Fundamental mismatch between content substance and voice requirements, or conflicting checklist items
Solution:
1. Output content with clearly flagged remaining violations
2. List specific checklist items that resist correction
3. Suggest the content may need to be regenerated from scratch with the correct voice skill

### Error: "Revision Introduced New Violations"
Cause: Fixing one category created violations in another (e.g., removing dramatic sentences introduced polished phrasing)
Solution:
1. Address new violations in next iteration
2. If oscillating between two violation types, fix both simultaneously
3. Prioritize tone and language violations over structural ones

---

## Anti-Patterns

### Anti-Pattern 1: Revising Without Scanning
**What it looks like**: "This doesn't sound right, let me rewrite it" without running the checklist
**Why wrong**: Subjective assessment misses specific violations. May "fix" things that aren't broken while missing real issues.
**Do instead**: Complete Phase 2 scan with documented violations before any revision.

### Anti-Pattern 2: Over-Revising Beyond Voice
**What it looks like**: Rewriting entire paragraphs, changing arguments, adding new points during voice correction
**Why wrong**: Voice validation fixes voice only. Changing substance is scope creep that alters the author's intent.
**Do instead**: Make the smallest change that resolves each voice violation. Preserve all meaning.

### Anti-Pattern 3: Skipping the Rescan
**What it looks like**: "I fixed the violations, it should be fine now" without re-running the checklist
**Why wrong**: Fixes can introduce new violations. "Should be fine" is a rationalization.
**Do instead**: Always run Phase 4 rescan. Every revision gets a full checklist pass.

### Anti-Pattern 4: Passing Content That Sounds Like LinkedIn
**What it looks like**: Content is polished, quotable, and shareable -- but marked as PASS
**Why wrong**: The LinkedIn test catches ~80% of voice violations. If it reads well on LinkedIn, it fails the target voice.
**Do instead**: Apply the quick check: "Could this be posted on LinkedIn without edits?" If yes, it FAILS.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "It sounds close enough" | Close enough ≠ voice fidelity | Run full checklist, fix all violations |
| "Only one small violation" | One violation breaks immersion | Fix it. No exceptions |
| "The substance matters more than voice" | Voice IS the deliverable in this context | Complete all 4 phases |
| "I already know what's wrong" | Knowing ≠ documenting with evidence | Scan and cite specific quotes |

### Related Skills
- `voice-{name}` - Generates content in a specific voice (validate output with this skill)
- `anti-ai-editor` - Complementary anti-AI pattern detection
- `voice-orchestrator` - Multi-step voice generation pipeline that invokes this skill
