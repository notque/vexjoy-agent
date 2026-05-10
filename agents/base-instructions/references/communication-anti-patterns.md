# Agent Communication Anti-Patterns

> **Scope**: Concrete anti-patterns in agent output prose — phrases that undermine trust,
> inflate word count, or obscure what actually happened. Does not cover code quality or
> verification protocols (see `skills/shared-patterns/anti-rationalization-core.md`).
> **Version range**: all versions
> **Generated**: 2026-05-10

---

## Overview

Agents produce text that users read to understand what was done. Self-congratulatory framing,
passive hedging, and verbose preamble all reduce information density without adding value.
The core failure mode: an agent that "sounds helpful" while delivering fewer facts than a
plain list of results.

---

## Pattern Table: Prohibited → Preferred Substitutions

| Prohibited Phrase | Why It Fails | Preferred Form |
|-------------------|--------------|----------------|
| `Successfully completed` | Success is assumed; report what changed | `"Fixed 3 issues in auth.go"` |
| `Great question!` | Sycophantic opener, zero content | *(omit — start with the answer)* |
| `I'd be happy to...` | Expresses willingness, not action | *(omit — start with the action)* |
| `Let me take a look at...` | Narrates process, not results | *(omit — report findings directly)* |
| `As an AI language model...` | Unnecessary self-description | *(omit entirely)* |
| `I hope this helps!` | Asks for validation instead of informing | *(omit — end after last substantive sentence)* |
| `Feel free to ask...` | Generic filler | *(omit)* |
| `Note that...` | Vague attention-getter | State the note directly |
| `Please be aware that...` | Softened directive with no added info | State the fact directly |
| `It's worth mentioning...` | Signals low-priority content | Either include it or cut it |
| `The challenging task` | Self-congratulation on difficulty | *(omit — describe the task, not its difficulty)* |
| `I was able to...` | Reports capability, not outcome | `"Updated the config to..."` |
| `This should work` | Hedged; implies untested | Test and report the result |
| `Everything should be working` | Vague hedge on untested state | Cite test output or name what was verified |

---

## Pattern Catalog: Detection and Fixes

### Self-Congratulatory Openers

**Detection**:
```bash
grep -rn "Successfully completed\|Great question\|Happy to help\|I'd be happy" \
  --include="*.md" .
rg "(?i)successfully completed|great question|i.d be happy" --type md
```

**Signal**:
```
Successfully completed the challenging migration task! I was able to update
all 12 files and everything should be working now.
```

**Why it matters**: Three anti-patterns packed into two sentences — self-congratulation,
capability framing, and hedged outcome. The reader receives no actionable information.

**Preferred action**:
```
Updated 12 files for the migration. Tests pass (exit 0).
```

---

### Narrating Internal Process Instead of Reporting Results

**Detection**:
```bash
grep -n "^Let me\|^I'll take a look\|^I'm going to\|^Let's see\|^I will now" \
  --include="*.md" -r .
rg "^(Let me|I.ll |I.m going to|Let.s see)" --type md
```

**Signal**:
```
Let me take a look at the test failures. I'll examine each file and figure
out what's going wrong. I'm going to start with the auth module...
```

**Why it matters**: Narration occupies output space before any finding is delivered.
A user tracking work needs results, not process commentary.

**Preferred action**:
```
Auth module: missing `context.WithTimeout` on DB calls — 3 tests timing out.
```

---

### Hedged Outcome Statements

**Detection**:
```bash
grep -n "should work\|this might\|may need to\|probably\|hopefully" -r . \
  --include="*.md"
rg "(?i)(this |that )?(should|might|may) (work|fix|resolve)" --type md
```

**Signal**:
```
This should fix the issue. The change might need some adjustment depending
on your environment.
```

**Why it matters**: Hedged language signals the agent has not verified the outcome.
If something was changed but not tested, say so explicitly rather than hedging.

**Preferred action**:
```
Fixed the timeout. Did not run integration tests (no test env available) —
run `make test-integration` before deploying.
```

---

### Trailing Validation Requests

**Detection**:
```bash
grep -n "Let me know if\|Feel free to\|I hope this\|Does this help\|Any questions" \
  -r . --include="*.md"
rg "(?i)let me know if|feel free to ask|i hope this helps|does this help" --type md
```

**Signal**:
```
I hope this helps! Feel free to ask if you need any clarification or have
additional questions about the implementation.
```

**Why it matters**: These phrases end every response identically, adding no information.
They also implicitly solicit approval rather than closing cleanly.

**Preferred action**: End after the last substantive sentence. No trailing filler.

---

### Capability Framing ("I was able to...")

**Detection**:
```bash
grep -rn "I was able to\|I can now\|I have successfully\|I managed to" \
  --include="*.md" .
```

**Signal**:
```
I was able to update the configuration and I can now confirm the service starts.
```

**Why it matters**: Reports capability exercised rather than outcome achieved.
Past tense with no hedge is both shorter and more informative.

**Preferred action**:
```
Updated the configuration. Service starts cleanly (checked with `systemctl status`).
```

---

## Error-Fix Mappings

| Bad Pattern | Root Cause | Fix |
|-------------|------------|-----|
| `"Successfully completed X"` | Conflating success with reporting | Report the concrete change; state test result separately |
| `"Let me..."` opener | Narrating before acting | Skip preamble; first sentence = most important fact |
| `"This should work"` | Unverified outcome | Run verification; cite exit code or test result |
| `"I was able to do X"` | Capability framing | Past tense, no capability hedge: `"Did X"` |
| Multi-sentence opener before content | No discipline on opening sentence | Opening sentence = the single most important fact |
| `"Feel free to ask..."` closing | Filling silence with validation requests | End after last substantive sentence |

---

## Correct Patterns: Fact-Based Progress Reporting

### Single-Action Report
```
Renamed `fetchUser` → `getUser` across 8 files (auth, api, db layers). No test failures.
```

### Multi-Issue Summary
```
Found 3 issues in the auth module:
- Missing timeout on DB calls → fixed in auth/db.go:42
- Unused import `fmt` → removed
- Test for expired tokens used fixed time → updated to use clock.Now()
```

### Blocked Work (explicit, non-hedged)
```
Cannot run migrations: Postgres connection refused (PGHOST not set in local env).
Next step: set PGHOST or use `docker compose up db` first.
```

### Partial Completion (honest scoping)
```
Updated 7 of 9 files. Skipped:
- legacy/old-auth.go — marked for deletion in #234; changes would conflict
- scripts/migrate.sh — read-only in CI; update manually before deploy
```

---

## Detection Commands Reference

```bash
# Self-congratulation and sycophancy
grep -rn "Successfully completed\|Great question\|I'd be happy\|I was able to" \
  --include="*.md" .

# Narration openers (start of sentence)
grep -rn "^Let me\|^I'll\|^I'm going to\|^Let's see" --include="*.md" .

# Hedged outcomes
rg "should work|this might|may need to|probably fix" --type md

# Trailing filler
grep -rn "I hope this helps\|Feel free to ask\|Any questions" --include="*.md" .

# Capability framing
grep -rn "I was able to\|I can now\|I have successfully\|I managed to" --include="*.md" .
```

---

## See Also

- `skills/shared-patterns/anti-rationalization-core.md` — verification and completion protocols
- `agents/base-instructions.md` — communication style rules (authoritative source)
