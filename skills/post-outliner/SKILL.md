---
name: post-outliner
description: |
  Create structural blueprints for blog posts before writing. Analyzes topic
  briefs, selects structure templates, generates outlines with word counts and
  section summaries. Use when planning a new post, brainstorming structure,
  or deciding scope before drafting. Use for "outline", "plan post",
  "structure this topic", "how should I organize". Do NOT use for writing
  actual post content, editing existing posts, or SEO keyword planning.
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
---

# Post Outliner Skill

## Operator Context

This skill operates as an operator for blog post planning, configuring Claude's behavior for creating structural blueprints that ensure posts have logical flow and appropriate scope. It implements the **Structured Analysis** pattern -- assess topic, select template, generate outline, validate structure.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before outlining
- **Over-Engineering Prevention**: Outline only what was asked. No speculative series planning, no "while I'm here let me plan 5 more posts"
- **Structure First**: ALWAYS select a structure template before generating content
- **Word Count Estimates**: Every section MUST include estimated word counts
- **your blog Identity**: Posts are technical, deep, problem-solving focused -- no fluff or filler
- **Alternative Structures**: Always offer at least one alternative structure type
- **Assess Before Outline**: NEVER generate an outline without understanding the topic's core problem or value proposition first

### Default Behaviors (ON unless disabled)
- **Section Summaries**: Include 2-3 sentence summaries per section
- **Reading Time**: Calculate and display estimated reading time (~250 wpm)
- **Complete Output**: Show full outline in formatted report block
- **Template Matching**: Auto-detect best structure from topic description
- **Hugo Frontmatter**: Include title, date, tags, summary planning
- **Logical Flow Validation**: Verify each section builds on the previous

### Optional Behaviors (OFF unless enabled)
- **Minimal Mode**: Just section headers, no summaries
- **Deep Mode**: Expand to sub-section level with bullet points
- **Series Mode**: Plan multi-part post series with dependencies

## What This Skill CAN Do
- Analyze topic briefs and identify the core "vex" or value proposition
- Select the most appropriate structure template for the content
- Generate structured outlines with section summaries and word counts
- Estimate reading time and validate scope
- Suggest alternative structures for the same topic
- Handle Hugo frontmatter planning (title, tags, summary)
- Validate logical flow between sections

## What This Skill CANNOT Do
- Write actual post content (use `blog-post-writer` for that)
- Edit existing posts (use `anti-ai-editor` for style fixes)
- Guarantee SEO optimization (focus is structure, not keywords)
- Plan non-blog content like documentation or README files
- Create outlines without understanding the topic first -- always assess

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

```markdown
## Topic Assessment
Problem: [What problem does this solve?]
Audience: [Who encounters this problem?]
Insight: [What's the key insight or solution?]
Scope: [Single post or potential series?]
```

If the topic brief is too vague to answer these, ask clarifying questions BEFORE proceeding:
- "What specific problem did you encounter?"
- "What did you learn?"
- "Who is the audience?"

**Gate**: Core problem/value identified. Topic is specific enough to outline. Proceed only when gate passes.

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

**Gate**: Template selected, scope defined. Proceed only when gate passes.

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

**Gate**: Outline complete with all required elements. Proceed only when gate passes.

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
- [ ] **your blog identity**: Technical, direct, problem-solving

If any check fails, revise the outline before presenting.

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

## Anti-Patterns

### Anti-Pattern 1: Outline Without Understanding
**What it looks like**: Generating a generic outline immediately after receiving a broad topic like "Kubernetes"
**Why wrong**: No specific value proposition, no your blog identity. Produces hollow structure without substance.
**Do instead**: Complete Phase 1 ASSESS first. Ask clarifying questions. Identify the specific problem and insight before touching structure.

### Anti-Pattern 2: Too Many Thin Sections
**What it looks like**: 8+ sections with Introduction, Background, Context, Problem Statement each at 100 words
**Why wrong**: your blog cuts to the chase. Multiple thin sections dilute impact and pad length without adding value.
**Do instead**: Merge related sections. Start with the vex. Aim for 3-7 substantive sections.

### Anti-Pattern 3: Generic Section Names
**What it looks like**: "Introduction", "Main Content", "Details", "Conclusion"
**Why wrong**: Section names should communicate content at a glance. Generic names reveal nothing about what the reader gains.
**Do instead**: Use specific, descriptive names like "Hugo Builds Fail on Cloudflare" instead of "The Problem".

### Anti-Pattern 4: Missing Word Counts
**What it looks like**: Sections listed without any size estimates
**Why wrong**: Cannot validate scope, cannot estimate reading time, cannot identify sections that are too heavy or too light.
**Do instead**: Every section gets a word count range. Totals must add up to overall estimate.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "Topic is clear enough, skip assessment" | Vague topics produce generic outlines | Complete Phase 1 ASSESS with key questions |
| "One structure is fine, no need for alternatives" | Author should choose from options | Always include ALTERNATIVE STRUCTURES section |
| "Word counts are rough, close enough" | Section totals must match overall estimate | Verify arithmetic before presenting |
| "Generic section names work for now" | Names reveal outline quality and thinking depth | Use specific, content-descriptive names |
| "Just one more section won't hurt" | Section bloat dilutes impact | Justify every section's existence against core insight |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/structure-templates.md`: Complete template library with section breakdowns and signal words
- `${CLAUDE_SKILL_DIR}/references/examples.md`: Real outlines from your blog posts demonstrating proper format
