---
name: repo-value-analysis
description: |
  Systematic 6-phase analysis of external repositories for ideas worth adopting:
  clone, parallel deep-read, self-inventory, synthesize gaps, targeted audit of
  affected subsystems, reality-grounded report. Use when evaluating whether an
  external repo provides value, analyzing repos for useful patterns, or
  comparing approaches.
  Do NOT use for general codebase exploration (use explore-pipeline instead).
version: 1.0.0
user-invocable: true
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

## Operator Context

This skill operates as an operator for systematic repo value analysis of external repositories against our toolkit. It implements a **6-phase Pipeline Architecture** — clone, parallel deep-read, self-inventory, synthesis, targeted audit, reality-grounded report — with parallel subagents dispatched via the Agent tool.

### Hardcoded Behaviors (Always Apply)
- **Full File Reading**: Agents MUST read every file in their assigned zone, not sample or skim
- **Artifacts at Every Phase**: Save findings to files; context is ephemeral
- **Reality-Grounding**: Every recommendation MUST be audited against our actual codebase before inclusion in the final report
- **Read-Only on External Repo**: Never modify the cloned repository
- **Comparison Focus**: All analysis is relative — "what do they have that we lack?" not "what do they have?"
- **Structured Output**: Final report follows the prescribed table format

### Default Behaviors (ON unless disabled)
- **Parallel Deep-Read**: Dispatch 1 agent per analysis zone (up to 8 zones)
- **Self-Inventory**: 1 agent catalogs our own system in parallel with deep-read
- **Zone Capping**: Cap each analysis zone at ~100 files; split larger zones
- **Draft-Then-Final**: Phase 4 saves a draft; Phase 6 overwrites with the audited final report
- **ADR Suggestion**: If HIGH-value items found, suggest creating an adoption ADR

### Optional Behaviors (OFF unless enabled)
- **Skip Clone**: Use `--local [path]` if the repo is already cloned or is a local directory
- **Focus Zone**: Use `--zone [name]` to analyze only a specific zone (e.g., skills, hooks)
- **Quick Mode**: Use `--quick` to skip Phase 5 audit (produces unverified recommendations)

## What This Skill CAN Do
- Clone and systematically analyze an external repository using parallel subagents
- Read every file across categorized analysis zones
- Inventory our own toolkit for accurate comparison
- Produce a reality-grounded comparison report with effort estimates
- Identify genuine gaps (things they have, we lack) vs superficial differences
- Suggest ADR creation for high-value adoption candidates

## What This Skill CANNOT Do
- Modify files in either repository (read-only analysis)
- Implement recommended changes (use feature-implement or systematic-refactoring)
- Analyze private repos without proper authentication configured
- Replace domain-expert judgment on adoption decisions
- Guarantee completeness for repos with 10,000+ files (zone capping applies)

---

## Instructions

### Input Parsing

Before starting Phase 1, parse the user's input:
- **GitHub URL**: Extract repo name from URL (e.g., `https://github.com/org/repo` -> `repo`)
- **Local path**: Validate the path exists and contains files
- **Bare repo name**: Assume `https://github.com/{name}` if it looks like `org/repo`

Set `REPO_NAME` and `REPO_PATH` variables for use throughout the pipeline.

### Phase 1: CLONE

**Goal**: Obtain the repository and categorize its contents into analysis zones.

**Step 1: Clone the repository**

```bash
git clone --depth 1 <url> /tmp/<REPO_NAME>
```

If `--local` flag was provided, skip cloning and use the provided path.

**Step 2: Count and categorize files**

Survey the repository structure:
- Count total files (excluding `.git/`)
- List top-level directories with file counts

**Step 3: Define analysis zones**

Categorize files into zones based on directory names and file patterns:

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

**Step 4: Cap zones**

If any zone exceeds ~100 files:
1. Split it into sub-zones by subdirectory
2. Each sub-zone gets its own agent in Phase 2
3. Log the split in the analysis notes

**Gate**: Repository cloned (or local path validated). All files categorized into zones. Zone file counts recorded. No zone exceeds ~100 files (split if needed). Proceed only when gate passes.

### Phase 2: DEEP-READ (Parallel)

**Goal**: Read every file in every zone of the external repository.

Dispatch 1 Agent per analysis zone (background). Each agent receives:
- The zone name and file list
- Instructions to read EVERY file (not sample, not skim)
- A structured output template

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

Dispatch up to 8 agents in parallel. If more than 8 zones exist, batch them (first 8, wait, then remaining).

**Gate**: All zone agents have completed (or timed out after 5 minutes each). At least 75% of agents returned results. Zone finding files exist in `/tmp/`. Proceed only when gate passes.

### Phase 3: INVENTORY (Parallel with Phase 2)

**Goal**: Catalog our own toolkit for accurate comparison.

Dispatch 1 Agent (in background, concurrent with Phase 2) to inventory our system:

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

**Gate**: Self-inventory agent completed (or timed out after 5 minutes). `/tmp/self-inventory.md` exists and contains counts for all 4 component types. Proceed only when gate passes.

### Phase 4: SYNTHESIZE

**Goal**: Merge findings from Phase 2 and Phase 3 into a comparison with candidate recommendations.

**Step 1: Read all zone findings**

Read every `/tmp/[REPO_NAME]-zone-*.md` file and `/tmp/self-inventory.md`.

**Step 2: Build comparison table**

For each capability area discovered in the external repo:

| Capability | Their Approach | Our Approach | Gap? |
|------------|---------------|--------------|------|
| ... | ... | ... | Yes/No/Partial |

**Step 3: Identify candidate recommendations**

For each genuine gap (not just a different approach to the same thing):
- Describe what they have
- Describe what we lack
- Rate value: HIGH / MEDIUM / LOW
- HIGH = addresses a real pain point or enables new capability
- MEDIUM = nice to have, improves existing workflow
- LOW = marginal improvement, different but not better

**Step 4: Save draft report**

Save to `research-[REPO_NAME]-comparison.md` with:
- Executive summary
- Comparison table
- Candidate recommendations with ratings
- Clear "DRAFT — pending audit" watermark

**Gate**: Draft report saved. At least 1 candidate recommendation identified (or explicit "no gaps found" conclusion). All recommendations have value ratings. Proceed only when gate passes.

### Phase 5: AUDIT (Parallel)

**Goal**: Reality-check each HIGH and MEDIUM recommendation against our actual codebase.

For each HIGH or MEDIUM recommendation, dispatch 1 Agent (in background):

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

**Gate**: All audit agents completed (or timed out after 5 minutes). At least 75% returned results. Audit files exist in `/tmp/`. Proceed only when gate passes.

### Phase 6: REPORT

**Goal**: Produce the final reality-grounded report.

**Step 1: Read all audit findings**

Read every `/tmp/audit-*.md` file.

**Step 2: Adjust recommendations**

For each recommendation:
- If audit found ALREADY EXISTS: remove from recommendations, note in "already covered" section
- If audit found PARTIAL: adjust description to focus on what's actually missing
- If audit found MISSING: keep as-is, add the affected files from audit

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

Remove temporary zone and audit files from `/tmp/` (keep the cloned repo for reference).

**Gate**: Final report saved to `research-[REPO_NAME]-comparison.md`. Report contains comparison table, adjusted recommendations, and verdict. No "DRAFT" watermark remains. All recommendations have been reality-checked against audit findings. Proceed only when gate passes.

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

## Anti-Patterns

### Anti-Pattern 1: Shallow Reading (Skimming Instead of Reading Every File)
**What it looks like**: Agent reads 10 of 50 files in a zone, claims to understand the zone
**Why wrong**: Misses the components that distinguish the repo; surface-level analysis produces surface-level recommendations
**Do instead**: Each agent MUST read every file in its zone. The zone capping in Phase 1 ensures this is feasible.

### Anti-Pattern 2: Recommending Things We Already Have
**What it looks like**: "They have a debugging skill; we should add one" (when we already have systematic-debugging)
**Why wrong**: Wastes effort on false gaps; undermines report credibility
**Do instead**: Phase 5 audit exists specifically to catch this. Never skip it. Every recommendation must survive audit.

### Anti-Pattern 3: Over-Counting Differences as Gaps
**What it looks like**: Listing every difference as a recommendation regardless of value
**Why wrong**: Different is not better. A different naming convention is not a gap worth addressing.
**Do instead**: Only flag genuine capability gaps — things they can do that we cannot. Rate honestly: most differences are LOW or not gaps at all.

### Anti-Pattern 4: Skipping the Audit Phase
**What it looks like**: Producing the report directly from Phase 4 synthesis without verifying
**Why wrong**: Unverified recommendations erode trust. The whole point of this pipeline is reality-grounding.
**Do instead**: Always run Phase 5 unless `--quick` was explicitly requested. Audit is what separates this from a superficial comparison.

### Anti-Pattern 5: Anchoring on Repository Size or Star Count
**What it looks like**: "This repo has 5,000 stars so it must have good ideas"
**Why wrong**: Popularity does not equal relevance to our specific toolkit
**Do instead**: Evaluate every component on its merits relative to our needs. A 10-star repo with one brilliant pattern is more valuable than a 10,000-star repo that duplicates what we have.

### Anti-Pattern 6: Generating Adoption Recommendations Without Effort Estimates
**What it looks like**: "We should adopt X" without saying how much work it would take
**Why wrong**: A HIGH-value recommendation that takes 3 weeks may be lower priority than a MEDIUM-value one that takes 30 minutes
**Do instead**: Every recommendation in the final table MUST include an effort estimate (S/M/L).

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks
- [Gate Enforcement](../shared-patterns/gate-enforcement.md) - Phase transition rules
- [Pipeline Architecture](../shared-patterns/pipeline-architecture.md) - Pipeline design principles

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "I read enough files to get the picture" | Sampling bias misses distinguishing components | Read every file in the zone |
| "Our system obviously has this" | Obvious to whom? Prove it with file paths. | Run audit agent, cite exact files |
| "This difference is clearly valuable" | Clearly to whom? Different is not better. | Rate honestly, audit against reality |
| "Audit would just confirm what I know" | Confidence is not correctness | Run audit; let evidence decide |
| "The repo is too big to read fully" | Zone capping exists for this reason | Split zones, read all files in each |
| "Quick comparison is good enough" | Quick comparisons miss nuance and produce false positives | Complete all 6 phases |
