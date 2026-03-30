---
name: blog-post-writer
description: "Deprecated: voice-integrated blog post creation."
version: 2.0.0
deprecated: true
deprecated_by: voice-writer
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
  triggers: []
  category: content-creation
---

# Blog Post Writer Skill

Voice-integrated blog post creation using a 4-phase pipeline: Assess, Decide, Draft, Preview. Each phase has a gate that must pass before proceeding.

## Instructions

> **DEPRECATED**: This skill is deprecated in favor of `voice-writer` (ADR-068).
> Use `/voice-writer` for all blog post and article generation. The voice-writer
> pipeline includes mandatory de-ai scanning, joy-check validation, and voice
> metric verification that this skill lacks.

### Phase 1: ASSESS

**Goal**: Understand the topic, select voice, and classify content type before writing.

**Step 1: Read repository CLAUDE.md** to load any project-specific writing rules or conventions before proceeding.

**Step 2: Analyze the topic**

```markdown
## Assessment
- Topic: [user-provided topic]
- Scope: [narrow / medium / broad]
- Audience: [beginner / intermediate / expert]
- Estimated length: [short 500-800 / medium 1000-1500 / long 2000+]
```

**Step 3: Select voice**

Load the specified voice skill. If none specified, ask the user which voice to use -- a voice must be selected before any writing begins because retrofitting voice patterns onto an existing draft produces inconsistent results.

Available voices can be found at `skills/voice-*/SKILL.md`. Create new voices with `/create-voice`. This skill does not create or modify voice profiles; redirect to the voice skill creation workflow if needed.

**Step 4: Classify content type**

Choose from `references/structure-templates.md`:
- **Problem-Solution**: Bug fix, debugging session, resolution
- **Technical Explainer**: Concept, technology, how it works
- **Walkthrough**: Step-by-step instructions for a task

**Gate**: Topic analyzed, voice loaded, content type selected. Proceed only when all three are confirmed.

### Phase 2: DECIDE

**Goal**: Plan post structure using voice patterns and structure templates.

**Step 1: Plan opening**

Read opening patterns from the loaded voice skill. Select the pattern that fits the topic. Use exactly one voice profile per post -- mixing patterns from different voices creates inconsistent, inauthentic output.

```markdown
## Plan
- Opening pattern: [Provocative Question / News Lead / Bold Claim / Direct Answer]
- Draft opening: [first sentence or question]
```

**Step 2: Plan extended metaphor** (if the loaded voice uses them)

```markdown
- Core metaphor: [conceptual lens]
- Development points: [where it recurs in the post]
```

**Step 3: Plan sections** (3-7 sections)

Plan only sections the user requested. Do not add "Future Implications", "Related Topics", or other unsolicited sections -- write what was asked for and nothing more. If you think an additional section would help, ask the user before including it.

```markdown
- Sections:
  1. [Section name]: [purpose]
  2. [Section name]: [purpose]
  ...
```

**Step 4: Plan closing**

Read closing patterns from voice skill. Select pattern and identify callback element.

```markdown
- Closing pattern: [Callback / Implication / Crescendo]
- Callback element: [what from opening returns]
```

**Step 5: Draft frontmatter**

All posts use Hugo YAML frontmatter with correct syntax:

```yaml
---
title: "Post Title Here"
slug: "post-slug-here"
date: YYYY-MM-DD
draft: false
tags: ["tag1", "tag2"]
summary: "One sentence description for list views"
---
```

**Gate**: Structure planned, opening and closing patterns selected, frontmatter drafted. Proceed only when gate passes.

### Phase 3: DRAFT

**Goal**: Generate the post applying voice patterns from the selected voice skill.

**Step 1: Write opening**
- Apply opening pattern from voice skill
- Establish premise or hook
- Plant callback element if using callback closing

**Step 2: Write each section**
- Apply sentence rhythm from voice skill
- Develop extended metaphors if voice uses them
- Use second-person address if voice uses it
- Include specific numbers for all claims -- use concrete data, not vague adjectives like "significant" or "many"

**Step 3: Write closing**
- Apply closing pattern from voice skill
- Return to callback element if planted
- Build to emotional crescendo if appropriate for voice

**Step 4: Banned word scan**

Run a systematic scan of the entire draft against `references/banned-words.md`. Visual scanning is insufficient because banned words hide in context -- the full list must be checked programmatically.

- If ANY banned word is found: rewrite the affected sentence immediately using alternatives from the reference
- Re-scan until zero violations
- Never suppress or skip a detection

**Step 5: Voice and formatting verification**
- Check patterns against voice skill requirements; "close enough" is not passing -- re-read the voice skill and verify each pattern explicitly
- Verify sentence rhythm matches voice
- Confirm opening and closing styles match voice
- Verify zero em-dashes in entire draft -- em-dashes are never acceptable; rewrite with commas, periods, or sentence restructuring

**Gate**: Draft complete, zero banned words, voice patterns verified, zero em-dashes. Proceed only when gate passes.

### Phase 4: PREVIEW

**Goal**: Display full draft for user approval before writing to file. Skipping preview loses the user's opportunity to request changes, and rewrites after file creation are costlier than previews. (Skip this phase only if the user explicitly enables Direct Write Mode.)

**Step 1: Present draft**

Display the complete post with frontmatter. Show target file path.

**Step 2: Show compliance report**

Verify that all planned sections are present -- length alone does not indicate completeness.

```markdown
## Voice Compliance
- Opening pattern: [pattern name] - PASS/FAIL
- Sentence rhythm: [verified/issues] - PASS/FAIL
- Extended metaphor: [present/n/a] - PASS/FAIL
- Closing pattern: [pattern name] - PASS/FAIL
- Banned words: [count] found - PASS/FAIL
- Em-dashes: [count] found - PASS/FAIL

Target file: content/posts/{slug}.md
```

**Step 3: Await approval**

Wait for user confirmation before writing. If user requests changes, return to the appropriate phase.

**Gate**: User approves draft. Write to file. Task complete.

## Error Handling

### Error: "No voice specified"
Cause: User did not specify a voice parameter
Solution:
1. Default to the user's configured voice skill
2. Notify user which voice is being used
3. Proceed with Phase 1

### Error: "Voice skill not found"
Cause: Specified voice skill does not exist at expected path
Solution:
1. List available voice skills with paths
2. Ask user to select from available voices
3. If user needs new voice, redirect to voice skill creation

### Error: "Banned word found in draft"
Cause: Draft contains words from `references/banned-words.md`
Solution:
1. Identify the exact sentence containing the banned word
2. Rewrite using alternatives from the banned words reference
3. Re-scan entire draft to confirm zero violations
4. Never suppress or ignore a banned word detection

### Error: "Topic too broad for target length"
Cause: Topic scope exceeds estimated word count
Solution:
1. Ask user to narrow scope
2. Suggest 2-3 specific angles derived from the topic
3. Proceed once user selects a narrower focus

## References

- `${CLAUDE_SKILL_DIR}/references/banned-words.md`: Words and phrases that signal AI-generated content
- `${CLAUDE_SKILL_DIR}/references/structure-templates.md`: Templates for Problem-Solution, Technical Explainer, and Walkthrough content types
