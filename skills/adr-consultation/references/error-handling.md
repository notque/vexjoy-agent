# ADR Consultation — Error Handling Reference

> **Scope**: Error conditions, detection commands, and recovery procedures for adr-consultation.
> Covers failures in discovery, dispatch, synthesis, and gate phases.
> **Version range**: Standard mode (3 agents), Complex mode (5 agents)

---

## Overview

ADR consultation failures fall into four categories: discovery failures (ADR not found or session
missing), dispatch failures (agents time out, write to wrong paths, or produce empty output),
synthesis failures (concern extraction incomplete or verdict misaggregated), and gate failures
(blocking concern rationalized or synthesis verdict contradicts concerns.md). Each has a detection
command and a concrete recovery.

---

## Phase 1 Errors: Discovery

### Error: ADR path unclear or not found

**Symptoms**: User invoked skill without specifying an ADR; `.adr-session.json` missing or stale.

**Detection**:
```bash
# Check for active session
cat .adr-session.json 2>/dev/null || echo "NO SESSION"

# List available ADRs
ls adr/*.md 2>/dev/null || echo "NO ADRs FOUND"

# Verify a user-provided path exists
ls {user-provided-path} 2>/dev/null || echo "FILE NOT FOUND"
```

**Recovery**: List available ADRs and ask the user to specify. Do not guess. A wrong ADR wastes
a full consultation cycle.

---

### Error: Consultation directory creation fails

**Symptoms**: `mkdir -p adr/{name}` exits non-zero; agents cannot write output files.

**Detection**:
```bash
# Check if adr/ parent exists
ls -d adr/ 2>/dev/null || echo "MISSING adr/ directory"

# Check write permissions
touch adr/.write-test 2>/dev/null && rm adr/.write-test || echo "NO WRITE PERMISSION"
```

**Recovery**: Create `adr/` if missing (`mkdir -p adr/`). If permissions are wrong, report
the issue — do not dispatch agents without a confirmed writable directory.

---

## Phase 2 Errors: Dispatch

### Error: Agent times out or fails to write file

**Symptoms**: Phase 2 completes but fewer than 3 agent files exist in `adr/{name}/`.

**Detection**:
```bash
# Count agent output files (standard: expect 3)
ls adr/{name}/reviewer-perspectives-*.md 2>/dev/null | wc -l

# Identify which agents succeeded and which are missing
for lens in contrarian user-advocate meta-process; do
  f="adr/{name}/reviewer-perspectives-$lens.md"
  if [ -f "$f" ]; then
    echo "OK:      $lens ($(wc -l < "$f") lines)"
  else
    echo "MISSING: $lens"
  fi
done
```

**Recovery**:
1. Report which agent(s) failed by name.
2. Re-run the failed agent individually with the same prompt from Phase 2.
3. Do not synthesize until all 3 files exist and are non-empty.
4. If re-run fails again, report to user — ask whether to proceed with partial consultation or abort.

---

### Error: Agent writes empty or near-empty file

**Symptoms**: Agent output file exists but contains < 10 lines or is missing the `## Verdict:` section.

**Detection**:
```bash
# Check line counts across all agent files
wc -l adr/{name}/reviewer-perspectives-*.md 2>/dev/null

# Verify each file has a Verdict section
for f in adr/{name}/reviewer-perspectives-*.md; do
  grep -q "## Verdict:" "$f" \
    && echo "OK:      $(basename $f)" \
    || echo "NO VERDICT: $(basename $f)"
done
```

**Recovery**: A file with < 10 lines or no `## Verdict:` indicates the agent hit a context limit
or failed mid-output. Re-run the affected agent. Do not synthesize from an incomplete file.

---

### Error: Agent wrote output to wrong path

**Symptoms**: No files appear in `adr/{name}/` but agent reports completion.

**Detection**:
```bash
# Search for recent reviewer output files regardless of where they landed
find . -name "reviewer-perspectives-*.md" -newer adr/ 2>/dev/null | sort

# Check if output landed in cwd instead of adr/{name}/
ls reviewer-perspectives-*.md 2>/dev/null
```

**Recovery**: Move misplaced files to `adr/{name}/` and verify the agent prompt contained the
explicit output path `adr/{name}/reviewer-perspectives-{lens}.md`.

---

## Phase 3 Errors: Synthesis

### Error: Concern in agent file not extracted to concerns.md

**Symptoms**: Synthesis verdict seems too optimistic; re-reading agent files reveals concerns
that never made it into concerns.md.

**Detection**:
```bash
# Extract all severity lines from agent files
grep -hi "severity\|blocking\|important\|minor" \
  adr/{name}/reviewer-perspectives-*.md 2>/dev/null

# Compare against what made it into concerns.md
grep "Severity:" adr/{name}/concerns.md 2>/dev/null
```

**Recovery**: Re-read each agent file systematically. For every concern mentioned, confirm it
appears in concerns.md with severity and resolution. Add any missing entries.

---

### Error: ADR body changed between dispatch and synthesis

**Symptoms**: Agent verdicts reference ADR content that no longer matches the current ADR file.

**Detection**:
```bash
# Compare timestamps — if ADR is newer than agent files, it changed post-dispatch
ls -lt adr/{name}.md adr/{name}/reviewer-perspectives-*.md 2>/dev/null | head -6
```

**Recovery**: Re-run the full consultation. Agent verdicts based on outdated ADR content are
invalid. Note in concerns.md why the prior consultation was invalidated.

---

### Error: All agents PROCEED but synthesizer detects a cross-cutting issue

**Symptoms**: Reading all three agent files together reveals an emergent concern that none
flagged individually because each assessed a different slice.

**Detection**: This is a judgment call — no automatic detection command. The signal is noticing
while reading all three files that Agent A's "acceptable tradeoff" creates Agent B's unstated risk.

```bash
# Surface candidate cross-cutting terms across all agent files
grep -hi "tradeoff\|trade.off\|acceptable\|assume\|assuming\|depends on\|relies on" \
  adr/{name}/reviewer-perspectives-*.md 2>/dev/null
```

**Recovery**: Document as an orchestrator-level concern in concerns.md:
```markdown
## Orchestrator Concern N: [Title]
- **Raised by**: synthesis orchestrator (cross-cutting)
- **Severity**: blocking | important | minor
- **Description**: [Why the combination of agent findings creates this concern]
- **Resolution**: UNRESOLVED
```
Factor this concern into the verdict. PROCEED from all three agents does not override
an orchestrator-level blocking concern.

---

## Phase 4 Errors: Gate

### Error: concerns.md has blocking severity but synthesis says PROCEED

**Symptoms**: Synthesis file says PROCEED but concerns.md contains unresolved blocking concerns.

**Detection**:
```bash
# Count blocking concerns
grep -c "Severity.*blocking\|severity.*blocking" adr/{name}/concerns.md 2>/dev/null

# Verify synthesis verdict
grep "## Verdict:" adr/{name}/synthesis.md 2>/dev/null
```

**Recovery**: Override the synthesis verdict to BLOCKED. To eventually reach PROCEED:
1. Address the blocking concern in the ADR text
2. Update concerns.md with `Resolution: RESOLVED: {description}`
3. Re-run consultation from Phase 2

Do not edit synthesis.md to say PROCEED while concerns.md still has unresolved blocking
entries — that is the rationalization anti-pattern and defeats the gate.

---

### Error: synthesis.md references concern not in concerns.md

**Symptoms**: Synthesis mentions a concern that does not appear as a `## Concern N:` entry
in concerns.md.

**Detection**:
```bash
# List concern headings in concerns.md
grep "^## Concern" adr/{name}/concerns.md 2>/dev/null

# Check synthesis for concern language not backed by concerns.md
grep -i "concern\|blocking\|issue" adr/{name}/synthesis.md 2>/dev/null
```

**Recovery**: Concerns must be extracted from agent files into concerns.md first; synthesis
must only reference what is already there. If synthesis.md mentions something not in
concerns.md, add it to concerns.md with proper severity, then re-verify the verdict.

---

## Quick Reference: Error-to-Recovery Table

| Symptom | Phase | Detection Command | Recovery |
|---------|-------|-------------------|----------|
| No ADR path found | Phase 1 | `cat .adr-session.json` | List ADRs, ask user |
| Agent file missing after dispatch | Phase 2 | `ls adr/{name}/reviewer-*.md \| wc -l` | Re-run missing agent individually |
| Agent file < 10 lines or no Verdict | Phase 2 | `wc -l adr/{name}/reviewer-*.md` | Re-run affected agent |
| Agent output in wrong directory | Phase 2 | `find . -name "reviewer-perspectives-*.md" -newer adr/` | Move files; fix prompt path |
| Concern in agent file not in concerns.md | Phase 3 | `grep -hi "severity" adr/{name}/reviewer-*.md` | Re-extract from agent files |
| ADR changed after dispatch | Phase 3 | `ls -lt adr/{name}.md adr/{name}/reviewer-*.md` | Re-run full consultation |
| Blocking in concerns.md, PROCEED in synthesis | Phase 4 | `grep -c "Severity.*blocking" concerns.md` | Override to BLOCKED; address concern |
| Synthesis mentions concern not in concerns.md | Phase 4 | `grep "^## Concern" concerns.md` | Add to concerns.md; re-verify verdict |

---

## See Also

- `consultation-preferred-patterns.md` — Structural anti-patterns (sequential dispatch, context-only synthesis, rationalization)
- `consultation-patterns.md` — Correct dispatch, synthesis, and verdict aggregation patterns
