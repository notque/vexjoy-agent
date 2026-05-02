---
name: sapcc-audit
description: "Full-repo SAP CC Go compliance audit against review standards."
user-invocable: false
command: /sapcc-audit
agent: golang-general-engineer
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Task
  - Skill
routing:
  triggers:
    - sapcc audit
    - sapcc compliance
    - check sapcc rules
    - full repo audit
    - sapcc secondary review
    - sapcc standards check
  pairs_with:
    - golang-general-engineer
    - golang-general-engineer-compact
    - go-patterns
  force_route: false
  complexity: Complex
  category: language
---

# SAPCC Full-Repo Compliance Audit v2

Review every package against established standards. Not checklist compliance -- **code-level review** finding over-engineering, dead code, interface violations, and inconsistent patterns.

---

## Reference Loading Table

| Signal | Load This File | When |
|--------|---------------|------|
| Phase 1 begins | `references/phase-1-discover-commands.md` | Detection commands, package mapping, segmentation table |
| Phase 2 begins | `references/phase-2-dispatch-agents.md` | Full dispatch prompt and per-domain review checklist (11 areas) |
| Phase 3 begins | `references/output-templates.md` | Report scaffold, per-finding format, severity guide |

Load each at phase start. Do not load all upfront.

---

## Instructions

### Phase 1: DISCOVER

**Goal**: Map repository and plan package segmentation.

Read `references/phase-1-discover-commands.md` for detection commands, segmentation table, and file-count queries.

Verify sapcc project (sapcc imports in go.mod). If not, stop immediately.

Map all packages, count files per package, produce segmentation table (5-8 agents, 5-15 files each).

**Gate**: Packages mapped, agents planned.

---

### Phase 2: DISPATCH

**Goal**: Launch parallel agents reviewing packages against project standards.

Read `references/phase-2-dispatch-agents.md` for full dispatch prompt (11 review areas: over-engineering, dead code, error messages, constructors, interface contracts, copy-paste, HTTP handlers, database patterns, type patterns, logging, mixed approaches).

Use dispatch prompt verbatim, substituting assigned package list. **Dispatch all agents in a single message using Task tool with `subagent_type=golang-general-engineer`.**

**Gate**: All agents dispatched.

---

### Phase 3: COMPILE REPORT

**Goal**: Aggregate findings into code-level compliance report.

Read `references/output-templates.md` for report scaffold, per-finding format, deduplication rules.

Deduplicate by `file:line`. Write `sapcc-audit-report.md`. Display verdict, must-fix count, top 5 findings inline.

**Schema Validation:**
```bash
python3 scripts/validate-review-output.py --type sapcc-audit sapcc-audit-report.md
```
Checks: package_summary present, must_fix/should_fix/nit sections populated, findings have file:line references.

**Gate**: Report complete.

---

## Error Handling

| Scenario | Response |
|----------|----------|
| Not sapcc project | Stop. Print: "This does not appear to be an SAP CC Go project (no sapcc imports in go.mod)." |
| Agent cannot read file | Log and continue. Flag in report under "Warnings." |
| gopls MCP unavailable | Fall back to grep-based analysis. Note in report. |
| >30 packages | Split into >8 agents. Keep 5-15 files each. |
| No violations found | Valid report. Empty sections for unused severity levels. |

**Audit only**: READS and REPORTS. Does NOT modify code unless `--fix` specified.

---

## Integration

- **Router**: `/do` routes via "sapcc audit", "sapcc compliance", "sapcc lead review"
- **Pairs with**: `go-patterns` (rules), `golang-general-engineer` (executor)

### Per-agent reference loading (in dispatch prompt, based on assigned packages)

| Package Type | Reference |
|-------------|-----------|
| HTTP handlers (`internal/api/`) | `api-design-detailed.md` |
| Test files (`*_test.go`) | `testing-patterns-detailed.md` |
| Error handling heavy | `error-handling-detailed.md` |
| Architecture/drivers | `architecture-patterns.md` |
| Build/CI config | `build-ci-detailed.md` |
| Import-heavy files | `library-reference.md` |

Available for calibration (load when needed): `quality-issues.md`, `review-standards-lead.md`.
