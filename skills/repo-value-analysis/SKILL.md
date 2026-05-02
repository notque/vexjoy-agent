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

7-phase pipeline: clone external repo, dispatch parallel subagents to read every file, inventory our toolkit in parallel, identify capability gaps, audit gaps against our codebase, produce a reality-grounded report, and implement HIGH-value recommendations by rebuilding in our architecture. Use `--analyze-only` to stop at Phase 6.

Enforces **full file reading** (not sampling), **parallel execution** (up to 8 zones), and **mandatory audit** (every recommendation verified). Optional flags: `--local` (skip clone), `--zone` (focus), `--quick` (skip audit).

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

Before Phase 1, parse:
- **GitHub URL**: Extract repo name (e.g., `https://github.com/org/repo` -> `repo`)
- **Local path**: Validate path exists
- **Bare repo name**: Assume `https://github.com/{name}` if it looks like `org/repo`

Set `REPO_NAME` and `REPO_PATH` for the pipeline.

### Phase 1: CLONE

**Goal**: Obtain repo and categorize contents into zones for parallel deep-read.

**Step 1: Clone**

```bash
git clone --depth 1 <url> /tmp/<REPO_NAME>
```

With `--local`, skip clone and use provided path.

**Step 2: Count and categorize**

Count total files (excluding `.git/`), list top-level directories with file counts.

**Step 3: Define analysis zones**

| Zone | Typical patterns | Purpose |
|------|-----------------|---------|
| skills | `skills/`, `commands/`, `prompts/`, `templates/` | Skill/prompt definitions |
| agents | `agents/`, `personas/`, `roles/` | Agent configurations |
| hooks | `hooks/`, `middleware/`, `interceptors/` | Event-driven automation |
| docs | `docs/`, `*.md`, `adr/`, `guides/` | Documentation |
| tests | `tests/`, `*_test.*`, `*.spec.*`, `__tests__/` | Test suites |
| config | Config files, CI/CD, `*.yaml`, `*.toml`, `*.json` (root) | Configuration |
| code | `scripts/`, `src/`, `lib/`, `pkg/`, `*.py`, `*.go`, `*.ts` | Source code |
| other | Everything else | Uncategorized |

**Step 4: Cap zones**

If any zone exceeds ~100 files, split by subdirectory. Agents MUST read **every file** in their zone (sampling introduces bias). ~100 files is feasible per agent. Log split decisions.

**Gate**: Repo cloned/validated. All files zoned. No zone >~100 files.

### Phase 2: DEEP-READ (Parallel)

**Goal**: Read every file in every zone to extract techniques, patterns, and gaps.

Dispatch 1 Agent per zone (background). Each gets zone name, file list, instructions to read EVERY file, and structured output template.

See `references/phase2-agent-template.md` for agent template and dispatch rules.

**Gate**: All zone agents completed (or timed out at 5min). >=75% returned results. Zone findings in `/tmp/`.

### Phase 3: INVENTORY (Parallel with Phase 2)

**Goal**: Catalog our toolkit concurrently with Phase 2.

Dispatch 1 Agent (background, concurrent with Phase 2) to inventory our system. Safe: inventory is read-only.

See `references/phase3-inventory-template.md` for agent template.

**Gate**: Inventory agent completed (or timed out at 5min). `/tmp/self-inventory.md` exists with counts for all 4 component types.

### Phase 4: SYNTHESIZE

**Goal**: Merge Phase 2+3 findings into draft comparison with adoption candidates.

**Step 1**: Read all `/tmp/[REPO_NAME]-zone-*.md` and `/tmp/self-inventory.md`.

**Step 2: Build comparison table**

| Capability | Their Approach | Our Approach | Gap? |
|------------|---------------|--------------|------|
| ... | ... | ... | Yes/No/Partial |

Focus: "what do they have that we lack?" not "what do they have?"

**Step 3: Identify candidates**

Per genuine gap (not just a different approach):
- Describe what they have / what we lack
- Rate: HIGH (real pain point or new capability), MEDIUM (nice-to-have), LOW (marginal)

Resist over-counting differences as gaps.

**Step 4: Save draft**

Save `research-[REPO_NAME]-comparison.md` with executive summary, comparison table, rated candidates, and "DRAFT -- pending Phase 5 audit" watermark.

**Gate**: Draft saved. >=1 candidate (or explicit "no gaps found"). All rated.

### Phase 5: AUDIT (Parallel)

**Goal**: Reality-check each HIGH/MEDIUM recommendation against our codebase.

Per HIGH/MEDIUM recommendation, dispatch 1 Agent (background). Catches "we already have this" false positives.

See `references/phase5-audit-template.md` for audit agent template, coverage levels (ALREADY EXISTS / PARTIAL / MISSING), and `--quick` behavior.

**Gate**: All audit agents completed (or timed out at 5min). >=75% returned. Audit files in `/tmp/`.

### Phase 6: REPORT

**Goal**: Produce final reality-grounded report with audit-verified recommendations.

Read audit findings. Adjust: ALREADY EXISTS -> "Already Covered"; PARTIAL -> focus on gaps; MISSING -> keep. Overwrite `research-[REPO_NAME]-comparison.md` with final report. Remove `/tmp/` files.

See `references/phase6-report-template.md` for workflow and template.

**Gate**: Final report saved. Contains comparison table, adjusted recommendations, verdict. No "DRAFT" watermark. All recommendations reality-checked (or marked unaudited if --quick).

### Phase 7: IMPLEMENT (Optional -- skipped with `--analyze-only`)

**Goal**: Rebuild HIGH-value recommendations in our architecture.

Default: run Phase 7. `--analyze-only`: deliver Phase 6 report.

**Step 1: Parse report**

| Priority | Action |
|----------|--------|
| **HIGH** + MISSING/PARTIAL | Dispatch implementation agent (Step 2) |
| **MEDIUM** | Add to "Future Consideration" -- no auto-implement |
| **LOW** | Note in log -- no action |

No HIGH recommendations => log and skip to gate.

**Step 2: Dispatch implementation agents**

Per HIGH recommendation, load `references/phase7-implement-template.md` and dispatch 1 Agent with:

1. Recommendation details
2. External repo's approach (reference only, not to copy -- per PHILOSOPHY.md "External Components Are Research Inputs, Not Imports")
3. PHILOSOPHY.md constraints: rebuild in our architecture, check existing components first ("One Domain, One Component"), progressive disclosure, deterministic execution
4. Quality gates: `ruff check . --config pyproject.toml`, `ruff format --check . --config pyproject.toml`, `python3 scripts/validate-references.py`, INDEX registration
5. Branch discipline: feature branch per implementation

Parallel when independent, sequential when dependent.

**Step 3: Collect results**

Per agent: what was built, quality gates passed, deferred items with reasons.

**Step 4: Append to `docs/CITATIONS.md`**

Under `## Repos` section, following existing format:

```markdown
### RepoName
https://github.com/org/repo

Description of what the repo is and why it was studied.

**Patterns adopted:**
- [Pattern name] ([implementation location]). Brief description.

**Patterns noted but not adopted:**
- [Pattern name]. Brief reason.
```

Mapping:
- HIGH + implemented -> "Patterns adopted" (include files from Step 3)
- HIGH + deferred -> "Patterns noted but not adopted" (state reason)
- MEDIUM -> "Patterns noted but not adopted"
- LOW -> "Patterns noted but not adopted"

Every recommendation must appear in exactly one section.

**Step 5: Write implementation log**

Append `## Implementation Results` to `research-[REPO_NAME]-comparison.md`:

```markdown
## Implementation Results

### HIGH Recommendations -- Implemented
| Recommendation | Status | Branch | Files Changed | Quality Gates |
|---------------|--------|--------|---------------|---------------|
| ... | DONE / DEFERRED | feat/... | ... | ruff PASS, validate-references PASS |

### MEDIUM Recommendations -- Future Consideration
- [recommendation]: [why worth considering later]

### LOW Recommendations -- Noted
- [recommendation]: [brief note]
```

**Gate**: All HIGH recommendations implemented or explicitly deferred with documented reason. Each follows our architecture. Citation appended to `docs/CITATIONS.md`. Implementation log appended.

---

## Error Handling

See `references/error-handling.md` for clone failures, large repos (10k+ files), agent timeouts, no-gaps-found, and self-inventory failures.

---

## References

- `references/phase2-agent-template.md` -- Phase 2 DEEP-READ agent template
- `references/phase3-inventory-template.md` -- Phase 3 INVENTORY agent template
- `references/phase5-audit-template.md` -- Phase 5 AUDIT agent template
- `references/phase6-report-template.md` -- Phase 6 REPORT workflow and template
- `references/phase7-implement-template.md` -- Phase 7 IMPLEMENT agent dispatch template
- `references/error-handling.md` -- Pipeline error handling
