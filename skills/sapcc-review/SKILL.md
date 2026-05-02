---
name: sapcc-review
description: "Gold-standard SAP CC Go code review: 10 parallel domain specialists."
user-invocable: false
argument-hint: "[--fix]"
command: /sapcc-review
agent: golang-general-engineer
allowed-tools:
  - Agent
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - TaskCreate
  - TaskUpdate
  - TaskList
  - EnterWorktree
routing:
  triggers:
    - sapcc review
    - sapcc lead review
    - sapcc compliance review
    - comprehensive sapcc audit
    - full sapcc check
    - review sapcc standards
  pairs_with:
    - golang-general-engineer
    - go-patterns
    - sapcc-audit
  force_route: false
  complexity: Complex
  category: language
---

# SAPCC Comprehensive Code Review v1

10-agent domain-specialist review. Each agent masters one rule domain and scans every package for violations.

**vs /sapcc-audit**: sapcc-audit segments by *package* (generalist per package). sapcc-review segments by *rule domain* (specialist per concern, cross-package). Specialists find issues generalists miss.

---

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| tasks related to this reference | `agent-dispatch-prompts.md` | Loads detailed guidance from `agent-dispatch-prompts.md`. |
| tasks related to this reference | `report-template.md` | Loads detailed guidance from `report-template.md`. |

## Instructions

### Phase 1: DISCOVER

**Goal**: Map repository, verify sapcc project, plan review.

**Step 1: Verify sapcc project**

```bash
cat go.mod | head -5
grep -c "sapcc" go.mod
```

If module path doesn't contain "sapcc" AND no sapcc imports, warn but continue.

**Step 2: Map Go packages/files**

```bash
find . -name "*.go" -not -path "*/vendor/*" | wc -l
find . -name "*.go" -not -path "*/vendor/*" | sed 's|/[^/]*$||' | sort | uniq -c | sort -rn
find . -name "*_test.go" -not -path "*/vendor/*" | wc -l
```

**Step 3: Check key imports**

```bash
grep -r "go-bits" go.mod
grep -r "go-api-declarations" go.mod
grep -r "gophercloud" go.mod
grep -r "gorilla/mux" go.mod
grep -r "database/sql" go.mod
```

**Step 4: Create task_plan.md**

```markdown
# Task Plan: SAPCC Review -- [repo name]

## Goal
Comprehensive code review of [repo] against project standards, 10 domain-specialist agents.

## Phases
- [x] Phase 1: Discover repo structure
- [ ] Phase 2: Dispatch 10 specialist agents
- [ ] Phase 3: Aggregate findings
- [ ] Phase 4: Write report

## Repo Profile
- Module: [module path]
- Packages: [N]
- Go files: [M] (excluding vendor)
- Test files: [T]
- Key imports: [list]

## Status
**Currently in Phase 2** - Dispatching agents
```

**Gate**: Repo mapped, plan created.

---

### Phase 2: DISPATCH

**Goal**: Launch 10 domain-specialist agents in ONE message for parallel execution.

**CRITICAL**: All 10 agents in ONE message via Agent tool.

Each agent receives:
1. Path to sapcc-code-patterns.md
2. Assigned sections to focus on
3. Domain-specific reference file (each loads ONLY what it needs)
4. Instructions to scan ALL .go files
5. Exact output format for findings

See `references/agent-dispatch-prompts.md` for shared preamble and all 10 agent specs.

**Gate**: All 10 dispatched in single message. Wait for completion.

---

### Phase 3: AGGREGATE

**Goal**: Compile findings into single prioritized report.

**Step 0**: Run `git status --short` (not just `git diff --stat`) to capture both modified AND untracked files.

**Step 1**: Read each agent's output. Extract findings with severity, file, rule, code.

**Step 2: Deduplicate** -- Same file:line => keep higher severity with more specific rule citation.

**Step 3: Prioritize** -- Apply cross-repository reinforcement from S35. See `references/report-template.md` for severity boost table.

**Step 4: Quick Wins** -- Mark findings that are single-line changes, no behavioral change, low risk of breaking tests. Goes in "Quick Wins" section.

**Step 5**: Write `sapcc-review-report.md` using template from `references/report-template.md`.

**Schema Validation:**
```bash
python3 scripts/validate-review-output.py --type sapcc-review sapcc-review-report.md
```
Checks: 10-agent scorecard present, quick_wins populated, findings have file:line references.

**Gate**: Report written. Display summary. Proceed to Phase 4 if `--fix`.

---

### Phase 4: FIX (Optional -- only with `--fix`)

**Step 1**: Use `EnterWorktree` to create isolated copy named `sapcc-review-fixes`.

**Step 2: Apply Quick Wins first** (lowest risk). After each group:

```bash
go build ./...
go vet ./...
make check 2>/dev/null || go test ./...
```

**Step 3**: Apply Critical/High fixes in order. Test between each. If fix breaks tests, revert and note.

**Step 4**: Commit:

```bash
git add -A
git commit -m "fix: apply sapcc-review findings (N fixes across M files)"
```

**Step 5**: Update `sapcc-review-report.md` with: which fixed, which skipped (why), test results.

---

## Error Handling

**Agent fails or empty findings**:
1. Verify repo has Go files
2. Check agent logs for permission errors or gopls MCP failures
3. Timeout => increase or split into two waves of 5
4. "No findings" = successful completion -- domain is clean

**Finding looks wrong** (false positive):
- Cross-check with cited sapcc-code-patterns.md section
- Contradicts reference => note discrepancy, file toolkit issue
- Pre-existing code older than rule => mark LOW, note in systemic recommendations

**`--fix` breaks tests**:
1. Revert failed fix
2. Note needs manual review with failure reason
3. Continue with next fix

---

## References

- **sapcc-code-patterns.md** -- 36-section reference (single source of truth)
- **Per-agent reference files**:
  - Agent 1: `review-standards-lead.md`
  - Agent 2: `architecture-patterns.md`
  - Agent 3: `api-design-detailed.md`
  - Agent 4: `error-handling-detailed.md`
  - Agent 5: (none -- rules inline in S7 + S27)
  - Agent 6: `testing-patterns-detailed.md`
  - Agent 7: `architecture-patterns.md`
  - Agent 8: (none -- rules inline in S14, S15, S29)
  - Agent 9: (none -- rules inline in S16-18, S20)
  - Agent 10: `preferred-patterns.md`
- **Optional deep-dive**: `pr-mining-insights.md`, `library-reference.md`
- **Progressive disclosure**: `references/agent-dispatch-prompts.md`, `references/report-template.md`

**Integration**:
- Complements `/sapcc-audit` (package-level generalist) -- use both for max coverage
- Prerequisite: go-patterns skill at `~/.claude/skills/go-patterns/`
- Sync: `cp -r skills/sapcc-review ~/.claude/skills/sapcc-review`
- Router: `/do` routes via "sapcc review", "sapcc lead review", "comprehensive sapcc audit"
