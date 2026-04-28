# ADR Consultation Patterns Guide

> **Scope**: Correct patterns for ADR consultation orchestration and synthesis. Covers dispatch, artifact management, verdict aggregation, and gate enforcement. Does NOT cover ADR authoring style or implementation quality.
> **Version range**: Standard mode (3 agents), Complex mode (5 agents)
> **Generated**: 2026-04-15

---

## Overview

ADR consultation succeeds when agents are dispatched simultaneously, artifacts are file-based, blocking concerns halt progress, and all perspectives are represented. The patterns below define the correct approach for each phase, with detection commands to find violations.

---

## Pattern Catalog

### Dispatch All Agents Simultaneously

Send all three Task calls in a single response message. Every agent assesses independently — simultaneous dispatch preserves independence and runs in one-third the wall-clock time.

```markdown
[Single message with all three Task calls]:
- Contrarian reviewer → writes adr/{name}/reviewer-perspectives-contrarian.md
- User advocate → writes adr/{name}/reviewer-perspectives-user-advocate.md
- Meta-process reviewer → writes adr/{name}/reviewer-perspectives-meta-process.md
```

**Why this matters**: Sequential dispatch triples wall-clock time and risks context contamination. If agents 2 and 3 see agent 1's findings, they lose independence — the value is simultaneous independent judgment from different perspectives.

**Detection**:
```bash
# All three files should exist simultaneously after dispatch completes
ls adr/{name}/reviewer-perspectives-contrarian.md 2>/dev/null
ls adr/{name}/reviewer-perspectives-user-advocate.md 2>/dev/null
ls adr/{name}/reviewer-perspectives-meta-process.md 2>/dev/null
```

---

### Synthesize From Files, Not Context

After all agents complete, explicitly read each `adr/{name}/reviewer-perspectives-*.md` file before writing synthesis — even if Task return context is available. File-based synthesis is auditable, resumable, and survives session drops.

Healthy state: `synthesis.md` exists alongside 3 agent files. Unhealthy state: `synthesis.md` exists with 0 agent files — synthesis came from ephemeral context only.

**Why this matters**: Task return context disappears when context is cleared or a new session starts. Synthesis built from context cannot be re-read, audited, or resumed. If the session drops mid-consultation, the entire analysis is lost.

**Detection**:
```bash
# If synthesis.md exists but agent files don't, synthesis came from context only
ls adr/{name}/synthesis.md 2>/dev/null
ls adr/{name}/reviewer-perspectives-*.md 2>/dev/null | wc -l
# Healthy: synthesis.md + 3 agent files. Unhealthy: synthesis.md + 0 agent files.
```

---

### Enforce Blocking Concerns as Hard Gates

Any `severity: blocking` concern means the verdict is BLOCKED. To reach PROCEED, address the concern in the ADR itself and re-run consultation. Never argue around a blocking concern in synthesis.

```markdown
## Verdict: BLOCKED
The contrarian reviewer identified a blocking data migration risk.
Resolution required before proceeding: [specific action needed].
```

**Why this matters**: Post-implementation discovery of a blocking issue costs dramatically more than pre-implementation: the feature is already built, tests written, and the fix requires architectural surgery. The word "theoretical" applied to a blocking concern is a rationalization signal.

**Detection**:
```bash
# Find blocking concerns that were rationalized to PROCEED
for dir in adr/*/; do
  name=$(basename "$dir")
  if grep -q "Severity.*blocking" "$dir/concerns.md" 2>/dev/null; then
    if grep -q "## Verdict: PROCEED" "$dir/synthesis.md" 2>/dev/null; then
      echo "RATIONALIZATION DETECTED: $name"
    fi
  fi
done
```

---

### Dispatch All Required Reviewers

Always dispatch all three agents in standard mode (contrarian, user-advocate, meta-process). An agent that finds no concerns returns PROCEED in seconds — that fast, cheap confirmation is worth having. Never skip an agent because the ADR "seems simple."

**Why this matters**: Each agent covers a different perspective class. The contrarian catches problems the user advocate misses; the meta-process lens catches coupling issues both miss. Removing an agent removes an entire class of analysis. Partial consultation gives false confidence.

**Detection**:
```bash
# Standard mode: expect exactly 3 reviewer files
count=$(ls adr/{name}/reviewer-perspectives-*.md 2>/dev/null | wc -l)
if [ "$count" -lt 3 ]; then
  echo "PARTIAL CONSULTATION: only $count/3 reviewers present"
fi
```

---

### Check for Existing Artifacts Before Dispatch

When `ls adr/{name}/` shows existing files, report them with timestamps and ask whether to overwrite (re-run) or use existing results. Never silently overwrite prior consultation.

**Why this matters**: Prior consultation may have reached a BLOCKED verdict that was intentionally deferred, or may contain concerns that were addressed in the ADR revision. Silently overwriting destroys the audit trail and forces re-covering the same ground without context.

**Detection**:
```bash
# Check for existing files before dispatch
ls -lt adr/{name}/ 2>/dev/null
# If files exist with recent timestamps, this is prior work — confirm before overwriting
```

---

### Validate Pre-Dispatch Gates Before Sending Agents

Before dispatching agents, confirm three prerequisites: (1) the ADR has been read, (2) the consultation directory exists (`mkdir -p adr/{name}`), and (3) the ADR name has been confirmed with the user.

**Why this matters**: Agents need a valid directory to write output files. An agent that cannot write to `adr/{name}/` because the directory does not exist will either fail silently or write to the wrong location. The synthesis then has no files to read.

**Detection**:
```bash
ls adr/{name}/ 2>/dev/null || echo "MISSING DIRECTORY"
cat .adr-session.json 2>/dev/null || echo "NO SESSION"
wc -l < adr/{name}.md 2>/dev/null || echo "ADR NOT READ"
```

---

### Treat NEEDS_CHANGES as Requiring Resolution

When multiple agents return NEEDS_CHANGES, extract all raised concerns, classify them, and either resolve them or explicitly accept them as known limitations. Multiple NEEDS_CHANGES is not a soft PROCEED — it means two independent reviewers identified specific things that must change.

```markdown
## Agent Verdicts
| Agent | Verdict |
|-------|---------|
| contrarian | NEEDS_CHANGES |
| user-advocate | NEEDS_CHANGES |
| meta-process | PROCEED |

## Verdict: PROCEED-with-conditions
All raised concerns listed below must be resolved or accepted:
1. [Concern from contrarian]: [resolution or acceptance rationale]
2. [Concern from user-advocate]: [resolution or acceptance rationale]
```

**Why this matters**: The synthesis verdict table is a concern aggregator, not a voting system. Aggregating two NEEDS_CHANGES to PROCEED discards both sets of concerns. Each NEEDS_CHANGES verdict represents specific, actionable feedback that was independently identified.

**Detection**:
```bash
# Count verdict types across all agent files in a consultation
grep -h "## Verdict:" adr/{name}/reviewer-perspectives-*.md 2>/dev/null | sort | uniq -c
```

---

## Error-Fix Mappings

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| Agent completes but no file in `adr/{name}/` | Path in agent prompt had typo or `adr/{name}/` not pre-created | Check prompt path; run `mkdir -p adr/{name}`; re-run failed agent |
| `synthesis.md` says PROCEED, `concerns.md` has `blocking` | Concerns read but not enforced | Override synthesis to BLOCKED; address concern in ADR; re-run |
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
