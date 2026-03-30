---
name: do-perspectives
description: |
  Inline multi-perspective analysis: 10 analytical lenses applied sequentially
  in a single session to extract patterns and improve agents or skills. Use when
  user invokes /do-perspectives, wants comprehensive multi-angle analysis of
  source material, or needs cost-effective pattern extraction from articles,
  docs, or code. Do NOT use for simple single-target improvements,
  parallel analysis (use /do with parallel-analysis reference), or tasks without source material.
version: 2.0.0
user-invocable: false
argument-hint: "<target-name> <source-path>"
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
    - multi-perspective analysis
    - do-perspectives
    - analyze from multiple angles
  pairs_with:
    - anti-ai-editor
    - voice-validator
  complexity: Medium
  category: content
---

# Multi-Perspective Analysis Skill

This skill extracts actionable patterns from source material through sequential analysis of 10 analytical frameworks. It operates as a **Pipeline** with four gates: VALIDATE INPUTS → MULTI-PERSPECTIVE ANALYSIS → SYNTHESIZE → APPLY.

## Instructions

**$ARGUMENTS** - Target agent/skill name + source material path (file path or inline text)

### Phase 1: VALIDATE INPUTS

**Goal**: Confirm target exists and source material is loaded before any analysis.

**Hardcoded requirement** (always apply): Source material must be loaded and verified before proceeding. This prevents wasted analysis cycles on empty or invalid input.

**Step 1: Parse arguments**
- First argument: target agent or skill name
- Second argument: source material file path or inline text

**Step 2: Verify target**
- Check that the target agent or skill file exists in the repository
- Read its current content to understand what will be improved

**Step 3: Load source material**
- If file path: read and verify file is non-empty
- If inline text: confirm sufficient content for analysis (minimum ~500 words)
- Estimate token budget based on source material length (target: 10,000-15,000 tokens total; flag if source material will exceed budget)

**Gate**: Target exists and is readable. Source material is loaded and non-trivial. Proceed only when gate passes.

### Phase 2: MULTI-PERSPECTIVE ANALYSIS

**Goal**: Analyze source material through all 10 analytical lenses, producing documented findings for each.

**Hardcoded requirement** (always apply): Complete all 10 perspectives. No skipping perspectives because "enough patterns found." Later perspectives often surface non-obvious patterns that earlier ones miss. The value of 10 lenses is comprehensiveness. If a perspective yields low signal, mark it as such in the report, but still complete the analysis.

**Default behavior** (ON unless disabled): For each perspective, include cross-reference tracking — note when multiple perspectives surface the same pattern. This reveals high-confidence rules.

For each perspective, produce output in this format:

```markdown
## [Perspective Name] Analysis

**Key Observations**:
1. [Observation with specific example from source]
2. [Observation with specific example from source]
3. [Observation with specific example from source]

**Extracted Rules**:
1. [Actionable rule for target]
2. [Actionable rule for target]
3. [Actionable rule for target]

**Cross-References**: [Patterns also seen in perspectives X, Y]
```

**The 10 Analytical Lenses**:

1. **Structural Analysis** -- Document organization, hierarchy, information architecture, complexity scaffolding
2. **Clarity and Precision** -- Language clarity, ambiguity elimination, term definitions, precision techniques
3. **Technical Explanation Patterns** -- Concept introduction, simplification strategies, analogy usage, layered explanation
4. **Audience Assumption Patterns** -- Assumed vs explained knowledge, jargon handling, progressive disclosure
5. **Evidence and Citation Strategy** -- Claim support, concrete examples, authority establishment, data usage
6. **Narrative Progression** -- Story arc, engagement techniques, hooks and payoffs, tension and resolution
7. **Paragraph and Sentence Architecture** -- Length variety, rhythm, topic sentences, cadence patterns
8. **Header and Signposting Strategy** -- Section naming, previews, reader orientation, navigation patterns
9. **Complexity Management** -- Approach to difficult topics, gradual escalation, when to be thorough vs concise
10. **Limitation and Nuance Handling** -- Caveats, edge cases, uncertainty acknowledgment, trade-off presentation

**Constraints on analysis output**:
- 200-500 words per perspective (focused, not padded): Over-engineering prevention applies here. Extract actionable patterns only. No speculative rules, no "might be useful" additions.
- 3-5 extracted rules per perspective
- Each perspective MUST reference specific content from the source material, not generic observations that could apply anywhere. Generic rules add no value. The purpose is extracting patterns specific to the source material.
- Cross-references to other perspectives are encouraged but optional

**Gate**: All 10 perspectives documented with observations, rules, and source references. Proceed only when gate passes.

### Phase 3: SYNTHESIZE

**Goal**: Unify findings across all perspectives into priority-ranked recommendations.

**Hardcoded requirement** (always apply): Synthesis before application. Complete the synthesis phase before applying any improvements. Without synthesis, you apply every extracted rule equally. Priority ranking prevents over-engineering and focuses on high-signal patterns.

**Step 1: Identify common themes**
- Patterns that appeared in 4+ perspectives are high-signal (supported by multiple lenses)
- Note convergence and reinforcement across lenses

**Step 2: Extract unique insights**
- Patterns that appeared in only 1-2 perspectives but have high impact
- These are the non-obvious findings that justify multi-perspective analysis

**Step 3: Create priority ranking**

```markdown
# Synthesized Recommendations

## Must-Have (Priority 1)
Rules supported by 7+ perspectives or critical impact
1. [Rule] -- supported by perspectives: [list]
2. [Rule] -- supported by perspectives: [list]

## Should-Have (Priority 2)
Rules supported by 4-6 perspectives or high impact
1. [Rule] -- supported by perspectives: [list]

## Nice-to-Have (Priority 3)
Rules supported by 1-3 perspectives or moderate impact
1. [Rule] -- supported by perspectives: [list]

## Implementation Guidance
[Specific sections to add or modify in target]
[Concrete templates or examples]
```

**Gate**: Synthesis complete with priority-ranked rules and implementation guidance. Proceed only when gate passes.

### Phase 4: APPLY

**Goal**: Improve the target agent or skill using synthesized recommendations.

**Hardcoded requirement** (always apply): Do NOT remove existing working patterns. Existing patterns were validated through prior use. New patterns should augment, not replace. Only modify existing content when source material provides a strictly better approach.

**Step 1: Read current target**
- Load the current agent or skill file
- Identify which sections map to Priority 1 and 2 recommendations

**Step 2: Apply improvements**
- Focus on Priority 1 (Must-Have) and Priority 2 (Should-Have)
- Add new sections or enhance existing sections based on recommendations
- Include concrete examples from source material where applicable
- Do NOT remove existing working patterns

**Step 3: Validate integration**
- Verify improvements integrate naturally with existing content
- Check that new content follows the target's existing style and format
- Confirm YAML frontmatter is valid if modified

**Gate**: Target updated with synthesized improvements. Changes are coherent and integrated. Proceed only when gate passes.

### Phase 5: VERIFY AND REPORT

**Goal**: Confirm changes are valid and generate completion report.

**Default behavior** (ON unless disabled): Generate structured completion report showing all phases, findings, and changes. This artifact serves as a reference for future improvements.

**Step 1: Verify file**
- Re-read the modified file to confirm it is well-formed
- Check YAML frontmatter parses correctly
- Confirm no content was accidentally removed

**Step 2: Create git commit**
- Stage changes with descriptive commit message
- Include which perspectives drove the improvements

**Step 3: Generate completion report**

```markdown
# Multi-Perspective Analysis -- Completion Report

**Target**: [name] ([agent/skill])
**Source Material**: [path or description]
**Token Budget**: ~[estimate] tokens

## Phase 1: Validation
- Target: [confirmed]
- Source: [confirmed, word count]

## Phase 2: Analysis
[1-line summary per perspective with key finding]

**Total Rules Extracted**: [count] across 10 perspectives

## Phase 3: Synthesis
- Common Themes: [count]
- Priority 1 (Must-Have): [count] rules
- Priority 2 (Should-Have): [count] rules
- Priority 3 (Nice-to-Have): [count] rules

## Phase 4: Application
- Lines Added: +[count]
- New Sections: [count]
- Key Improvements: [list]

## Phase 5: Verification
- File well-formed: [yes/no]
- Git commit: [hash]
```

**Gate**: Report generated. All phases documented. Task complete.

---

## Examples

### Example 1: Improve Agent from Article
User says: "/do-perspectives technical-journalist-writer article.md"
Actions:
1. Verify agent exists, load article.md (VALIDATE)
2. Analyze article through all 10 lenses (ANALYZE)
3. Synthesize: 4 must-have rules, 6 should-have, 3 nice-to-have (SYNTHESIZE)
4. Apply Priority 1 and 2 rules to agent file (APPLY)
5. Verify file, commit, report (VERIFY)
Result: Agent enhanced with patterns extracted from expert writing

### Example 2: Improve Skill from Documentation
User says: "/do-perspectives go-testing golang-testing-guide.md"
Actions:
1. Verify skill exists, load guide (VALIDATE)
2. Analyze guide through structural, technical, complexity lenses etc. (ANALYZE)
3. Synthesize testing patterns into ranked recommendations (SYNTHESIZE)
4. Add new testing patterns and examples to skill (APPLY)
5. Verify, commit, report (VERIFY)
Result: Testing skill enriched with methodology from expert documentation

---

## Error Handling

### Error: "Target Agent/Skill Not Found"
Cause: Name does not match any file in agents/ or skills/ directories
Solution:
1. List available agents and skills with glob search
2. Suggest closest matches to the provided name
3. Ask user to confirm correct target before proceeding

### Error: "Source Material Too Short or Empty"
Cause: File path wrong, file empty, or inline text insufficient
Solution:
1. Verify file path is absolute and correct
2. If file exists but is empty, report to user
3. If inline text is under ~500 words, warn that analysis will be shallow

### Error: "Token Budget Exceeded"
Cause: Source material is very long, producing excessive analysis
Solution:
1. Summarize source material before analysis (extract key sections)
2. Reduce per-perspective output to 200 words
3. If still too large, suggest splitting into multiple runs

---

## References

- [CLAUDE.md Compliance](../../../CLAUDE.md) - Verification over assumption, artifacts over memory, authentic over polished
- Pipeline Architecture pattern - Phase-based execution with gates
- Sequential analysis constraints - Cross-contamination inherent in sequential analysis (see skills/do/references/parallel-analysis.md for zero cross-contamination alternative)
