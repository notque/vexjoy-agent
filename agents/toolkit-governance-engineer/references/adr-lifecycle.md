# ADR Lifecycle Reference

> **Scope**: ADR status transitions, validation criteria, consultation records, and local-only governance. Does not cover routing tables or frontmatter compliance (see sibling reference files).
> **Version range**: all toolkit versions
> **Generated**: 2026-04-15

---

## Overview

ADRs are local working documents that track architectural decisions. They live in `adr/` (gitignored) and never get committed. The lifecycle moves through four states: `Proposed → Accepted → Implemented → Superseded`. Skipping a state is a governance violation — a `Proposed` ADR should not jump directly to `Implemented` without explicit `Accepted` confirmation, because that bypasses the consultation record and validation criteria.

---

## Status Transition Table

| From | To | Required Before Transitioning | Common Skip Error |
|------|----|-------------------------------|-------------------|
| `Proposed` | `Accepted` | Decision documented, alternatives listed, consultation complete | Moving to Implemented before acceptance |
| `Accepted` | `Implemented` | Validation criteria written, implementation verified against them | Marking implemented before criteria are met |
| `Implemented` | `Superseded` | New ADR number referenced, rationale for supersession documented | Deleting instead of superseding |
| Any | `Rejected` | Rejection reason documented, alternatives noted | Silently deleting instead of rejecting |

---

## ADR File Format

```markdown
# ADR-NNN: Title

## Status
Proposed — YYYY-MM-DD

## Date
YYYY-MM-DD

## Context
[Why this decision is needed. What problem it solves. Constraints.]

## Decision
[What was decided. Be specific enough that "Implemented" can be verified.]

## Alternatives Considered
[What else was considered and why it was rejected. Required for Accepted status.]

## Validation Criteria
[Concrete, checkable criteria that prove implementation is complete.]
[Required before transitioning Accepted to Implemented.]

## Consultation Notes
[Records from adr-consultation sessions. Required for contested decisions.]

## Consequences
[What changes because of this decision. Positive and negative.]
```

---

## Correct Patterns

### Status Line Format

The status line must include the state word and the date.

```markdown
## Status
Proposed — 2026-04-15

## Status
Accepted — 2026-04-15. [Optional one-line summary of acceptance condition.]

## Status
Implemented — 2026-04-15. Validation: all 3 criteria met (see criteria section).

## Status
Superseded — 2026-04-15. Superseded by ADR-NNN.

## Status
Rejected — 2026-04-15. [One-line reason.]
```

**Why**: The date is required for time-ordered audit trails. `scripts/adr-status.py` parses the date to compute ADR age and flag stale proposed items.

---

### Validation Criteria Before Implementing

Write concrete, falsifiable criteria in `Accepted` state before marking `Implemented`.

```markdown
## Validation Criteria
- [ ] `python3 scripts/new-feature.py --check` exits 0
- [ ] `grep -r "old-pattern" agents/ skills/` returns no matches
- [ ] At least one existing test exercises the new path
- [ ] INDEX.json regenerated and coverage count unchanged
```

**Why**: Vague criteria ("feature works") cannot be objectively verified. Concrete criteria make `Implemented` status auditable — anyone reading the ADR can confirm implementation without re-investigating.

---

### Consultation Records

When `adr-consultation` is dispatched, record its output in the ADR.

```markdown
## Consultation Notes
### 2026-04-15 — adr-consultation run
Challenger raised: "This breaks existing consumers if they rely on field ordering."
Resolution: Field ordering is not guaranteed by the spec — confirmed in docs/PHILOSOPHY.md §3.
Decision unchanged.
```

**Why**: Consultation records prevent re-litigating decisions. If the same objection appears later, the ADR shows it was already considered and explains why it was resolved that way.

---

## Pattern Catalog
<!-- no-pair-required: section header with no content -->

### ❌ Proposed to Implemented Without Accepted Step

**Detection**:
```bash
# Find Implemented ADRs that lack a prior Accepted state record
grep -rn "Implemented" adr/*.md | cut -d: -f1 | sort -u | xargs grep -L "Accepted"

# Find Implemented ADRs missing Validation Criteria section
grep -rn "Implemented" adr/*.md | cut -d: -f1 | sort -u | xargs grep -L "Validation Criteria"
```

**What it looks like**: <!-- no-pair-required: sub-block split by code-comment heading; Do instead is inline below -->
```markdown
## Status
Implemented — 2026-04-15
# (no Accepted state, no Validation Criteria section)
```

**Do instead:** Add an explicit `Accepted` state before `Implemented`. See the positive guidance below.

**Why wrong**: Skipping `Accepted` means the decision was never formally reviewed and alternatives were never documented. `Implemented` status becomes meaningless — it cannot be distinguished from "I started writing code" versus "all criteria verified."

**Do instead:**

Add an explicit `Accepted` state with a completed `## Alternatives Considered` section and a checkable `## Validation Criteria` section before moving to `Implemented`. Run `grep -L "Accepted" adr/*.md` to find ADRs that skipped this step.

**Fix**: Add an `Accepted` block with alternatives and validation criteria, then re-evaluate whether `Implemented` is truly warranted.

---

### ❌ Deleting ADRs Instead of Superseding or Rejecting

**Detection**:
```bash
# Gaps in ADR numbering indicate deletions
python3 -c "
import glob, re, os
nums = []
for f in glob.glob('adr/*.md'):
    m = re.search(r'(\d+)-', os.path.basename(f))
    if m: nums.append(int(m.group(1)))
nums.sort()
if nums:
    gaps = [i for i in range(nums[0], nums[-1]+1) if i not in nums]
    if gaps: print('GAPS (possible deletions):', gaps)
    else: print('No numbering gaps found')
"
```

**Why wrong**: Deleting an ADR erases the decision history. Future contributors cannot tell whether a feature was rejected (do not implement it) or just never decided (still open). The absence looks like a gap in thinking rather than a deliberate choice.

**Do instead:**

Set the status to `Rejected — YYYY-MM-DD. [one-line reason]` or `Superseded — YYYY-MM-DD. Superseded by ADR-NNN.` The file stays in `adr/` permanently. Run the numbering-gap detection script to find any ADRs that were already deleted and document the gap.

**Fix**: Set status to `Rejected — YYYY-MM-DD. [reason]` or `Superseded — YYYY-MM-DD. Superseded by ADR-NNN.` Never delete.

---

### ❌ Missing Date in Status Line

**Detection**:
```bash
# Find status lines without em-dash and date
grep -n "^## Status" adr/*.md -A1 | grep -v " — [0-9]\|^adr\|^--\|^$"

# Alternative: find Proposed/Accepted/Implemented lines missing date pattern
grep -rn "^Proposed\|^Accepted\|^Implemented\|^Superseded\|^Rejected" adr/*.md | grep -v " — 20[0-9][0-9]-"
```

**What it looks like**: <!-- no-pair-required: sub-block split by code-comment heading; Do instead is inline below -->
```markdown
## Status
Implemented
```

**Do instead:** Always append ` — YYYY-MM-DD` to every status line. See the positive guidance below.

**Why wrong**: `scripts/adr-status.py` parses the date from the status line to compute age and detect stale proposals. Missing dates silently break age-based reporting and make the audit trail unreliable.

**Do instead:**

Always write the full status line: `Proposed — YYYY-MM-DD` (or `Accepted`, `Implemented`, `Superseded`, `Rejected`). Use the detection command `grep -rn "^Proposed\|^Accepted\|^Implemented" adr/*.md | grep -v " — 20"` to find lines missing the date.

**Fix**: Always append ` — YYYY-MM-DD` to every status line.

---

### ❌ Validation Criteria Written After Marking Implemented

**What it looks like**:
Criteria written in future tense ("will verify", "should check") or added to the ADR after the `Implemented` date stamp.

**Do instead:** Write criteria in present-tense checkboxes during the `Accepted` phase, before any implementation begins. See the positive guidance below.

**Detection**:
```bash
# Find criteria using future tense (indicative of post-hoc writing)
grep -rn "will verify\|should check\|to be verified\|TBD" adr/*.md
```

**Why wrong**: Validation criteria written after the fact are retroactive justifications, not pre-agreed standards. They cannot prove the implementation met a standard that didn't exist when work was done.

**Do instead:**

Write validation criteria as present-tense checkboxes in the `## Validation Criteria` section while the ADR is in `Accepted` state. Each criterion must be falsifiable: a specific command to run or a specific condition to check. Only mark `Implemented` after every checkbox is confirmed.

**Fix**: Write criteria in present tense as checkboxes during the `Accepted` phase. Mark each criterion complete only when verified during implementation.

---

## Error-Fix Mappings

| Symptom | Root Cause | Fix |
|---------|------------|-----|
| `scripts/adr-status.py` cannot parse status date | Missing ` — YYYY-MM-DD` in status line | Add date in `Status — YYYY-MM-DD` format |
| ADR shows as "stale" in status report | Status is Proposed and last modified >30 days ago | Advance status or add a hold note explaining delay |
| Consultation rejected but decision still advanced | No consultation record in ADR body | Add consultation notes section with objection and resolution |
| ADR not found by `adr-status.py` | Filename doesn't match `NNN-kebab-title.md` pattern | Rename to match; script scans by glob pattern |
| `grep -L "Alternatives"` returns this ADR | Accepted without listing alternatives | Add `## Alternatives Considered` section before re-advancing |

---

## Detection Commands Reference

```bash
# List all ADRs with their current status
grep -h "^## Status" adr/*.md -A1 | grep -v "^## Status\|^--"

# Find Proposed ADRs older than 30 days (stale proposals)
python3 -c "
import glob, re
from datetime import datetime
for f in glob.glob('adr/*.md'):
    txt = open(f).read()
    m = re.search(r'Proposed — (\d{4}-\d{2}-\d{2})', txt)
    if m:
        age = (datetime.now() - datetime.strptime(m.group(1), '%Y-%m-%d')).days
        if age > 30: print(f'STALE ({age}d): {f}')
"

# Find Implemented ADRs missing Validation Criteria
grep -rn "Implemented" adr/*.md | cut -d: -f1 | sort -u | xargs grep -L "Validation Criteria"

# Find ADRs missing Alternatives Considered (required for Accepted+)
grep -rL "Alternatives" adr/*.md

# Find status lines without date
grep -rn "^Proposed\|^Accepted\|^Implemented\|^Superseded\|^Rejected" adr/*.md | grep -v " — 20"

# Find validation criteria with future tense (post-hoc writing)
grep -rn "will verify\|should check\|to be verified" adr/*.md
```

---

## See Also

- `routing-table-patterns.md` — INDEX.json validation, component registration
- `frontmatter-compliance.md` — YAML field compliance for agents and skills
- `docs/PHILOSOPHY.md` — deterministic validation and anti-rationalization principles
- `scripts/adr-status.py` — CLI for ADR status reporting and intake queue
