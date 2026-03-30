---
name: post-outliner
description: "Create structural blueprints for blog posts: outlines, word counts."
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
routing:
  triggers:
    - "outline post"
    - "blog structure"
    - "content blueprint"
  category: content-creation
---

# Post Outliner Skill

## Overview

This skill creates structural blueprints for blog posts by analyzing topic briefs, selecting appropriate structure templates, and generating outlines with word counts and section summaries. Posts should be technical, deep, problem-solving focused—no fluff or filler. The workflow follows a four-phase process: assess the topic for core value proposition, decide on the right template and scope, generate the outline with all required elements, then validate against quality standards.

The skill operates under two core constraints:

1. **Structure First**: Always select a structure template before generating content. Never output an outline without understanding the topic's core problem or value proposition first.
2. **No Over-Engineering**: Outline only what was asked. Do not speculate on series planning, suggest related posts, or generate more outlines than requested.

---

## Instructions

### Phase 1: ASSESS

**Goal**: Understand the topic deeply before selecting any structure.

**Step 1: Read the topic brief**

Identify these elements:
- The core "vex" (frustration/problem being solved)
- The value proposition for readers
- Any constraints (length, audience, etc.)

**Step 2: Ask key questions**

If the topic brief is too vague to answer these, ask clarifying questions BEFORE proceeding:
- "What specific problem did you encounter?"
- "What did you learn?"
- "Who is the audience?"

Document your assessment:

```markdown
## Topic Assessment
Problem: [What problem does this solve?]
Audience: [Who encounters this problem?]
Insight: [What's the key insight or solution?]
Scope: [Single post or potential series?]
```

**Gate**: Core problem/value identified. Topic is specific enough to outline. Do not proceed with outline generation without this.

**Why This Phase**: Vague topics produce generic outlines. Section names should communicate content at a glance. Generic names (e.g., "Introduction", "Main Content", "Details", "Conclusion") reveal nothing about reader value and indicate shallow thinking about the topic. Always complete assessment with specific, content-descriptive section names in mind.

### Phase 2: DECIDE

**Goal**: Select the right structure template and scope.

**Step 1: Match template to content**

| Situation | Template | Why |
|-----------|----------|-----|
| Debugging story | Problem-Solution | Natural narrative arc |
| Explaining a concept | Technical Explainer | Clear progression |
| Teaching a process | Walkthrough | Step-by-step clarity |
| Comparing options | Comparison | Structured evaluation |
| Mixed content | Hybrid | Combine as needed |

See `references/structure-templates.md` for full template details with section breakdowns, signal words, and examples.

**Step 2: Set scope parameters**

| Post Type | Target Words | Sections |
|-----------|-------------|----------|
| Quick fix | 600-800 | 3 |
| Standard post | 1,000-1,500 | 4-5 |
| Deep dive | 1,500-2,500 | 5-7 |
| Tutorial | 1,200-2,000 | 5-6 |
| Series part | 800-1,200 | 3-4 |

**Why Scope Matters**: Section bloat dilutes impact. Your blog cuts to the chase. Too many thin sections (8+) at 100 words each pad length without adding value. Merge related sections. Aim for 3-7 substantive sections with specific names. Do not justify every section's existence against the core insight: cut sections that don't serve the core message. Word count estimates must be verified to add up to the overall total—rough estimates undermine scope validation.

**Gate**: Template selected, scope defined. Do not proceed without this.

### Phase 3: GENERATE

**Goal**: Produce the complete outline in standard format.

Generate the outline in this exact format:

```
===============================================================
 OUTLINE: [Working Title]
===============================================================

 Structure: [Template Name]
 Estimated Length: [X,XXX-X,XXX] words (~[N] min read)

 FRONTMATTER:
   title: "[Working Title]"
   date: [YYYY-MM-DD]
   tags: ["tag1", "tag2", "tag3"]
   summary: "[1-2 sentence summary for list views]"

 SECTIONS:

 1. [Section Title] [XXX-XXX words]
    [2-3 sentence summary describing what this section covers
    and what value it provides to the reader.]

 2. [Section Title] [XXX-XXX words]
    [2-3 sentence summary describing what this section covers
    and what value it provides to the reader.]

 [Continue for all sections]

===============================================================
 ALTERNATIVE STRUCTURES:

 -> [Template Name]: [1-sentence explanation of how this
    structure would approach the same topic differently]
 -> [Template Name]: [1-sentence explanation]
===============================================================
```

**Why Each Element**: Every section must have estimated word counts so you can validate scope and identify sections that are too heavy or too light. Calculating reading time (~250 wpm) helps authors understand audience engagement expectations. Include Hugo frontmatter planning (title, date, tags, summary) to reduce friction at the publication phase. Always offer at least one alternative structure so the author can choose from options rather than being locked into one approach.

**Gate**: Outline complete with all required elements.

### Phase 4: VALIDATE

**Goal**: Verify the outline meets quality standards.

Run through this checklist:

- [ ] **Clear vex/value**: Can you state the problem in one sentence?
- [ ] **Logical flow**: Does each section build on the previous?
- [ ] **No fluff sections**: Every section adds concrete value
- [ ] **Appropriate scope**: Not too broad, not too narrow
- [ ] **Specific section names**: No generic "Introduction" or "Conclusion"
- [ ] **Word counts present**: Every section has estimates
- [ ] **Word counts add up**: Section totals match overall estimate
- [ ] **Alternative structures**: At least one alternative offered
- [ ] **Blog identity**: Technical, direct, problem-solving

If any check fails, revise the outline before presenting.

**Why This Validation**: Word counts are not rough—they must be precise. Section totals must match the overall estimate. Do not tolerate arithmetic drift. Generic section names are a red flag that you haven't thought deeply about the content and what readers gain from each part.

**Gate**: All validation checks pass. Outline is complete.

---

## Examples

### Example 1: Debugging Topic
User says: "Spent 3 hours debugging why Hugo builds locally but fails on Cloudflare"
Actions:
1. Assess: Core vex is environment mismatch, audience is Hugo users (ASSESS)
2. Match: Debugging story maps to Problem-Solution template (DECIDE)
3. Generate: 4-section outline with word counts (GENERATE)
4. Validate: Logical flow, specific section names, scope appropriate (VALIDATE)
Result: Structured outline with Problem-Solution template, ~1,200-1,500 words

### Example 2: Concept Explanation
User says: "Want to explain how Go 1.22 changed loop variables"
Actions:
1. Assess: Value is understanding a language change, audience is Go devs (ASSESS)
2. Match: Concept explanation maps to Technical Explainer (DECIDE)
3. Generate: 4-section outline with code example notes (GENERATE)
4. Validate: Technical depth appropriate, no fluff sections (VALIDATE)
Result: Structured outline with Technical Explainer template, ~1,400-1,700 words

See `references/examples.md` for complete outline examples with full formatting.

---

## Error Handling

### Error: "Topic Too Vague"
Cause: User provides broad topic without specific angle (e.g., "write about Kubernetes")
Solution:
1. Ask clarifying questions: "What specific problem with Kubernetes?"
2. Suggest prompts: "What frustrated you? What did you learn?"
3. Do NOT generate a generic outline -- wait for specifics

### Error: "Topic Too Broad for Single Post"
Cause: Topic covers too much ground for target word count
Solution:
1. Identify the single key insight
2. Suggest splitting into a series with clear part boundaries
3. Recommend focusing the outline on the core insight only

### Error: "No Clear Structure Fit"
Cause: Topic doesn't map cleanly to any single template
Solution:
1. Use hybrid approach combining elements from multiple templates
2. See `references/structure-templates.md` for hybrid templates
3. Prioritize the dominant content type when choosing base structure

### Error: "Estimated Length Exceeds Target"
Cause: Too many sections or sections scoped too broadly
Solution:
1. Merge thin sections that cover similar ground
2. Cut sections that don't directly serve the core insight
3. Suggest multi-part series if content genuinely requires depth

---

## References

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/structure-templates.md`: Complete template library with section breakdowns and signal words
- `${CLAUDE_SKILL_DIR}/references/examples.md`: Real outlines from your blog posts demonstrating proper format
