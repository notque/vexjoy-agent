# PR Fix Loop: Message Formats

Load in Phase 2 and Phase 4. Use these formats exactly; the owner reads many of them in a row.

## Phase 2: discussion format (one PR per message, in merge order)

```markdown
## <PR full URL>

**State:** head <full sha> (Phase 4 lease baseline), version <x.y.z>, merge order <n of m>, CI <green|red|pending>

**What it changes and why:** <the problem, with live numbers>

**What's right:** <points, each with evidence>

**Problems:**
| Severity | file:line | What's wrong | Proposed fix |
|----------|-----------|--------------|--------------|

**One-commit plan:** <the one real thing>; Docker validation: <exact before/after/control>; run on final code: <yes|not yet>

**Confidence:** <total | not yet: what is missing>

**Decisions for the owner:**
1. <question> Recommendation: <answer, one reason>
2. ...

**Defaults I picked:** <each default, overridable>
```

## Phase 3: Docker table

| Run | Input | Expected | Observed |
|-----|-------|----------|----------|
| before | <branch base, real input> | bug shows | |
| after | <PR head, same input> | fix shows | |
| control | <unrelated input> | unchanged | |

## Phase 4: publish result

```markdown
## <PR full URL>

**Head:** <sha12>, one commit: <yes|no>
**CI:** <per check: pass|fail|pending>
**Copilot:** <registered: yes|no | not available on this host>
**Round:** <n of 3>
| # | Comment | Verdict | Action |
|---|---------|---------|--------|
| 1 | <summary> | valid / invalid | fixed in <sha12> / reasoning in <local file> |

**Docker:** <table from Phase 3>
**Body:** <exact body as pushed>
**Unverified:** <anything not proven, or "none">
```
