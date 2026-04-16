# ADR Consultation — Anti-Patterns

> **Scope**: Common failures in ADR consultation orchestration and synthesis. Covers what goes wrong
> and how to detect and fix it. Does NOT cover ADR authoring style or implementation quality.
> **Version range**: Standard mode (3 agents), Complex mode (5 agents)
> **Generated**: 2026-04-15

---

## Overview

ADR consultation fails in predictable ways: agents dispatched sequentially, synthesis from
ephemeral context instead of files, blocking concerns rationalized away, and partial consultation
masquerading as full review. Each failure mode has a detection command and a concrete fix.

---

## Anti-Pattern Catalog

### ❌ Sequential Agent Dispatch

**Detection**:
```bash
# Look for single-agent output files — if contrarian exists but others don't yet,
# dispatch was sequential
ls adr/{name}/reviewer-perspectives-contrarian.md 2>/dev/null
ls adr/{name}/reviewer-perspectives-user-advocate.md 2>/dev/null
ls adr/{name}/reviewer-perspectives-meta-process.md 2>/dev/null
# All three should exist simultaneously after dispatch completes
```

**What it looks like**:
```markdown
[Message 1]: Dispatching contrarian reviewer now...
[Message 2]: Contrarian complete. Now dispatching user-advocate...
[Message 3]: User-advocate complete. Now dispatching meta-process...
```

**Why wrong**: Triples wall-clock time with no benefit. Each agent is supposed to assess
independently; sequential dispatch means agents 2 and 3 may see context contaminated by
agent 1's findings, undermining independence. The value is *simultaneous* independent judgment.

**Fix**: All three Task calls in a single response message. No exceptions.

---

### ❌ Context-Only Synthesis

**Detection**:
```bash
# If synthesis.md exists but agent files don't, synthesis came from context only
ls adr/{name}/synthesis.md 2>/dev/null
ls adr/{name}/reviewer-perspectives-*.md 2>/dev/null | wc -l
# Healthy: synthesis.md + 3 agent files. Unhealthy: synthesis.md + 0 agent files.
```

**What it looks like**:
```markdown
<!-- synthesis.md created without the orchestrator having read agent files from disk -->
# Consultation Synthesis: my-adr
## Verdict: PROCEED
[Based on what the agents reported in this session...]
```

**Why wrong**: Task return context disappears when context is cleared or a new session starts.
Synthesis built from context cannot be re-read, audited, or resumed. If the session drops
mid-consultation, the entire analysis is lost. File-based artifacts are the permanent record.

**Fix**: After all agents complete, explicitly read each `adr/{name}/reviewer-perspectives-*.md`
file before synthesizing — even if Task return context is available.

---

### ❌ Rationalizing Blocking Concerns

**Detection**:
```bash
# Check if any concerns.md has blocking severity while synthesis says PROCEED
for dir in adr/*/; do
  name=$(basename "$dir")
  if grep -q "Severity.*blocking" "$dir/concerns.md" 2>/dev/null; then
    if grep -q "## Verdict: PROCEED" "$dir/synthesis.md" 2>/dev/null; then
      echo "RATIONALIZATION DETECTED: $name"
    fi
  fi
done
```

**What it looks like**:
```markdown
## Verdict: PROCEED
Although the contrarian reviewer raised a blocking concern about the data migration
risk, this seems theoretical given our team's experience with similar migrations.
We'll keep an eye on it during implementation.
```

**Why wrong**: "Theoretical risk is still risk." The gate exists to surface blocking concerns
before implementation. Post-implementation discovery of the same issue costs dramatically
more: the feature is already built, tests written, and the fix requires architectural surgery.
The word "theoretical" is a rationalization signal — stop and address the concern.

**Fix**: Any `severity: blocking` means the verdict is BLOCKED. To reach PROCEED, address
the concern in the ADR itself and re-run consultation. Do not argue around it in synthesis.

---

### ❌ Partial Consultation

**Detection**:
```bash
# Standard mode: expect exactly 3 reviewer files
count=$(ls adr/{name}/reviewer-perspectives-*.md 2>/dev/null | wc -l)
if [ "$count" -lt 3 ]; then
  echo "PARTIAL CONSULTATION: only $count/3 reviewers present"
fi
```

**What it looks like**: Dispatching only 1 or 2 agents because the ADR "seems simple" or
"is mostly a config change" or "we've done this type of decision before."

**Why wrong**: Partial consultation gives false confidence. An agent that genuinely finds no
concerns returns PROCEED in seconds — that's a fast, cheap confirmation worth having. Removing
an agent removes an entire perspective class. The contrarian lens catches problems the user
advocate misses; the meta-process lens catches coupling issues both miss. Each lens exists
because the others have blind spots.

**Fix**: Dispatch all three agents. Let agents self-report "no concerns" when clean — that is
a valid, valuable outcome that costs almost nothing.

---

### ❌ Silent Overwrite of Prior Consultation

**Detection**:
```bash
# Check for existing files before dispatch
ls -lt adr/{name}/ 2>/dev/null
# If files exist with recent timestamps, this is prior work — confirm before overwriting
```

**What it looks like**: Re-running consultation on an ADR that already has consultation
artifacts without acknowledging or showing the existing results.

**Why wrong**: Silently overwriting prior consultation destroys the audit trail. The prior
consultation may have reached a BLOCKED verdict that was intentionally deferred, or may
contain concerns that were addressed in the ADR revision — losing this history means the
same ground is re-covered without context.

**Fix**: When `ls adr/{name}/` shows existing files, report them with timestamps and ask
whether to overwrite (re-run) or use existing results.

---

### ❌ Skipping Pre-Dispatch Gate Validation

**Detection**:
```bash
# Verify all pre-dispatch requirements before sending Task calls
ls adr/{name}/ 2>/dev/null || echo "MISSING DIRECTORY"
cat .adr-session.json 2>/dev/null || echo "NO SESSION"
wc -l < adr/{name}.md 2>/dev/null || echo "ADR NOT READ"
```

**What it looks like**: Dispatching agents before confirming the ADR has been read, the
consultation directory exists, and the ADR name has been confirmed.

**Why wrong**: Agents need a valid directory to write output files. An agent that cannot
write `adr/{name}/reviewer-perspectives-contrarian.md` because `adr/{name}/` doesn't exist
will either fail silently or write to the wrong location. The synthesis then has no files to read.

**Fix**: Enforce the Phase 1 gate explicitly: confirm ADR content read, `mkdir -p adr/{name}`
complete, ADR name confirmed. Only then dispatch.

---

### ❌ Treating NEEDS_CHANGES as Soft PROCEED

**Detection**:
```bash
# Count NEEDS_CHANGES vs PROCEED vs BLOCK in agent files
grep -h "## Verdict:" adr/{name}/reviewer-perspectives-*.md 2>/dev/null | sort | uniq -c
```

**What it looks like**:
```markdown
## Agent Verdicts
| Agent | Verdict |
|-------|---------|
| contrarian | NEEDS_CHANGES |
| user-advocate | NEEDS_CHANGES |
| meta-process | PROCEED |

## Verdict: PROCEED
Two reviewers had minor concerns but overall the approach is sound.
```

**Why wrong**: Two NEEDS_CHANGES verdicts mean two independent reviewers identified specific
things that must change. Aggregating this to PROCEED discards both sets of concerns. The
synthesis verdict table is not a voting system — it is a concern aggregator. Multiple
NEEDS_CHANGES is a signal that the ADR needs revision before proceeding.

**Fix**: When multiple agents return NEEDS_CHANGES, treat as BLOCKED or PROCEED-with-conditions
only after all raised concerns are extracted, classified, and either resolved or explicitly
accepted as known limitations.

---

## Error-Fix Mappings

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| Agent completes but no file in `adr/{name}/` | Path in agent prompt had typo or `adr/{name}/` not pre-created | Check prompt path; run `mkdir -p adr/{name}`; re-run failed agent |
| `synthesis.md` says PROCEED, `concerns.md` has `blocking` | Rationalization — concerns read but not enforced | Override synthesis to BLOCKED; address concern in ADR; re-run |
| Only 1-2 agent files present after dispatch | Sequential dispatch or agent failure | Check whether dispatch was single-message; re-run missing agents |
| Consultation re-run silently overwrites prior results | Pre-dispatch check skipped | Always `ls adr/{name}/` before dispatching; report existing files |
| Synthesis references concerns not in concerns.md | Synthesizer added concerns during synthesis instead of extracting from agent files | Re-extract from agent files systematically; update concerns.md |

---

## Detection Commands Reference

```bash
# Check for sequential dispatch (files should appear simultaneously)
ls -lt adr/{name}/reviewer-perspectives-*.md 2>/dev/null

# Verify complete consultation (expect 3 files in standard mode)
ls adr/{name}/reviewer-perspectives-*.md 2>/dev/null | wc -l

# Detect rationalized blocking concerns
grep -l "Severity.*blocking" adr/*/concerns.md 2>/dev/null | while read f; do
  dir=$(dirname "$f")
  grep -l "Verdict: PROCEED" "$dir/synthesis.md" 2>/dev/null && echo "CHECK: $dir"
done

# Count verdict types across all agent files in a consultation
grep -h "## Verdict:" adr/{name}/reviewer-perspectives-*.md 2>/dev/null | sort | uniq -c

# Verify permanent artifacts after cleanup
ls adr/{name}/synthesis.md adr/{name}/concerns.md 2>/dev/null
```

---

## See Also

- `consultation-patterns.md` — Correct patterns for dispatch, synthesis, and verdict aggregation
- `skills/parallel-code-review/SKILL.md` — Fan-out/fan-in pattern this skill adapts
