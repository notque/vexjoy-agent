# Error Catalog Reference

> **Scope**: Research coordination errors: delegation, structural, synthesis, output format. Not subagent-executor errors.
> **Version range**: All versions
> **Generated**: 2026-04-13

---

## Error-Fix Mappings

### Delegation Errors

| Symptom | Root Cause | Fix |
|---------|------------|-----|
| All subagents return similar content | No methodological differentiation | Re-assign with distinct angles |
| Off-topic content | Missing OUT-OF-SCOPE | Add explicit exclusions |
| Returns meta-analysis | Instruction said "research" not "find data" | Specify data/facts deliverable |
| Wildly different lengths | No word count spec | Add word count range |
| Cites paywalled sources with no data | No source guidance | Add source tier preference |
| Nothing useful | Scope too narrow | Widen or merge with adjacent topic |

### Structural Errors

| Symptom | Root Cause | Fix |
|---------|------------|-----|
| Covers everything, focuses nothing | Breadth-first treated as depth-first | Re-classify; one entity per subagent |
| Comparison impossible | Wrong query type | Re-run breadth-first with standardized format |
| Simple query → 1200-word essay | Over-deployed | 1 subagent, tight spec, 150-250 words |
| >20 subagents needed | Over-scoped | Merge topics, reduce scope |
| Wave 2 repeats Wave 1 | No Bayesian update | Reference gaps in Wave 2 scope |

### Synthesis Errors

| Symptom | Root Cause | Fix |
|---------|------------|-----|
| Copy-paste of subagent outputs | No synthesis | Identify cross-cutting patterns; reconcile conflicts |
| Unresolved conflicts | No reconciliation | State conflict, explain cause, recommend resolution |
| Gaps despite broad research | Didn't audit coverage | Audit against original query; deploy gap-fill subagent |
| Delegates final report | Hardcoded violation | Lead agent ALWAYS writes report |
| Contains citations | Output format violation | Remove all citations |

### Output Format Errors

| Symptom | Root Cause | Fix |
|---------|------------|-----|
| Report not saved | Skipped Write tool | Save to `research/{topic}/report.md` |
| Wrong location | Name not normalized | Lowercase, hyphen-separated |
| Missing completion header | Format not followed | Add `═══ RESEARCH COMPLETE ═══` header |
| Temp files remain | Cleanup skipped | Delete intermediate files |

---

## Detailed Entries

### Synthesis Delegation (Critical)

**Detection**:
```bash
grep -ri "subagent.*final\|delegate.*synthesis" research/*/plan.md
```

A subagent sees only its own stream — cannot reconcile cross-stream conflicts.

**Fix**: Lead agent reads all outputs directly, writes final report.

---

### Citation Inclusion

**Detection**:
```bash
grep -rn "^## References\|^## Sources" research/*/report.md
grep -rn "\[[0-9]\+\]\|([A-Z][a-z]*,\s*20[0-9][0-9])" research/*/report.md
```

Citation agent handles separately. Inline attribution when needed: "According to Synergy Research Q4 2024 data, AWS holds 31% market share."

---

### Scope Creep in Subagent Output

**Detection**:
```bash
grep -i "consumer\|gaming\|RTX\|GeForce" research/*/subagent-*.md | head -20
wc -w research/*/subagent-*.md | sort -rn | head -10
```

**Fix**: (1) Filter off-topic content during synthesis. (2) Move OUT-OF-SCOPE to top of future instructions.

---

### Diminishing Returns Not Detected

**Detection**:
```bash
ls -1 research/*/subagent-*.md 2>/dev/null | wc -l
```

**Stop signals**: Same sources repeated, refinements not new categories, word counts dropping, >7 subagents for medium query.

**Fix**: After each wave, check: "Did Wave N add findings not in Wave N-1?" If marginal count < 2, stop.

---

## Detection Commands Reference

```bash
# Critical violations
grep -rn "^## References\|^## Sources" research/*/report.md
grep -ri "subagent.*final.*report\|delegate.*synthesis" research/*/plan.md

# Scope issues
grep -rL "Do NOT\|OUT OF SCOPE" research/*/instructions/ 2>/dev/null

# Output format
grep -rL "RESEARCH COMPLETE" research/*/report.md 2>/dev/null

# Subagent count
ls -1 research/*/subagent-*.md 2>/dev/null | wc -l

# Diminishing returns
wc -w research/*/subagent-*.md 2>/dev/null | sort -n
```

---

## See Also

- `delegation-patterns.md` — Prevention via instruction quality
- `query-classification.md` — Correct type prevents structural errors
