---
name: series-planner
promoted_to: content
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
    - content
---

# Series Planner Skill

Plan multi-part content series: assess viability, select structure, produce plan with cross-linking and cadence. Three phases with strict gates.

## Deep References

| Signal | Load | Why |
|---|---|---|
| Publishing frequency, delay handling | `references/cadence-guidelines.md` | Schedule selection criteria |
| Navigation links, Hugo implementation | `references/cross-linking.md` | Prev/next nav, shortcodes, landing pages |
| Plan output format | `references/output-format.md` | Complete plan template |
| Series types, selection matrix | `references/series-types.md` | Three type templates with examples |

## Usage

```
/series [topic]
/series --type=progressive [topic]     # Force type
/series --parts=5 [topic]              # Target count
/series --with-landing [topic]         # Include landing page
/series --minimal [topic]              # Titles and scope only
```

## Phase 1: ASSESS

Determine viability and natural divisions.

1. Analyze topic: scope (narrow/medium/broad), natural divisions, audience progression.
2. Check viability: minimum 3 distinct subtopics, each stands alone, logical progression exists, no filler.
3. Detect series type:

| Signal | Type |
|--------|------|
| learn, master, deep dive | Progressive Depth |
| build, create, project | Chronological Build |
| why we chose, migration, debugging | Problem Exploration |

**Gate**: 3+ natural divisions identified. If fewer, recommend single post or scope adjustment.

## Phase 2: DECIDE

Select type, part count (strict 3-7 bounds), and structure.

1. Select type and justify. Define part count and word estimate.
2. Draft breakdown per part: title, scope (1 sentence), standalone value, adjacent links.
3. Validate standalone value for every part:
   - Reader learns something complete and actionable from this part alone
   - Working code/config/output possible without other parts
   - No critical info deferred to other parts
   - Search landing on this part alone yields value

Red flags (reject): "read Part 1 first" dependency, mid-implementation endings, concepts only in earlier parts.

4. Select cadence (see `references/cadence-guidelines.md`). Default: weekly.

**Gate**: All parts pass standalone test. Part count 3-7. Type justified.

## Phase 3: GENERATE

Produce the complete plan.

1. Build plan: series header, per-part breakdown, cross-linking (see `references/cross-linking.md`), publication dates, Hugo frontmatter.
2. Final validation checklist:
   - Every part has standalone value
   - Word counts 800-1500/part, within 20% variance
   - Cross-linking complete (prev/next for all)
   - No cliff-hangers, no filler
   - Part count within bounds
3. Output using `references/output-format.md` format.

**Gate**: All checks pass. Plan complete.

## Series Types

| Type | Structure | Reader flexibility |
|------|-----------|-------------------|
| **Progressive Depth** | Shallow to deep mastery | Beginners stop at Part 1; advanced skip ahead |
| **Chronological Build** | Step-by-step creation | Each part produces working output |
| **Problem Exploration** | Problem to solution journey | Even failed approaches are instructive |

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| Topic too narrow | Fewer than 3 natural divisions | Recommend single post or scope expansion |
| Topic too broad | Would need 8+ parts | Split into multiple series; narrow scope |
| No logical progression | Parts are loosely related, not building | Consider standalone posts instead of series |
| Standalone value missing | Parts depend on each other | Merge dependent parts or add context inline |
