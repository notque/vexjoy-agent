---
name: repo-value-analysis
description: "Analyze external repositories for adoptable ideas and patterns."
user-invocable: false
argument-hint: "<repo-url-or-path>"
agent: research-coordinator-engineer
allowed-tools:
  - Agent
  - Read
  - Write
  - Bash
  - Grep
  - Glob
routing:
  force_route: true
  triggers:
    - repo value analysis
    - does repo add value
    - analyze repo for ideas
    - what can we learn from
    - compare against repo
    - read every file in repo
    - check if repo is valuable
    - evaluate this repo
    - what can we adopt from
    - study this repo
    - clone and analyze repo
    - external repo analysis
    - skills repo evaluation
    - steal from
    - adopt from
    - assess repo
    - assess this repo
  pairs_with:
    - workflow
  complexity: Complex
  category: analysis
---

# Repo Competitive Analysis Pipeline

## Overview

This skill conducts systematic 7-phase analysis of external repositories to assess their value for adoption, then implements the findings. You dispatch parallel subagents to read and catalog every file in an external repo, inventory your own toolkit in parallel, identify genuine capability gaps, audit those gaps against your actual codebase, produce a reality-grounded comparison report, and implement HIGH-value recommendations by rebuilding them in our architecture. Use `--analyze-only` to stop at the report (Phase 6) without implementing.

The pipeline enforces **full file reading** (not sampling), **parallel execution** (up to 8 agent zones simultaneously), and **mandatory audit** (every recommendation verified before reporting). Optional flags allow local analysis (`--local`), zone focus (`--zone`), and quick comparison (`--quick` skips audit).

---

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| errors, error handling | `error-handling.md` | Loads detailed guidance from `error-handling.md`. |
| tasks related to this reference | `phase2-agent-template.md` | Loads detailed guidance from `phase2-agent-template.md`. |
| tasks related to this reference | `phase3-inventory-template.md` | Loads detailed guidance from `phase3-inventory-template.md`. |
| tasks related to this reference | `phase5-audit-template.md` | Loads detailed guidance from `phase5-audit-template.md`. |
| tasks related to this reference | `phase6-report-template.md` | Loads detailed guidance from `phase6-report-template.md`. |
| implementation, adopt, build recommendations | `phase7-implement-template.md` | Loads agent dispatch template for Phase 7 IMPLEMENT. |

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

Dispatch 1 Agent per analysis zone (background). Each agent receives the zone name and file list, instructions to read EVERY file (not sample, not skim) to avoid sampling bias, and a structured output template.

See `references/phase2-agent-template.md` for the full agent instructions template and parallel dispatch rules.

**Gate**: All zone agents have completed (or timed out after 5 minutes each). At least 75% of agents returned results (tolerance for individual agent failure). Zone finding files exist in `/tmp/`. Proceed only when gate passes.

### Phase 3: INVENTORY (Parallel with Phase 2)

**Goal**: Catalog our own toolkit simultaneously with Phase 2 deep-read for faster wall-clock time.

Dispatch 1 Agent (in background, concurrent with Phase 2 zone agents) to inventory our system. Running this in parallel is safe because inventory is a read-only catalog of our codebase.

See `references/phase3-inventory-template.md` for the full agent instructions and parallel-execution rationale.

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

For each HIGH or MEDIUM recommendation, dispatch 1 Agent (in background). Audit is what separates superficial analysis from rigorous analysis — skipping it produces unverified recommendations that erode trust.

See `references/phase5-audit-template.md` for the full audit agent instructions, coverage levels (ALREADY EXISTS / PARTIAL / MISSING), and `--quick` flag behavior.

**Gate**: All audit agents completed (or timed out after 5 minutes). At least 75% returned results. Audit files exist in `/tmp/`. Proceed only when gate passes.

### Phase 6: REPORT

**Goal**: Produce the final, reality-grounded report with recommendations verified by Phase 5 audit.

Read audit findings, adjust recommendations (ALREADY EXISTS → move to "Already Covered"; PARTIAL → focus on gaps; MISSING → keep), overwrite `research-[REPO_NAME]-comparison.md` with the final report, and remove temporary `/tmp/` files.

See `references/phase6-report-template.md` for the full 4-step workflow and final report markdown template.

**Gate**: Final report saved to `research-[REPO_NAME]-comparison.md`. Report contains comparison table, adjusted recommendations based on audit findings, and verdict. No "DRAFT" watermark remains. All recommendations have been reality-checked against Phase 5 audit findings (or marked as unaudited if --quick was used). Proceed only when gate passes.

### Phase 7: IMPLEMENT (Optional — skipped with `--analyze-only`)

**Goal**: Take HIGH-value recommendations from the Phase 6 report and rebuild them inside our architecture. This is the adoption phase — it closes the loop from "we found something valuable" to "we built our version of it."

If `--analyze-only` was passed at invocation, skip this phase entirely and deliver the Phase 6 report as the final output. The default behavior is to run Phase 7 because the whole point of this pipeline is end-to-end adoption, not just analysis.

**Step 1: Parse the final report for actionable recommendations**

Read `research-[REPO_NAME]-comparison.md` and extract all recommendations by priority:

| Priority | Action |
|----------|--------|
| **HIGH** with MISSING or PARTIAL coverage | Dispatch an implementation agent (Step 2) |
| **MEDIUM** | Add to "Future Consideration" section — do not auto-implement |
| **LOW** | Note in the implementation log — do not action |

If no HIGH recommendations exist (all gaps are MEDIUM or LOW), log the outcome and skip to the gate.

**Step 2: Dispatch implementation agents**

For each HIGH recommendation, load `references/phase7-implement-template.md` and dispatch 1 Agent with:

1. **The recommendation details** — what to build, what gap it fills, which files are affected
2. **The external repo's approach** — for reference only, not to copy. The external code is research input, not an installation source (per PHILOSOPHY.md: "External Components Are Research Inputs, Not Imports")
3. **PHILOSOPHY.md constraints** — the agent MUST read `docs/PHILOSOPHY.md` before writing any code. Key principles enforced:
   - Rebuild in our architecture: our naming, our structure, our routing model
   - Check existing components first: search `agents/`, `skills/`, `scripts/` for overlap before creating anything new ("One Domain, One Component")
   - Progressive disclosure: thin runtime files, deep content in `references/`
   - Deterministic execution: if the work can be a script, write a script
4. **Quality gates** — the agent must run applicable validation before declaring done:
   - `ruff check . --config pyproject.toml` and `ruff format --check . --config pyproject.toml` for Python
   - `python3 scripts/validate-references.py` for new agent/skill reference files
   - Verify new components are registered in INDEX files
5. **Branch discipline** — each implementation creates a feature branch (not committing to main)

Agents run in parallel where recommendations are independent. Sequential dispatch when one recommendation depends on another.

**Step 3: Collect implementation results**

For each dispatched agent, collect:
- What was built (files created or modified)
- Which quality gates passed
- Any deferred items with explicit reasons

**Step 4: Append citation to `docs/CITATIONS.md`**

After implementations complete (or after all HIGH recommendations are deferred), append a citation entry under the `## Repos` section of `docs/CITATIONS.md`. Use the Phase 6 report's comparison table and Step 3 results to populate it. The entry must follow the existing format in that file:

```markdown
### RepoName
https://github.com/org/repo

Description of what the repo is and why it was studied.

**Patterns adopted:**
- [Pattern name] ([implementation location]). Brief description of what was adopted and how it was rebuilt in our architecture.

**Patterns noted but not adopted:**
- [Pattern name]. Brief reason why it wasn't adopted.
```

Mapping rules:
- **HIGH + implemented** → "Patterns adopted" — include the specific files or components created (from Step 3 results) as the implementation location
- **HIGH + deferred** → "Patterns noted but not adopted" — state the deferral reason
- **MEDIUM** → "Patterns noted but not adopted" — state why it was not auto-implemented (e.g., "Nice to have but not high priority")
- **LOW** → "Patterns noted but not adopted" — brief note on why it was marginal

Every recommendation from the Phase 6 report must appear in exactly one of the two sections. Do not omit MEDIUM or LOW items — citation completeness tracks what was studied and why each decision was made, which prevents future re-analysis of the same repo.

**Step 5: Write implementation log**

Append an "## Implementation Results" section to `research-[REPO_NAME]-comparison.md`:

```markdown
## Implementation Results

### HIGH Recommendations — Implemented
| Recommendation | Status | Branch | Files Changed | Quality Gates |
|---------------|--------|--------|---------------|---------------|
| ... | DONE / DEFERRED | feat/... | ... | ruff PASS, validate-references PASS |

### MEDIUM Recommendations — Future Consideration
- [recommendation]: [why it's worth considering later]

### LOW Recommendations — Noted
- [recommendation]: [brief note]
```

**Gate**: All HIGH recommendations either implemented (branch created, quality gates passed) or explicitly deferred with a documented reason. Each implementation follows our architecture — no direct imports of external code. Citation entry appended to `docs/CITATIONS.md` with all recommendations mapped (HIGH adopted/deferred, MEDIUM noted, LOW noted). Implementation log appended to the report. Proceed only when gate passes.

---

## Error Handling

See `references/error-handling.md` for clone failures, large repos (10k+ files), agent timeouts, no-gaps-found outcome, and self-inventory failures.

---

## References

- `references/phase2-agent-template.md` — Phase 2 DEEP-READ agent template
- `references/phase3-inventory-template.md` — Phase 3 INVENTORY agent template
- `references/phase5-audit-template.md` — Phase 5 AUDIT agent template
- `references/phase6-report-template.md` — Phase 6 REPORT workflow and final template
- `references/phase7-implement-template.md` — Phase 7 IMPLEMENT agent dispatch template
- `references/error-handling.md` — Pipeline error handling
