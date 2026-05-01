# Phase 5: AUDIT Agent Template

For each HIGH or MEDIUM recommendation, dispatch 1 Agent (in background). Audit is what separates superficial analysis from rigorous analysis — skipping it produces unverified recommendations that erode trust:

```
You are auditing whether recommendation "[recommendation]" is already
addressed in the vexjoy-agent repository.

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
