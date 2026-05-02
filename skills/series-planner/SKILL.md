---
name: series-planner
description: "Plan multi-part content series: structure, cross-linking, cadence."
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
    - "article series"
    - "content arc"
  category: content-creation
  pairs_with:
    - content-calendar
    - topic-brainstormer
    - publish
---

# Series Planner Skill

Three-phase workflow: **ASSESS** (viability), **DECIDE** (structure), **GENERATE** (plan). Gates prevent scope creep, enforce standalone value, and maintain quality.

---

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| tasks related to this reference | `cadence-guidelines.md` | Loads detailed guidance from `cadence-guidelines.md`. |
| tasks related to this reference | `cross-linking.md` | Loads detailed guidance from `cross-linking.md`. |
| tasks related to this reference | `output-format.md` | Loads detailed guidance from `output-format.md`. |
| tasks related to this reference | `series-types.md` | Loads detailed guidance from `series-types.md`. |

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

**Goal**: Determine series viability and identify natural divisions.

**Step 1: Analyze topic**

```markdown
## Series Assessment
Topic: [user-provided topic]
Scope: [narrow / medium / broad]
Natural divisions: [how this topic breaks apart]
Audience progression: [beginner to expert? single level?]
```

**Step 2: Check viability**

- Minimum 3 distinct subtopics (non-negotiable)
- Each division stands alone as complete content
- Logical progression exists between parts
- No artificial padding -- each part earns its place

**Step 3: Detect series type**

Match topic signals to type. See `references/series-types.md` for full templates.

| Signal | Type |
|--------|------|
| "learn", "master", "deep dive" | Progressive Depth |
| "build", "create", "project" | Chronological Build |
| "why we chose", "migration", "debugging" | Problem Exploration |

**Gate**: 3+ natural divisions identified. If topic fails, recommend single post or scope adjustment.

### Phase 2: DECIDE

**Goal**: Select series type, part count, and structure.

**Step 1: Select type and justify**

```markdown
## Series Decision
Type: [Progressive Depth / Chronological Build / Problem Exploration]
Justification: [why this type fits]
Part Count: [3-7, enforced strictly]
Total Estimated Words: [X,XXX - X,XXX]
```

Part count: minimum 3, maximum 7, no exceptions.

**Step 2: Draft part breakdown**

Per part: title and scope (1 sentence), standalone value (what reader learns alone), forward/backward links.

**Step 3: Validate standalone value**

Every part must pass:
- Reader learns something complete and actionable
- Working code/config/output possible from this part alone
- No critical information deferred to other parts
- Someone landing via search gets value

Red flags (reject any part showing these):
- "To understand this, read Part 1 first" as mandatory dependency
- Part ends mid-implementation with "Part 2 will continue"
- Core concepts explained only in earlier parts

**Step 4: Select publishing cadence**

See `references/cadence-guidelines.md`. Default weekly unless complexity suggests otherwise.

**Gate**: All parts pass standalone check. Part count 3-7. Type justified.

### Phase 3: GENERATE

**Goal**: Produce the complete series plan.

**Step 1: Build series plan**

1. Series header with type and metadata
2. Detailed per-part breakdown (scope, standalone value, links)
3. Cross-linking structure (see `references/cross-linking.md`)
4. Publication schedule with dates
5. Hugo frontmatter template per part

**Step 2: Final validation**

- [ ] Every part has standalone value described
- [ ] Word counts realistic (800-1500 per part, within 20% variance)
- [ ] Cross-linking complete (prev/next for all parts)
- [ ] No cliff-hangers
- [ ] No filler parts
- [ ] Part count within 3-7

**Step 3: Output plan**

Use format from `references/output-format.md`.

**Gate**: All validation checks pass. Plan complete.

---

## Series Types (Summary)

Full templates in `references/series-types.md`.

### Progressive Depth
Shallow-to-deep mastery. Each level complete; beginners stop at Part 1, advanced skip ahead.

### Chronological Build
Step-by-step creation. Each part produces working output; reader stops at any milestone with a working artifact.

### Problem Exploration
Journey from problem to solution. Failed approaches are instructive; each part teaches something standalone.

---

## Error Handling

### Topic Too Narrow
Cause: Fewer than 3 natural divisions.
Solution: Suggest publish (outline intent) for single post. Propose scope expansion. List what 3+ parts would require.

### Topic Too Broad
Cause: Would require 8+ parts.
Solution: Identify breakpoints for multiple series. Recommend first series (smallest, highest value). Suggest narrowing.

### No Logical Progression
Cause: Parts loosely related, not building on each other.
Solution: Determine if standalone posts are better. Find connecting thread. Evaluate whether series structure adds value.

### Standalone Value Missing
Cause: Parts depend on previous parts.
Solution: Identify failing parts. Suggest content additions for completeness. Or merge dependent parts.

---

## References

### Reference Files
- `${CLAUDE_SKILL_DIR}/references/series-types.md`: Type templates with examples and selection criteria
- `${CLAUDE_SKILL_DIR}/references/cross-linking.md`: Navigation patterns and Hugo implementation
- `${CLAUDE_SKILL_DIR}/references/cadence-guidelines.md`: Publishing frequency recommendations
- `${CLAUDE_SKILL_DIR}/references/output-format.md`: Series plan output format template

### Key Constraints

1. **Part Count (3-7)**: Prevents scope creep and false series.
2. **Standalone Value**: Every part delivers complete value to readers landing via search. No cliff-hangers, deferred concepts, or mid-implementation endings.
3. **No Filler**: Each part earns its place with substantial unique content.
4. **Logical Progression**: Parts build meaningfully. Loosely related topics should not be a series.
5. **No Over-Engineering**: Plan only what requested. No bonus parts or scope creep.
