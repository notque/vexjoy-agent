# Phase 6: REPORT Template

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
# Competitive Analysis: [REPO_NAME] vs vexjoy-agent

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
