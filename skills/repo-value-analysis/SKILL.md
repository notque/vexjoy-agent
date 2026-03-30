---
name: repo-value-analysis
description: "Analyze external repositories for adoptable ideas and patterns."
version: 1.0.0
user-invocable: false
argument-hint: "<repo-url-or-path>"
agent: research-coordinator-engineer
model: opus
allowed-tools:
  - Agent
  - Read
  - Write
  - Bash
  - Grep
  - Glob
routing:
  triggers:
    - repo value analysis
    - does repo add value
    - analyze repo for ideas
    - what can we learn from
    - compare against repo
    - read every file in repo
  pairs_with:
    - explore-pipeline
  complexity: Complex
  category: analysis
---

# Repo Competitive Analysis Pipeline

## Overview

This skill conducts systematic 6-phase analysis of external repositories to assess their value for adoption. You dispatch parallel subagents to read and catalog every file in an external repo, inventory your own toolkit in parallel, identify genuine capability gaps, audit those gaps against your actual codebase, and produce a reality-grounded comparison report with adoption recommendations.

The pipeline enforces **full file reading** (not sampling), **parallel execution** (up to 8 agent zones simultaneously), and **mandatory audit** (every recommendation verified before reporting). Optional flags allow local analysis (`--local`), zone focus (`--zone`), and quick comparison (`--quick` skips audit).

---

## Instructions

### Input Parsing

Before starting Phase 1, parse the user's input:
- **GitHub URL**: Extract repo name from URL (e.g., `https://github.com/org/repo` -> `repo`)
- **Local path**: Validate the path exists and contains files
- **Bare repo name**: Assume `https://github.com/{name}` if it looks like `org/repo`

Set `REPO_NAME` and `REPO_PATH` variables for use throughout the pipeline.

### Phase 1: CLONE

**Goal**: Obtain the repository and categorize its contents into zones for parallel deep-read.

**Step 1: Clone the repository**

```bash
git clone --depth 1 <url> /tmp/<REPO_NAME>
```

If `--local` flag was provided, skip cloning and use the provided path instead. This allows re-analysis of already-cloned repos without redundant network calls.

**Step 2: Count and categorize files**

Survey the repository structure:
- Count total files (excluding `.git/`)
- List top-level directories with file counts

This gives you a baseline for zone complexity and helps identify sub-repo patterns.

**Step 3: Define analysis zones**

Categorize files into zones based on directory names and file patterns. Zones organize the repo into digestible chunks:

| Zone | Typical directories/patterns | Purpose |
|------|------------------------------|---------|
| skills | `skills/`, `commands/`, `prompts/`, `templates/` | Reusable skill/prompt definitions |
| agents | `agents/`, `personas/`, `roles/` | Agent configurations |
| hooks | `hooks/`, `middleware/`, `interceptors/` | Event-driven automation |
| docs | `docs/`, `*.md` (non-config), `adr/`, `guides/` | Documentation and decisions |
| tests | `tests/`, `*_test.*`, `*.spec.*`, `__tests__/` | Test suites |
| config | Config files, CI/CD, `*.yaml`, `*.toml`, `*.json` (root) | Configuration |
| code | `scripts/`, `src/`, `lib/`, `pkg/`, `*.py`, `*.go`, `*.ts` | Source code |
| other | Everything else | Uncategorized files |

**Step 4: Cap zones for parallel feasibility**

If any zone exceeds ~100 files, split it into sub-zones by subdirectory. Each sub-zone gets its own agent in Phase 2. Cap at ~100 files per agent because:
- Agents MUST read **every file** in their zone, not sample or skim (sampling introduces bias and misses distinguishing components)
- ~100 files is feasible for a single agent within budget and timeout
- Larger zones are split, so no single agent is overwhelmed

Log the split decisions in the analysis notes for transparency.

**Gate**: Repository cloned (or local path validated). All files categorized into zones. Zone file counts recorded. No zone exceeds ~100 files (split if needed). Proceed only when gate passes.

### Phase 2: DEEP-READ (Parallel)

**Goal**: Read every file in every zone of the external repository to extract techniques, patterns, and potential capability gaps.

Dispatch 1 Agent per analysis zone (background). Each agent receives:
- The zone name and file list
- Instructions to read EVERY file (not sample, not skim) to avoid sampling bias
- A structured output template that captures what they have, not just what they are

**Agent instructions template** (replace ALL bracketed placeholders with actual values before dispatching):

```
You are analyzing the "[zone]" zone of repository [REPO_NAME].

Read EVERY file listed below. For each file, extract:
1. Purpose (1-2 sentences)
2. Key techniques or patterns used
3. Notable or unique approaches
4. Dependencies on other components

Files to read:
[file list]

After reading ALL files, produce a structured summary:

## Zone: [zone]
### Component Inventory
| File | Purpose | Key Pattern |
|------|---------|-------------|
| ... | ... | ... |

### Key Techniques
- [technique]: [which files use it, how]

### Notable Patterns
- [pattern]: [why it's notable]

### Potential Gaps They Fill
- [gap]: [what capability this provides that might be missing elsewhere]

Save your findings to /tmp/[REPO_NAME]-zone-[zone].md
```

Dispatch up to 8 agents in parallel for speed. If more than 8 zones exist, batch them (first 8, wait 5 minutes, then remaining) rather than serializing — parallel dispatch is default unless `--quick` flag requests otherwise.

**Gate**: All zone agents have completed (or timed out after 5 minutes each). At least 75% of agents returned results (tolerance for individual agent failure). Zone finding files exist in `/tmp/`. Proceed only when gate passes.

### Phase 3: INVENTORY (Parallel with Phase 2)

**Goal**: Catalog our own toolkit simultaneously with Phase 2 deep-read for faster wall-clock time.

Dispatch 1 Agent (in background, concurrent with Phase 2 zone agents) to inventory our system. Running this in parallel is safe because inventory is a read-only catalog of our codebase:

```
You are cataloging the claude-code-toolkit repository for comparison purposes.

Inventory these component types:
1. Agents (agents/*.md) - count and list with brief descriptions
2. Skills (skills/*/SKILL.md) - count and list with brief descriptions
3. Hooks (hooks/*.py) - count and list with brief descriptions
4. Scripts (scripts/*.py) - count and list with brief descriptions

For each category, note:
- Total count
- Key capability areas covered
- Notable patterns in how components are structured

Save your inventory to /tmp/self-inventory.md
```

Running this in parallel (not waiting for Phase 2 to finish) reduces total pipeline time from `Phase1 + Phase2 + Phase3` to roughly `Phase1 + max(Phase2, Phase3)`.

**Gate**: Self-inventory agent completed (or timed out after 5 minutes). `/tmp/self-inventory.md` exists and contains counts for all 4 component types. Proceed only when gate passes.

### Phase 4: SYNTHESIZE

**Goal**: Merge Phase 2 and Phase 3 findings into a draft comparison with candidate adoption recommendations.

**Step 1: Read all zone findings and inventory**

Read every `/tmp/[REPO_NAME]-zone-*.md` file and `/tmp/self-inventory.md` to build a unified picture.

**Step 2: Build comparison table**

For each capability area discovered in the external repo, document what we have vs what they have:

| Capability | Their Approach | Our Approach | Gap? |
|------------|---------------|--------------|------|
| ... | ... | ... | Yes/No/Partial |

This table is relative: "what do they have that we lack?" not "what do they have?"

**Step 3: Identify candidate recommendations**

For each genuine gap (not just a different approach to the same thing):
- Describe what they have
- Describe what we lack
- Rate value honestly: HIGH / MEDIUM / LOW
  - HIGH = addresses a real pain point or enables new capability
  - MEDIUM = nice to have, improves existing workflow
  - LOW = marginal improvement, different but not better

Resist the temptation to over-count differences as gaps. A different naming convention is not a gap worth addressing.

**Step 4: Save draft report**

Save to `research-[REPO_NAME]-comparison.md` with:
- Executive summary
- Comparison table
- Candidate recommendations with ratings
- Clear "DRAFT — pending Phase 5 audit" watermark

This draft is intentionally unaudited so you can bail out early if findings look weak.

**Gate**: Draft report saved. At least 1 candidate recommendation identified (or explicit "no gaps found" conclusion). All recommendations have value ratings. Proceed only when gate passes.

### Phase 5: AUDIT (Parallel)

**Goal**: Reality-check each HIGH and MEDIUM recommendation against our actual codebase to catch "we already have this" false positives.

For each HIGH or MEDIUM recommendation, dispatch 1 Agent (in background). Audit is what separates superficial analysis from rigorous analysis — skipping it produces unverified recommendations that erode trust:

```
You are auditing whether recommendation "[recommendation]" is already
addressed in the claude-code-toolkit repository.

The recommendation suggests: [description]

Your task:
1. Search the repository for components that address this capability
2. Read the SPECIFIC files/subsystems that would be affected
3. Determine coverage level:
   - ALREADY EXISTS: We have this. Cite the exact files.
   - PARTIAL: We have something similar but incomplete. Cite files and gaps.
   - MISSING: We genuinely lack this. Confirm by searching for related patterns.
4. If PARTIAL or MISSING, identify the exact files that would need to change

Save findings to /tmp/audit-[recommendation-slug].md with:
## Recommendation: [name]
### Coverage: [ALREADY EXISTS | PARTIAL | MISSING]
### Evidence
- [file path]: [what it does / doesn't do]
### Verdict
[1-2 sentence conclusion]
```

Dispatch audit agents in parallel for speed. If `--quick` flag was used in the initial call, skip Phase 5 entirely and proceed directly to Phase 6 with unaudited recommendations (noted in final report as unverified).

**Gate**: All audit agents completed (or timed out after 5 minutes). At least 75% returned results. Audit files exist in `/tmp/`. Proceed only when gate passes.

### Phase 6: REPORT

**Goal**: Produce the final, reality-grounded report with recommendations verified by Phase 5 audit.

**Step 1: Read all audit findings (unless --quick was used)**

Read every `/tmp/audit-*.md` file. If `--quick` flag was used, skip this step and note in the report that recommendations are unaudited.

**Step 2: Adjust recommendations based on audit coverage**

For each recommendation:
- If audit found ALREADY EXISTS: remove from recommendations, note in "Already Covered" section with the exact files
- If audit found PARTIAL: adjust description to focus on what's actually missing, cite the partial files
- If audit found MISSING: keep as-is, add the affected files from audit

This adjustment step catches the false positive anti-pattern: "we should adopt X" when we already have X.

**Step 3: Build final report**

Overwrite `research-[REPO_NAME]-comparison.md` with the final report:

```markdown
# Competitive Analysis: [REPO_NAME] vs claude-code-toolkit

## Executive Summary
[2-3 sentences: what the repo is, whether it adds value, headline finding]

## Repository Overview
- **URL**: [url]
- **Total files analyzed**: [count]
- **Analysis zones**: [list with counts]
- **Analysis date**: [date]

## Comparison Table

| Capability | Their Approach | Our Approach | Status |
|------------|---------------|--------------|--------|
| ... | ... | ... | Equivalent / They lead / We lead / Unique to them |

## Already Covered
[Capabilities we initially thought were gaps but audit confirmed we have]

| Capability | Our Implementation | Files |
|------------|-------------------|-------|
| ... | ... | ... |

## Recommendations

| # | Recommendation | Value | What We Have | What's Missing | Effort | Affected Files |
|---|---------------|-------|--------------|----------------|--------|----------------|
| 1 | ... | HIGH | ... | ... | S/M/L | ... |

## Verdict
[Final assessment: is this repo worth adopting ideas from? Which specific items?]

## Next Steps
- [ ] [Actionable items]
- [ ] [If HIGH-value items: "Create ADR for adoption of [specific items]"]
```

**Step 4: Cleanup**

Remove temporary zone and audit files from `/tmp/` (keep the cloned repo for reference if further investigation is needed).

**Gate**: Final report saved to `research-[REPO_NAME]-comparison.md`. Report contains comparison table, adjusted recommendations based on audit findings, and verdict. No "DRAFT" watermark remains. All recommendations have been reality-checked against Phase 5 audit findings (or marked as unaudited if --quick was used). Proceed only when gate passes.

---

## Error Handling

### Error: "Repository Clone Failed"
Cause: Invalid URL, private repo, network issue, or repo doesn't exist
Solution:
1. Verify the URL is correct and the repo is public
2. If private, check that git credentials are configured
3. If network issue, retry once after 5 seconds
4. If repo doesn't exist, report to user and abort pipeline

### Error: "Repository Too Large (10,000+ files)"
Cause: Monorepo or very large codebase
Solution:
1. Increase zone capping to split aggressively (sub-zones of ~50 files)
2. Prioritize zones most relevant to our toolkit (skills, agents, hooks, docs)
3. Deprioritize vendor, generated, and third-party code zones
4. Note incomplete coverage in the final report

### Error: "Agent Timed Out in Phase 2/5"
Cause: Zone too large, agent stuck on binary/generated files
Solution:
1. Proceed with results from completed agents (minimum 75% required)
2. Note which zones/audits were incomplete in the report
3. If below 75%, retry failed zones with smaller file batches

### Error: "No Gaps Found"
Cause: External repo covers the same ground or less than ours
Solution:
1. This is a valid outcome, not an error
2. Report confirms our toolkit already covers or exceeds the external repo
3. Note any interesting alternative approaches even if not gaps
4. Skip Phase 5 (no recommendations to audit)

### Error: "Self-Inventory Agent Failed"
Cause: Our own repo structure changed or agent timed out
Solution:
1. Fall back to reading `skills/INDEX.json` for skill counts
2. Use `ls agents/ hooks/ scripts/` for basic counts
3. Note that self-inventory is approximate in the report

---

## References

None. This skill is self-contained and does not reference shared patterns or external documentation.
