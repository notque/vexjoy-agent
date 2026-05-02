---
name: integration-checker
description: "Verify cross-component wiring and data flow."
user-invocable: false
command: /integration-checker
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
routing:
  triggers:
    - integration check
    - check integration
    - verify wiring
    - are components connected
    - check connections
    - integration-checker
    - wiring check
  pairs_with:
    - feature-lifecycle
    - systematic-code-review
  complexity: Medium
  category: process
---

# Integration Checker Skill

Catches the most common class of bugs in AI-generated code: components that are individually correct but not connected. A function can exist, pass verification, and never be imported or called. An API endpoint can be defined but never wired into the router.

Read-only analysis — reports but does not fix. Fixes route back to /feature-lifecycle (implement phase) or the user.

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| tasks related to this reference | `wiring-checks.md` | Loads detailed guidance from `wiring-checks.md`. |

## Instructions

### Phase 0: PRIME

**Step 1**: Read repository CLAUDE.md (if present) and follow project-specific conventions.

**Step 2: Detect execution context**
- **Pipeline**: Check for `.feature/state/implement/` artifact. If present, scope to changed/added files.
- **Standalone**: Scope to current working directory or user-specified path. Analyze all source files.

**Step 3: Detect project language(s)** — different languages have fundamentally different import/export patterns.

> See `references/wiring-checks.md` for language detection indicators, per-language patterns, and common integration failures.

Multiple languages may coexist. Run all applicable techniques.

**Gate**: Language(s) detected. Scope established.

---

### Phase 1: EXPORT/IMPORT MAP

**Goal**: Classify every in-scope export as WIRED, IMPORTED_NOT_USED, or ORPHANED.

**Step 1: Discover exports**

Scan source files for exported symbols (language-aware):
- **Go**: Capitalized function, type, const, var at package level. Include method receivers on exported types.
- **Python**: Module-level definitions. Check `__all__` and `__init__.py` re-exports.
- **TypeScript/JavaScript**: `export` declarations, `export default`, barrel re-exports.

Skip `node_modules/`, `vendor/`, `.git/`, `__pycache__/`, `dist/`, `build/`, test fixtures, generated files.

Record: `{file, name, kind (function/type/const/var), line}`.

**Step 2: Discover imports and usages**

For each export, search for:
1. **Import**: Symbol appears in an import statement referencing the exporting module
2. **Usage**: Imported symbol is actually used (called, referenced, assigned, passed) beyond the import statement

Both required. Import without usage is a distinct failure from an orphan.

**Step 3: Classify each export**

> See `references/wiring-checks.md` for classification table, exclusion list, and files to skip.

**Step 4: Build the map** — report failures first (ORPHANED before IMPORTED_NOT_USED before WIRED):

```
## Export/Import Map

### ORPHANED (Failure)
| File | Export | Kind | Imported By |
|------|--------|------|-------------|
| api/handlers.go | HandleUserDelete | func | (none) |

### IMPORTED_NOT_USED (Warning)
| File | Export | Kind | Imported By | Used? |
|------|--------|------|-------------|-------|
| api/handlers.go | HandleUserUpdate | func | routes/api.go | No |

### WIRED (Pass) — [N] components
(Shown only in verbose mode)
```

**Gate**: All in-scope exports classified. Map produced.

---

### Phase 2: DATA FLOW AND CONTRACT CHECK

**Goal**: For WIRED components, verify real data flows through connections and output shapes match input expectations. Structural analysis only — not semantic correctness.

#### Data Flow Tracing

For each WIRED connection, check whether real data reaches the component.

> See `references/wiring-checks.md` for data flow failure patterns (hardcoded empty data, placeholder data, dead parameters, mock remnants) and contract mismatch patterns (shape, type, event/message) with confidence levels.

**Gate**: Data flow and contract findings recorded.

---

### Phase 3: REPORT

**Step 1: Requirements integration map (pipeline mode only)**

If running within feature pipeline and task plan exists in `.feature/state/plan/`, trace each requirement from entry point to implementation (WIRED / PARTIAL / UNWIRED).

> See `references/wiring-checks.md` for map format and status definitions.

**Step 2: Compile integration report**

```markdown
# Integration Check Report

## Summary
- Components checked: [N]
- WIRED: [N]
- IMPORTED_NOT_USED: [N]
- ORPHANED: [N]
- Data flow issues: [N]
- Contract mismatches: [N]
- Integration score: [WIRED / (WIRED + IMPORTED_NOT_USED + ORPHANED) * 100]%

## Verdict: PASS / WARN / FAIL

PASS: No ORPHANED, no data flow issues, no contract mismatches
WARN: No ORPHANED, but has IMPORTED_NOT_USED or low-confidence contract findings
FAIL: Has ORPHANED, data flow issues, or high-confidence contract mismatches

## Export/Import Map
[From Phase 1 — issues only, unless verbose]

## Data Flow Issues
[From Phase 2]

## Contract Mismatches
[From Phase 2 — with confidence level]

## Requirements Integration Map
[If pipeline mode]

## Recommended Actions
1. [Specific action per ORPHANED component]
2. [Specific action per IMPORTED_NOT_USED]
3. [Specific action per data flow issue]
4. [Specific action per contract mismatch]
```

Only fail on high-confidence contract mismatches. Low-confidence findings in dynamic languages are WARN, not FAIL.

**Step 3: Next steps**

| Verdict | Next Step |
|---------|-----------|
| **PASS** | Proceed to /feature-lifecycle (validate phase) |
| **WARN** | Review warnings. Proceed if intentional; fix if not. |
| **FAIL** | Route back to /feature-lifecycle (implement phase) with specific wiring tasks. |

**Gate**: Report produced with verdict and recommendations.

---

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| No source files found | Wrong scope or empty project | Verify working directory, check scope parameter |
| Language not detected | No recognizable build files | Specify language manually or check project structure |
| Too many exports | Large monorepo | Narrow scope to changed files (`git diff --name-only` against base branch) |
| False positive ORPHANED | Library code, plugin interfaces, entry points | Check exclusion patterns; add legitimate public API to exclusions |
| Circular import detected | Python/Go import cycles | Report as separate finding |
| No implementation artifact | Pipeline mode but implement phase didn't checkpoint | Fall back to standalone mode using git diff |

## References

- [Feature State Conventions](../feature-lifecycle/references/shared.md)
- [ADR-078: Integration Checker](../../adr/078-integration-checker.md)
