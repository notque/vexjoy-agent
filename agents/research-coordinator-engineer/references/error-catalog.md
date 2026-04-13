# Error Catalog Reference

> **Scope**: Common research coordination errors: subagent failures, synthesis failures, scope failures, and output format violations. Does NOT cover subagent-executor errors — those are handled by research-subagent-executor.
> **Version range**: All versions of research-coordinator-engineer
> **Generated**: 2026-04-13 — add new error patterns when observed in production sessions

---

## Overview

Research coordination errors fall into four categories: delegation errors (bad instructions), structural errors (wrong query strategy), synthesis errors (lead agent failures), and output errors (format violations). Most root causes trace to skipping query classification or vague subagent instructions. Detection commands scan research output files for symptom patterns.

---

## Error-Fix Mappings

### Delegation Errors

| Error Symptom | Root Cause | Fix |
|---------------|------------|-----|
| All subagents return similar content | Angle overlap — no methodological differentiation | Re-assign with distinct angles; verify no two subagents have same scope |
| Subagent returns off-topic content | Missing OUT-OF-SCOPE clause | Add explicit exclusions to every instruction |
| Subagent returns meta-analysis | Instruction said "research" not "find data" | Specify deliverable as data/facts, not analysis |
| Subagents return wildly different lengths | No word count specification | Add explicit word count range to every instruction |
| Subagent cites paywalled sources with no data | No source quality guidance | Add source tier preference: primary > secondary > aggregator |
| One subagent returns nothing useful | Scope too narrow or impossible to research | Widen scope or merge with adjacent subagent's topic |

### Structural Errors

| Error Symptom | Root Cause | Fix |
|---------------|------------|-----|
| Research covers everything, focuses on nothing | Breadth-first query treated as depth-first | Re-classify; assign one entity per subagent |
| Comparison not possible from findings | Comparison query treated as depth-first | Re-run with breadth-first; standardize deliverable format |
| Simple factual query produced 1200-word essay | Straightforward query over-deployed | Use 1 subagent, tight deliverable spec, 150-250 words |
| >20 subagents needed | Over-scoped query | Restructure: merge adjacent topics, reduce scope to core questions |
| Wave 2 repeats Wave 1 findings | No Bayesian update applied | Reference Wave 1 gaps explicitly; scope Wave 2 to gaps only |

### Synthesis Errors

| Error Symptom | Root Cause | Fix |
|---------------|------------|-----|
| Final report is copy-paste of subagent outputs | Lead agent didn't synthesize — just concatenated | Identify cross-cutting patterns; reconcile conflicts; produce integrated analysis |
| Report contains unresolved conflicts | Lead agent didn't reconcile contradictions | State conflict explicitly, explain likely cause, recommend resolution |
| Report has gaps despite broad research | Synthesis didn't identify missing coverage | Audit coverage against original query; deploy targeted gap-fill subagent |
| Final report delegates to subagent | Hardcoded behavior violation | Lead agent ALWAYS writes final report — this is non-negotiable |
| Report contains citations/references section | Citation-free output violation | Remove all citations; citation agent handles separately |

### Output Format Errors

| Error Symptom | Root Cause | Fix |
|---------------|------------|-----|
| Report not saved to file | Skipped Write tool | Always save to `research/{topic}/report.md` before declaring complete |
| Report saved in wrong location | Topic name not normalized | Use lowercase, hyphen-separated: `research/ai-compute-trends/report.md` |
| Report missing completion header | Output format not followed | Add the `═══ RESEARCH COMPLETE ═══` header with all metadata fields |
| Temporary subagent files not cleaned | Cleanup step skipped | Delete intermediate files; keep only final report |

---

## Detailed Error Entries

### Synthesis Delegation (Critical)

**Symptom**: Lead agent writes "Subagent: compile findings from the above three reports into a final synthesis."

**Detection**:
```bash
# Find research plans that delegate synthesis
grep -ri "subagent.*final\|delegate.*synthesis\|compile.*report" research/*/plan.md
grep -ri "write.*final.*report" research/*/instructions/ | grep -v "lead agent"
```

**Why wrong**: Synthesis delegation violates the hardcoded lead-agent-synthesizes rule. When subagents synthesize, the coordinator loses the cross-stream perspective needed to reconcile conflicts. A subagent sees only its own research stream — it cannot identify what the other subagents found or whether findings conflict.

**Fix**:
```markdown
# WRONG
"Subagent 4: Read outputs from subagents 1-3 and write final report"

# CORRECT
# Lead agent reads all subagent outputs directly:
# Read research/{topic}/subagent-1.md
# Read research/{topic}/subagent-2.md
# Read research/{topic}/subagent-3.md
# Then writes final report as the coordinator
```

---

### Citation Inclusion (Output Violation)

**Symptom**: Final report contains `## References`, `[1] Source Name...`, or inline `(Smith, 2024)` citations.

**Detection**:
```bash
# Find reports with citation sections
grep -rn "^## References\|^## Sources\|^## Bibliography" research/*/report.md
# Find inline citations
grep -rn "\[[0-9]\+\]\|([A-Z][a-z]*,\s*20[0-9][0-9])" research/*/report.md
```

**Why wrong**: The citation agent handles citations separately as a downstream step. Including citations in the research report creates duplication, formatting conflicts, and incorrect attribution when the citation agent reformats. Citation-free output is a hardcoded behavior — the coordinator must strip citations from its synthesis.

**Fix**: Remove all citation markers from the final report. If a specific statistic needs attribution for credibility, embed it inline: "According to Synergy Research Q4 2024 data, AWS holds 31% market share" — no footnote, no reference section.

---

### Scope Creep in Subagent Output

**Symptom**: Subagent returns content that covers topics explicitly excluded in its instruction.

**Detection**:
```bash
# After research, check if excluded topics appear in subagent outputs
# Example: instruction said "Do NOT cover consumer GPU" — check if subagent covered it
grep -i "consumer\|gaming\|RTX\|GeForce" research/*/subagent-*.md | head -20
# General: check word count — scope creep usually inflates output
wc -w research/*/subagent-*.md | sort -rn | head -10
```

**Why it happens**: The subagent lacked explicit OUT-OF-SCOPE guidance, or the exclusion was buried at the end of a long instruction. Subagents default to covering adjacent topics when boundaries are unclear.

**Fix**: Two actions required:
1. During synthesis — filter out off-topic content from the subagent's output before integrating
2. For future research — move OUT-OF-SCOPE clause to the TOP of the instruction, before the positive scope statement

```markdown
# Structure that prevents scope creep:
Do NOT cover: consumer GPU market, gaming hardware, edge inference chips.
Focus ONLY ON: data center AI accelerators (H100, TPU v5, Trainium2 class).
[positive scope follows after exclusions are clearly stated]
```

---

### Diminishing Returns Not Detected

**Symptom**: Coordinator deploys Wave 3, 4, 5 subagents when Wave 2 already answered the query; report quality does not improve.

**Detection**:
```bash
# Count subagent output files — more than 7 for a medium query is a signal
ls -1 research/*/subagent-*.md 2>/dev/null | wc -l
# Check if late-wave subagents repeat Wave 1 findings
diff research/*/subagent-1.md research/*/subagent-5.md 2>/dev/null | wc -l
```

**Why it happens**: No diminishing-returns check between waves. The coordinator keeps deploying because "more data = better report" — which is false when the additional subagents find the same sources.

**Fix**: After each wave, evaluate: "Did Wave N add findings not present in Wave N-1?" If the marginal finding count drops below 2, stop. Synthesize from current data.

Signals that diminishing returns have been reached:
- New subagent outputs cite the same sources as previous subagents
- New findings are refinements of existing data (not new categories)
- Subagent word counts drop as it struggles to find new material
- Over-engineering prevention rule triggers: "Only research what is directly requested"

---

## Detection Commands Reference

```bash
# Critical violations — check after every session
grep -rn "^## References\|^## Sources\|^## Bibliography" research/*/report.md
grep -ri "subagent.*final.*report\|delegate.*synthesis" research/*/plan.md

# Scope issues
grep -rL "Do NOT\|OUT OF SCOPE\|Exclude\|Not in scope" research/*/instructions/ 2>/dev/null

# Output format violations
grep -rL "RESEARCH COMPLETE" research/*/report.md 2>/dev/null
find research/ -name "report.md" | xargs grep -L "research/{" 2>/dev/null

# Subagent count check
ls -1 research/*/subagent-*.md 2>/dev/null | wc -l  # alert if > 20

# Diminishing returns signal
wc -w research/*/subagent-*.md 2>/dev/null | sort -n  # dropping word count = exhausted topic
```

---

## See Also

- `delegation-patterns.md` — Prevention: how to write instructions that avoid these errors
- `query-classification.md` — Prevention: correct query type prevents most structural errors
