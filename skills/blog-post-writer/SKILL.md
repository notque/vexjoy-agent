---
name: blog-post-writer
description: |
  Voice-integrated blog post creation with 4-phase workflow: Assess, Decide,
  Draft, Preview. Use when user wants to write a blog post, create content
  for a Hugo site, or draft an article using a specific voice profile.
  Use for "write post", "blog about", "draft article", "create content",
  or "write about [topic]". Do NOT use for editing existing posts, voice
  profile creation, SEO optimization, or social media content.
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
routing:
  triggers:
    - "write blog post"
  category: content-creation
---

# Blog Post Writer Skill

## Operator Context

This skill operates as an operator for blog post creation, configuring Claude's behavior for structured, voice-consistent content generation. It implements the **Pipeline** architectural pattern -- Assess, Decide, Draft, Preview -- with **Voice Integration** via separate voice skills for stylistic patterns.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before writing
- **Over-Engineering Prevention**: Write the post requested. No "bonus sections", no unsolicited additions, no extra content types
- **Banned Words Enforcement**: NEVER use words from `references/banned-words.md`. Scan every draft before finalizing
- **Voice Compliance**: Follow the specified voice skill's patterns exactly. Do not blend voices
- **Hugo Format**: All posts use proper YAML frontmatter with correct syntax
- **Em-Dash Prohibition**: NEVER use em-dashes. Use commas, periods, or sentence restructuring instead

### Default Behaviors (ON unless disabled)
- **Voice Required**: Must specify a voice skill (user must configure a default voice or specify one)
- **Preview Before Write**: Display full draft for approval before writing to file
- **Post-Draft Banned Word Scan**: Verify zero banned words before finalizing
- **Structure Template**: Use appropriate template from `references/structure-templates.md`
- **Specific Numbers**: Include concrete numbers for all claims, not vague adjectives

### Optional Behaviors (OFF unless enabled)
- **Direct Write Mode**: Skip preview and write directly to file
- **Outline Only**: Generate structure without full draft
- **Multiple Variants**: Generate 2-3 opening paragraphs for selection

## What This Skill CAN Do
- Write complete blog posts in any defined voice profile
- Apply voice-specific patterns (metaphors, rhythm, structure, tone)
- Generate proper Hugo frontmatter with correct YAML syntax
- Coordinate with voice skills for stylistic consistency
- Revise drafts based on user feedback

## What This Skill CANNOT Do
- Use banned words under any circumstances (see `references/banned-words.md`)
- Write without a voice specification (redirect: specify `--voice` or accept default)
- Add sections not requested by user (redirect: ask user before adding)
- Create or modify voice profiles (redirect: use voice skill creation workflow)
- Skip the banned word verification step

---

## Instructions

### Phase 1: ASSESS

**Goal**: Understand the topic, select voice, and classify content type before writing.

**Step 1: Analyze the topic**

```markdown
## Assessment
- Topic: [user-provided topic]
- Scope: [narrow / medium / broad]
- Audience: [beginner / intermediate / expert]
- Estimated length: [short 500-800 / medium 1000-1500 / long 2000+]
```

**Step 2: Select voice**

Load the specified voice skill. If none specified, ask the user which voice to use.

Available voices can be found at `skills/voice-*/SKILL.md`. Create new voices with `/create-voice`.

**Step 3: Classify content type**

Choose from `references/structure-templates.md`:
- **Problem-Solution**: Bug fix, debugging session, resolution
- **Technical Explainer**: Concept, technology, how it works
- **Walkthrough**: Step-by-step instructions for a task

**Gate**: Topic analyzed, voice loaded, content type selected. Proceed only when gate passes.

### Phase 2: DECIDE

**Goal**: Plan post structure using voice patterns and structure templates.

**Step 1: Plan opening**

Read opening patterns from voice skill. Select the pattern that fits the topic.

```markdown
## Plan
- Opening pattern: [Provocative Question / News Lead / Bold Claim / Direct Answer]
- Draft opening: [first sentence or question]
```

**Step 2: Plan extended metaphor** (if voice uses them)

```markdown
- Core metaphor: [conceptual lens]
- Development points: [where it recurs in the post]
```

**Step 3: Plan sections** (3-7 sections)

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
- Include specific numbers for all claims

**Step 3: Write closing**
- Apply closing pattern from voice skill
- Return to callback element if planted
- Build to emotional crescendo if appropriate for voice

**Step 4: Banned word scan**
- Scan entire draft against `references/banned-words.md`
- If ANY banned word found: rewrite the affected sentence immediately
- Re-scan until zero violations

**Step 5: Voice verification**
- Check patterns against voice skill requirements
- Verify sentence rhythm matches voice
- Confirm opening and closing styles match voice
- Verify zero em-dashes in entire draft

**Gate**: Draft complete, zero banned words, voice patterns verified. Proceed only when gate passes.

### Phase 4: PREVIEW

**Goal**: Display full draft for user approval before writing to file.

**Step 1: Present draft**

Display the complete post with frontmatter. Show target file path.

**Step 2: Show compliance report**

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

---

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

---

## Anti-Patterns

### Anti-Pattern 1: Writing Without Voice Skill Loaded
**What it looks like**: Starting to draft before reading the voice skill's patterns
**Why wrong**: Post will not match the voice profile. Retrofitting voice is harder than starting with it.
**Do instead**: Complete Phase 1 fully. Load and read the voice skill before writing any content.

### Anti-Pattern 2: Ignoring Banned Word Scan
**What it looks like**: "The draft reads well, no need to scan for banned words"
**Why wrong**: Banned words are AI fingerprints. A single occurrence undermines authenticity.
**Do instead**: Run banned word scan on every draft. Zero tolerance.

### Anti-Pattern 3: Adding Unsolicited Sections
**What it looks like**: Adding "Future Implications" or "Related Topics" sections the user did not request
**Why wrong**: Over-engineering the content. User asked for a specific post, not a content hub.
**Do instead**: Write exactly what was requested. Ask before adding anything extra.

### Anti-Pattern 4: Skipping Preview Phase
**What it looks like**: Writing directly to file without showing the draft first
**Why wrong**: User loses the opportunity to review and request changes. Rewrites are costlier than previews.
**Do instead**: Always show full draft with compliance report unless Direct Write Mode is enabled.

### Anti-Pattern 5: Blending Voice Patterns
**What it looks like**: Mixing one voice's extended metaphors with another voice's community warmth in one post
**Why wrong**: Each voice has distinct patterns. Mixing creates an inconsistent, inauthentic voice.
**Do instead**: Use exactly one voice profile per post. Follow that voice skill's patterns exclusively.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks
- [Wabi-Sabi Authenticity](../shared-patterns/wabi-sabi-authenticity.md) - Natural imperfections over synthetic perfection
- [Voice-First Writing](../shared-patterns/voice-first-writing.md) - Voice-driven content patterns

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "No banned words jumped out at me" | Visual scan misses words in context | Run systematic scan against full banned list |
| "Close enough to the voice" | Close ≠ matching the voice profile | Re-read voice skill, verify each pattern |
| "The post is already long enough" | Length ≠ completeness | Check all planned sections are present |
| "Em-dash here reads better" | Em-dashes are absolutely forbidden | Rewrite with comma, period, or restructure |
| "One extra section adds value" | User did not request it | Write what was asked, nothing more |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/banned-words.md`: Words and phrases that signal AI-generated content
- `${CLAUDE_SKILL_DIR}/references/structure-templates.md`: Templates for Problem-Solution, Technical Explainer, and Walkthrough content types
