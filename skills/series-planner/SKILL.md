---
name: series-planner
description: |
  Plan multi-part content series with structure, cross-linking, and publishing
  cadence. Use when user needs to plan a blog post series, structure a multi-part
  tutorial, or design content with cross-linked navigation. Use for "plan series",
  "series on [topic]", "multi-part blog", or "content series". Do NOT use for
  writing individual posts, single-article outlines, or content calendar planning
  without series structure.
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
command: /series
routing:
  triggers:
    - "plan series"
    - "multi-part content"
    - "content series"
  category: content-creation
---

# Series Planner Skill

## Operator Context

This skill operates as an operator for multi-part content planning, configuring Claude's behavior for creating cohesive blog post series with proper cross-linking, standalone value, and publishing cadence. It implements the **Structured Analysis** pattern -- assess viability, decide structure, generate plan -- with **Domain Intelligence** embedded in series type selection and standalone value enforcement.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before planning
- **Over-Engineering Prevention**: Plan the series requested. No bonus parts, no scope creep
- **Standalone Value**: Every part MUST deliver value without requiring other parts
- **Cross-Linking Structure**: Every series gets navigation plan (Part X of Y, prev/next)
- **Part Count Bounds**: Minimum 3 parts, maximum 7 parts. No exceptions
- **No Filler Parts**: Each part earns its place with substantial, unique content

### Default Behaviors (ON unless disabled)
- **Full Plan Display**: Show complete plan with all details, never summarize
- **Word Count Estimates**: Every part includes word count range (800-1500 typical)
- **Publishing Cadence**: Always recommend publication schedule with reasoning
- **Series Type Auto-Detection**: Select best series type from topic signals
- **Hugo Frontmatter**: Include frontmatter template for each part
- **Standalone Value Check**: Verify each part passes standalone test before output

### Optional Behaviors (OFF unless enabled)
- **Minimal Mode**: Just part titles and scope, no detailed breakdown
- **Landing Page**: Generate series index page plan (enable with "with landing page")
- **Parallel Planning**: Plan multiple series at once for content calendar

## What This Skill CAN Do
- Plan 3-7 part blog post series with logical progression
- Select appropriate series type (Progressive Depth, Chronological Build, Problem Exploration)
- Ensure each part has standalone value while enhancing series context
- Design cross-linking structure with navigation patterns
- Recommend publishing cadence based on content complexity
- Generate Hugo frontmatter templates for series posts

## What This Skill CANNOT Do
- Write actual post content (use blog-post-writer for writing)
- Plan series fewer than 3 parts (use single post or post-outliner instead)
- Plan series more than 7 parts (break into multiple series or narrow scope)
- Skip standalone value check (each part must be complete on its own)
- Create vague, padded series (no filler parts to hit a number)

---

## Instructions

### Usage

```
/series [topic or idea]
/series --type=progressive [topic]      # Force series type
/series --parts=5 [topic]               # Target part count
/series --with-landing [topic]          # Include landing page plan
/series --minimal [topic]               # Titles and scope only
```

### Phase 1: ASSESS

**Goal**: Determine whether the topic is viable as a series and identify natural divisions.

**Step 1: Analyze topic**

```markdown
## Series Assessment
Topic: [user-provided topic]
Scope: [narrow / medium / broad]
Natural divisions: [how this topic breaks apart]
Audience progression: [beginner to expert? single level?]
```

**Step 2: Check viability**

- [ ] Topic has natural divisions (3+ distinct subtopics)
- [ ] Each division can stand alone
- [ ] Logical progression exists between parts
- [ ] Not artificially padded (each part earns its place)

**Step 3: Detect series type**

Match topic signals to type. See `references/series-types.md` for full templates.

| Signal | Type |
|--------|------|
| "learn", "master", "deep dive" | Progressive Depth |
| "build", "create", "project" | Chronological Build |
| "why we chose", "migration", "debugging" | Problem Exploration |

**Gate**: Topic passes viability check with 3+ natural divisions identified. If topic fails viability, recommend single post or scope adjustment. Proceed only when gate passes.

### Phase 2: DECIDE

**Goal**: Select series type, part count, and structure.

**Step 1: Select type and justify**

```markdown
## Series Decision
Type: [Progressive Depth / Chronological Build / Problem Exploration]
Justification: [why this type fits]
Part Count: [3-7]
Total Estimated Words: [X,XXX - X,XXX]
```

**Step 2: Draft part breakdown**

For each part, define:
- Title and scope (1 sentence)
- Standalone value (what reader gets from this part alone)
- Forward/backward links to adjacent parts

**Step 3: Validate standalone value**

For EACH part, verify:
- Reader learns something complete (not half a concept)
- Working code/config/output is possible from this part alone
- No critical information deferred to other parts
- Someone landing on just this part gets something useful

Red flags that fail standalone test:
- "To understand this, read Part 1 first" as mandatory
- Part ends mid-implementation
- Core concepts explained only in earlier parts
- "Part 2 will explain why this works"

**Step 4: Select publishing cadence**

See `references/cadence-guidelines.md` for detailed criteria. Default to weekly unless topic complexity or content depth suggests otherwise.

**Gate**: All parts pass standalone value check. Part count is 3-7. Type selection justified. Proceed only when gate passes.

### Phase 3: GENERATE

**Goal**: Produce the complete series plan with all metadata.

**Step 1: Build series plan**

Output the complete plan including:
1. Series header with type and metadata
2. Detailed breakdown per part (scope, standalone value, links)
3. Cross-linking structure (see `references/cross-linking.md`)
4. Publication schedule with dates
5. Hugo frontmatter template per part

**Step 2: Final validation**

- [ ] Every part has standalone value described
- [ ] Word counts are realistic (800-1500 per part)
- [ ] Cross-linking is complete (prev/next for all parts)
- [ ] No cliff-hangers that frustrate readers
- [ ] No filler parts
- [ ] Part count within 3-7 bounds

**Step 3: Output plan**

Use the series plan format from `references/output-format.md`.

**Gate**: All validation checks pass. Plan is complete and ready for delivery.

---

## Series Types (Summary)

Three primary types. Full templates and examples in `references/series-types.md`.

### Progressive Depth
Shallow-to-deep mastery. Each level is complete; beginners stop at Part 1, advanced readers skip ahead.

### Chronological Build
Step-by-step creation. Each part produces working output; reader can stop at any milestone.

### Problem Exploration
Journey from problem to solution. Even failed approaches are instructive; each part teaches something.

---

## Examples

### Example 1: Standard Technical Series
User says: "/series Go error handling"
Actions:
1. Assess: Topic has clear depth levels (basics, wrapping, custom types, patterns) (ASSESS)
2. Decide: Progressive Depth, 4 parts, weekly cadence (DECIDE)
3. Generate: Full plan with standalone value per part (GENERATE)
Result: 4-part series where each part teaches complete error handling at its level

### Example 2: Project Tutorial Series
User says: "/series building a CLI tool in Rust"
Actions:
1. Assess: Topic has build milestones (scaffold, commands, config, distribution) (ASSESS)
2. Decide: Chronological Build, 4 parts, weekly cadence (DECIDE)
3. Generate: Full plan with working output per milestone (GENERATE)
Result: 4-part series where each part produces a functional artifact

### Example 3: Problem Exploration Series
User says: "/series why we migrated from MongoDB to PostgreSQL"
Actions:
1. Assess: Topic has journey arc (problem, attempt, failure, solution) (ASSESS)
2. Decide: Problem Exploration, 4 parts, bi-weekly cadence (DECIDE)
3. Generate: Full plan where each part teaches standalone lessons (GENERATE)
Result: 4-part series where even failed approaches deliver instructive value

### Example 4: Topic Too Narrow
User says: "/series Go defer statement"
Actions:
1. Assess: Topic has 1-2 natural divisions, not 3+ (ASSESS)
2. Gate fails: Recommend single post or expanding scope to "Go resource management"
Result: Redirect to post-outliner or expanded topic suggestion

---

## Error Handling

### Error: "Topic Too Narrow for Series"
Cause: Topic doesn't naturally divide into 3+ parts
Solution:
1. Suggest post-outliner for single comprehensive post
2. Propose scope expansion: "Consider covering [related aspect]"
3. List what would need to be true for series to work

### Error: "Topic Too Broad for Series"
Cause: Would require 8+ parts or scope is unmanageable
Solution:
1. Identify natural breakpoints for multiple series
2. Recommend first series to tackle
3. Suggest narrowing to specific aspect

### Error: "No Logical Progression"
Cause: Parts don't build on each other meaningfully; just loosely related topics
Solution:
1. Determine if these are better as standalone posts
2. Find the connecting thread that creates progression
3. Consider if forcing series structure adds value vs. individual posts

### Error: "Standalone Value Missing"
Cause: One or more parts don't stand alone
Solution:
1. Identify which parts fail the standalone test
2. Suggest content to add for completeness
3. Or merge dependent parts into one

---

## Anti-Patterns

### Anti-Pattern 1: The Cliff-Hanger Series
**What it looks like**: "...but the real solution is in Part 2!" -- content gates behind future parts
**Why wrong**: Frustrates readers, SEO penalty for thin content, Part 2 visitors get nothing
**Do instead**: Each part delivers complete value. Reference other parts for context, not content.

### Anti-Pattern 2: The Padded Series
**What it looks like**: "Part 1: Introduction", "Part 2: Getting Started", "Part 3: Basics" -- three parts that should be one
**Why wrong**: Disrespects reader time, each part lacks substance
**Do instead**: Combine until each part has substantial, unique value. 3 meaty parts beats 6 thin ones.

### Anti-Pattern 3: The Prerequisite Spiral
**What it looks like**: "Before we start, read these 5 posts..." -- hard dependency chains
**Why wrong**: Creates barrier to entry, search traffic to later parts bounces immediately
**Do instead**: Brief context inline. Link to prerequisites as optional. Make each part accessible.

### Anti-Pattern 4: Inconsistent Scope
**What it looks like**: Part 1 is 500 words, Part 2 is 3000 words, Part 3 is 400 words
**Why wrong**: Reader expectations whiplash, suggests poor planning
**Do instead**: Keep parts roughly similar in depth and length. 800-1200 words each is the target.

### Anti-Pattern 5: Scope Creep Mid-Series
**What it looks like**: Starting with 3 planned parts, ending with 7 because "one more thing"
**Why wrong**: Breaks publishing cadence, dilutes series focus, reader fatigue
**Do instead**: Plan the full series before publishing Part 1. If scope grows, split into a second series.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "This needs 8 parts to be complete" | Scope creep; split into two series | Enforce 3-7 part limit |
| "Part 1 is just setup, real value starts Part 2" | Part 1 fails standalone test | Ensure Part 1 delivers value |
| "Readers will read them in order" | Search traffic lands anywhere | Each part must stand alone |
| "One more part won't hurt" | Padding dilutes series quality | Every part must earn its place |

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/series-types.md`: Complete type templates with examples and selection criteria
- `${CLAUDE_SKILL_DIR}/references/cross-linking.md`: Navigation patterns and Hugo implementation
- `${CLAUDE_SKILL_DIR}/references/cadence-guidelines.md`: Publishing frequency recommendations and schedules
- `${CLAUDE_SKILL_DIR}/references/output-format.md`: Series plan output format template
