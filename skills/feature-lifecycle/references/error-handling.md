# Error Handling Reference

> **Scope**: Recovery patterns for feature-state.py CLI failures, phase transition errors, artifact issues, and agent dispatch failures within the feature lifecycle skill.
> **Version range**: all versions
> **Generated**: 2026-04-17

---

## Overview

The feature lifecycle skill uses `feature-state.py` as the single source of truth for phase tracking. Most errors fall into four categories: phase mismatches (requesting a phase the state machine isn't ready for), missing artifacts (previous phase didn't complete), agent dispatch failures (task agents returning errors), and gate failures (quality criteria not met). Each has a distinct recovery path — routing to the wrong path wastes entire waves of work.

---

## Pattern Table

| Situation | Correct Recovery | Wrong Recovery |
|-----------|-----------------|----------------|
| Phase mismatch | Report current phase, suggest correct next | Silently advance state |
| Missing artifact | Route back to producing phase | Proceed with empty artifact |
| Agent dispatch fails x3 | Stop, report to user | Retry indefinitely |
| Gate failure | Report exactly what failed, stop | Approve and advance |
| Tier 3 architectural deviation | Stop, present options | Auto-apply and continue |

---

## Correct Patterns

### Always Check State Before Acting

Check the feature state machine before dispatching any work in a phase.

```bash
# Verify phase is what you expect before loading anything
python3 ~/.claude/scripts/feature-state.py status my-feature
```

**Why**: The user may have partially completed a prior run, abandoned a phase, or the state file may reflect a different feature than the session context. Acting on stale assumptions causes cascading plan-vs-reality drift across waves.

---

### Record Gate Failures Before Stopping

When a gate fails, record the failure before stopping so retries start with context.

```bash
# Record the gate failure
python3 ~/.claude/scripts/feature-state.py gate my-feature validate.test-failure

# Document what failed
python3 ~/.claude/scripts/feature-state.py retro-record my-feature gate-failure \
  "validate: 3 tests failed in auth module" --confidence high
```

**Why**: Gate failures without records force re-diagnosis on retry. The retro system surfaces these as patterns so the plan phase can allocate more time to high-failure areas.

---

### Tier Classification Before Acting on Deviations

Classify every deviation before choosing a recovery path.

```bash
# After classifying as Tier 3 — stop and present to user
python3 ~/.claude/scripts/feature-state.py gate my-feature implement.architectural-deviation
```

```
Tier 1 (auto-fix):  bug, import error, type error → apply fix, record in retro, continue
Tier 2 (blocking):  missing dep, config issue → attempt auto-fix, record, escalate if stuck
Tier 3 (arch):      schema change, API redesign, scope expansion → STOP, present to user
```

**Why**: Tier 3 deviations represent scope changes the plan didn't authorize. Auto-applying them hides architectural decisions in implementation output where they can't be reviewed.

---

## Pattern Catalog

### Check Feature State Before Every Action

**Detection**:
```bash
# Look for advance calls without a preceding status check in the same block
grep -rn 'feature-state.py advance' skills/feature-lifecycle/
rg 'feature-state\.py (checkpoint|advance)' skills/
```

**Signal**:
```bash
# Missing: python3 ~/.claude/scripts/feature-state.py status my-feature
python3 ~/.claude/scripts/feature-state.py advance my-feature
```

**Why this matters**: Advancing without reading state can skip a phase or double-advance when a prior partial run already moved the state forward. The state file is authoritative; skipping the read assumes it matches session context.

**Preferred action**:
```bash
python3 ~/.claude/scripts/feature-state.py status my-feature
# Only if output confirms phase is ready:
python3 ~/.claude/scripts/feature-state.py advance my-feature
```

---

### Stop and Report After Three Agent Failures

**Detection**:
```bash
grep -rn 'Attempt [4-9]\|Attempt [0-9][0-9]' .feature/state/implement/
rg 'retry.*attempt|attempt.*[4-9]' .feature/ --ignore-case
```

**Signal**:
```
Attempt 1: Agent dispatch failed (no output)
Attempt 2: Agent dispatch failed (timeout)
Attempt 3: Agent dispatch failed (malformed response)
Attempt 4: Retrying with more context...  ← wrong
```

**Why this matters**: Three consecutive failures signal a structural problem: wrong agent type, missing prerequisite context, or a malformed task spec. More retries don't fix structural problems — they burn budget while delaying root-cause diagnosis.

**Preferred action**: After three failures, stop and report:
```
Task [name] failed 3 times. Root cause candidates:
- Agent type mismatch (assigned: X, task domain: Y)
- Missing prerequisite context (wave N depended on wave N-1 artifact)
- Task spec too ambiguous (file list or operations underspecified)

Blocked. Requires user input to continue.
```

---

### Block Advancement on Gate Failure

**Detection**:
```bash
grep -rn 'gate.*fail\|BLOCKED.*proceed\|proceeding.*fail' .feature/state/ --ignore-case
rg 'minor failure|appears minor|otherwise complete' .feature/
```

**Signal**:
```
Gate: Validate failed (2 tests failing), but proceeding to release because
      failures appear minor and the feature is otherwise complete.
```

**Why this matters**: Gates are binary. Downstream phases depend on upstream correctness — releasing with failing validation tests ships broken code. There is no "minor failure" category.

**Preferred action**:
```
Gate failed: validate (2 tests failing)
  - auth_test.go:TestLoginExpiry
  - auth_test.go:TestRefreshToken
BLOCKED. Cannot advance to release. Fix failing tests and re-run validate.
```

---

### Use the CLI for All State Mutations

**Detection**:
```bash
# Find scripts opening the state JSON directly instead of via CLI
rg '\.feature/state.*\.json' . --type py
grep -rn 'open.*feature.*state' . --include="*.py"
```

**Signal**:
```python
import json
with open('.feature/state/my-feature.json', 'w') as f:
    json.dump({'phase': 'validate', ...}, f)  # direct write — wrong
```

**Why this matters**: The state file format is an implementation detail of `feature-state.py`. Direct writes bypass validation, lock acquisition, and event recording. The CLI is the contract; the file schema is not.

**Preferred action**:
```bash
# Always use the CLI, never the file path
python3 ~/.claude/scripts/feature-state.py advance my-feature
python3 ~/.claude/scripts/feature-state.py gate my-feature implement.custom-gate
```

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `Phase mismatch: expected implement, current is plan` | Advance called before plan phase completed | Complete plan phase, run `checkpoint plan`, then advance |
| `No design artifact found in .feature/state/design/` | Design phase did not write artifact, or wrong slug | Re-run design phase; verify feature name slug matches directory |
| `Consultation required for Medium+ feature` | ADR exists but no synthesis.md | Run `/adr-consultation` before continuing implement |
| `Consultation blocked implementation` | synthesis.md verdict is BLOCKED | Resolve concerns in `adr/{name}/concerns.md`, then re-consult |
| `Gate already passed: {name}` | Gate command called twice (idempotent) | Safe to ignore — gate was recorded on first call |
| `Feature not found: {slug}` | Slug doesn't match initialized feature | Run `feature-state.py status` to list active features |
| `Cannot advance: current phase has no completion checkpoint` | Checkpoint not recorded before advance | Run `checkpoint {phase}` with artifact, then advance |

---

## Detection Commands Reference

```bash
# Find state advance calls in lifecycle refs
rg 'feature-state\.py advance' skills/feature-lifecycle/

# Find gate failures in feature logs
grep -rn 'Gate.*fail\|BLOCKED' .feature/state/

# Find direct state file manipulation (bypass anti-pattern)
rg '\.feature/state.*\.json' . --type py

# Find agent retry loops beyond threshold in implement logs
grep -c 'Attempt' .feature/state/implement/*.md 2>/dev/null

# Confirm all phase artifacts exist before release
ls .feature/state/design/ .feature/state/plan/ .feature/state/implement/ .feature/state/validate/
```

---

## See Also

- `shared.md` — state machine commands and directory structure
- `implement.md` — Tier 1/2/3 deviation classification detail
- `validate.md` — gate definitions and quality gate skill routing
