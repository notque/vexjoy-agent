---
name: integration-checker
description: "Verify cross-component wiring and data flow."
version: 1.0.0
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
    - feature-implement
    - feature-validate
    - comprehensive-review
  complexity: Medium
  category: process
---

# Integration Checker Skill

**Existence does not equal integration.** A component existing is implementation-level verification; a component being connected is integration-level verification. Both are necessary. Neither is sufficient alone.

This skill catches the most common class of real-world bugs in AI-generated code: components that are individually correct but not connected to each other. A function can exist, contain real logic, pass correctness verification, and never be imported or called. An API endpoint can be defined but never wired into the router. An event handler can be registered but never receive events.

This is a read-only analysis skill -- it reads and reports but does not fix wiring issues. Fixes route back to /feature-implement or the user, because integration fixes often require design decisions about which component should call which.

---

## Instructions

### Phase 0: PRIME

**Goal**: Establish context, detect language, identify scope.

**Step 1: Read repository CLAUDE.md** (if present) and follow any project-specific conventions before proceeding.

**Step 2: Detect execution context**

Determine if running within the feature pipeline or standalone:
- **Pipeline**: Check for `.feature/state/implement/` artifact. If present, load it to understand what was built and scope the check to changed/added files. Scoping to changed files prevents wasting time analyzing unchanged code in large repositories.
- **Standalone**: Scope to the current working directory or user-specified path. Analyze all source files.

**Step 3: Detect project language(s)**

Detect language(s) before applying any verification techniques -- different languages have fundamentally different import/export patterns.

| Indicator | Language |
|-----------|----------|
| `go.mod`, `*.go` | Go |
| `pyproject.toml`, `setup.py`, `*.py` | Python |
| `tsconfig.json`, `*.ts`, `*.tsx` | TypeScript |
| `package.json`, `*.js`, `*.jsx` | JavaScript |

Multiple languages may coexist. Run all applicable techniques for each.

**Step 4: Identify language-specific patterns**

| Language | Export Pattern | Import Pattern | Common Integration Failures |
|----------|---------------|----------------|----------------------------|
| Go | Capitalized identifiers at package level | `import "path/to/pkg"` then `pkg.Name` | Exported function in wrong package; interface satisfied but never used via interface type; `init()` side effects not triggered because package not imported |
| Python | Module-level definitions, `__all__`, `__init__.py` re-exports | `from module import name`, `import module` | Circular imports causing silent failures; `__init__.py` missing re-export; relative vs absolute import mismatch |
| TypeScript | `export`, `export default`, barrel files (`index.ts`) | `import { name } from './module'` | Barrel file missing re-export; type-only import where value import needed; path alias not resolving |
| JavaScript | `module.exports`, `export`, `export default` | `require()`, `import` | CommonJS/ESM mismatch; default vs named export confusion |

**Gate**: Language(s) detected. Scope established. Proceed to Phase 1.

---

### Phase 1: EXPORT/IMPORT MAP

**Goal**: For every export in scope, determine its wiring status. Every export gets exactly one of three states -- no ambiguous classifications.

**Step 1: Discover exports**

Scan source files for exported symbols. Be language-aware:

- **Go**: Find all capitalized function, type, const, and var declarations at package level. Include method receivers on exported types.
- **Python**: Find all module-level function/class/variable definitions. Check `__all__` if present (it restricts the public API). Check `__init__.py` for re-exports.
- **TypeScript/JavaScript**: Find all `export` declarations, `export default`, and barrel file re-exports.

Skip `node_modules/`, `vendor/`, `.git/`, `__pycache__/`, `dist/`, `build/`, test fixtures, and generated files. These contain intentionally unused exports (library code, vendored deps) that would flood the report with false positives.

Record each export as: `{file, name, kind (function/type/const/var), line}`.

**Step 2: Discover imports and usages**

For each export found, search the codebase for:
1. **Import**: The symbol is imported (appears in an import statement referencing the exporting module)
2. **Usage**: The imported symbol is actually used (called, referenced, assigned, passed as argument) beyond the import statement itself

Both checks are required. An import without usage is a distinct failure mode from an orphan -- it signals someone intended to use the component but didn't finish wiring it.

**Step 3: Classify each export**

| Condition | Status | Severity |
|-----------|--------|----------|
| Exported, imported, AND used in at least one consumer | **WIRED** | Pass |
| Exported and imported, but never used beyond the import statement | **IMPORTED_NOT_USED** | Warning |
| Exported but never imported anywhere in the project | **ORPHANED** | Failure |

**Exclusions** (do not flag as ORPHANED -- these have legitimate reasons for not being imported internally):
- `main()` functions and entry points
- Interface implementations that satisfy an interface (Go)
- Test helpers exported for use by `_test.go` files in other packages
- Symbols listed in public API documentation or `__all__` in library packages
- CLI command handlers wired via registration (e.g., cobra commands, click groups)
- Exports in files matching exclusion patterns (vendor, node_modules, etc.)

**Step 4: Build the export/import map**

Report failures first -- users need to see ORPHANED before IMPORTED_NOT_USED before WIRED.

```
## Export/Import Map

### ORPHANED (Failure)
| File | Export | Kind | Imported By |
|------|--------|------|-------------|
| api/handlers.go | HandleUserDelete | func | (none) |
| utils/format.py | format_currency | func | (none) |

### IMPORTED_NOT_USED (Warning)
| File | Export | Kind | Imported By | Used? |
|------|--------|------|-------------|-------|
| api/handlers.go | HandleUserUpdate | func | routes/api.go | No |

### WIRED (Pass) — [N] components
(Shown only in verbose mode)
```

**Gate**: All in-scope exports classified. Map produced. Proceed to Phase 2.

---

### Phase 2: DATA FLOW AND CONTRACT CHECK

**Goal**: For WIRED components, verify that real data flows through the connections and that output shapes match input expectations. A component wired to always receive empty data is functionally disconnected.

This phase checks two things simultaneously because they both operate on the same set of WIRED connections identified in Phase 1.

This is structural analysis, not semantic verification. Contract checking verifies shape and naming compatibility, not whether data is logically correct -- semantic correctness would require runtime information that static analysis cannot provide.

#### Data Flow Tracing

For each WIRED connection, check whether real data actually reaches the component. Specifically look for:

**Hardcoded empty data:**
- Empty arrays/slices passed to functions that iterate over them: `processItems([])`, `handleUsers([]User{})`
- Empty strings passed where meaningful content is expected
- Zero values for IDs, counts, or sizes that should be populated
- `nil`/`None`/`null`/`undefined` passed where a real object is expected

**Placeholder data:**
- TODO/FIXME/HACK comments adjacent to data assignment
- Lorem ipsum, "test", "example", "placeholder" string literals in non-test code
- Zeroed structs or objects with no fields populated: `User{}`, `{}`

**Dead parameters:**
- Function declares a parameter but never reads it (not just `_` convention)
- Parameter is read only to immediately discard: `_ = param`

**Mock remnants:**
- `return []`, `return nil`, `return {}` in non-test code paths where real data is expected
- Hardcoded return values that bypass actual logic

Record each finding as: `{file, line, kind (empty-data|placeholder|dead-param|mock-remnant), description}`.

#### Cross-Component Contract Checking

For each WIRED connection where component A's output feeds into component B's input, verify structural compatibility:

**Shape mismatches:**
- A returns `{id, name, email}` but B expects `{userId, displayName, emailAddress}` -- field naming mismatch
- A returns a flat object but B destructures expecting nested structure
- A returns a single item but B expects an array (or vice versa)

**Type mismatches:**
- A returns a string ID but B expects a numeric ID
- A returns an optional/nullable value but B accesses it without null check

**Event/message contract mismatches:**
- Emitter sends event type `"user.created"` but handler listens for `"userCreated"`
- Message producer sends one schema, consumer expects different fields

Record each finding as: `{producer_file, consumer_file, mismatch_kind, description}`.

Report contract findings with appropriate confidence levels. In dynamic languages, approximate checking still catches obvious mismatches -- report what you can find rather than skipping the check:
- **High confidence**: Explicit type annotations match/mismatch, struct/interface definitions
- **Medium confidence**: Inferred from usage patterns, variable names, JSDoc/docstrings
- **Low confidence**: Dynamic access patterns, computed property names, reflection

Note: dynamically-loaded modules, reflection-based wiring, and plugin architectures cannot be analyzed with certainty through static analysis. Flag what is visible and note the limitation.

**Gate**: Data flow and contract findings recorded. Proceed to Phase 3.

---

### Phase 3: REPORT

**Goal**: Produce a structured integration report with actionable findings. Report facts and show the wiring map -- not prose about the wiring map.

**Step 1: Requirements integration map (pipeline mode only)**

If running within the feature pipeline and a task plan exists in `.feature/state/plan/`:

For each requirement in the plan, trace the integration path from entry point to implementation:

| Status | Meaning |
|--------|---------|
| **WIRED** | Requirement has a complete integration path from entry point to implementation |
| **PARTIAL** | Some components exist but the path has gaps (identify the gaps) |
| **UNWIRED** | Components may exist but no integration path connects them |

```
## Requirements Integration Map

| Requirement | Status | Integration Path |
|-------------|--------|-----------------|
| User can delete account | WIRED | DELETE /api/users/:id -> routes/api.go -> handlers.HandleUserDelete -> db.DeleteUser |
| Email notification on delete | PARTIAL | handlers.HandleUserDelete -> [GAP] -> email.SendNotification (exists but not called from handler) |
| Audit log on delete | UNWIRED | audit.LogEvent exists, but no call from any delete path |
```

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

PASS: No ORPHANED components, no data flow issues, no contract mismatches
WARN: No ORPHANED, but has IMPORTED_NOT_USED or low-confidence contract findings
FAIL: Has ORPHANED components, data flow issues, or high-confidence contract mismatches

## Export/Import Map
[From Phase 1 — only issues, unless verbose mode]

## Data Flow Issues
[From Phase 2 — data flow findings]

## Contract Mismatches
[From Phase 2 — contract findings with confidence level]

## Requirements Integration Map
[From Step 1 — if in pipeline mode]

## Recommended Actions
1. [Specific action for each ORPHANED component]
2. [Specific action for each IMPORTED_NOT_USED]
3. [Specific action for each data flow issue]
4. [Specific action for each contract mismatch]
```

Only fail the verdict on high-confidence contract mismatches. Low-confidence findings in dynamic languages are informational -- they belong in the WARN tier, not FAIL.

**Step 3: Verdict and next steps**

| Verdict | Next Step |
|---------|-----------|
| **PASS** | Proceed to /feature-validate |
| **WARN** | Review warnings. Proceed if warnings are intentional (unused imports for future use, etc.). Fix if unintentional. |
| **FAIL** | Route back to /feature-implement with specific wiring tasks. Do NOT proceed to validation. |

**Gate**: Report produced with verdict and actionable recommendations.

---

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| No source files found | Wrong scope path or empty project | Verify working directory, check scope parameter |
| Language not detected | No recognizable build files or source extensions | Specify language manually or check project structure |
| Too many exports to analyze | Large monorepo or library with thousands of exports | Narrow scope to changed files (use `git diff --name-only` against base branch) |
| False positive ORPHANED | Library code, plugin interfaces, or entry points | Check exclusion patterns. If legitimate public API, add to exclusions. |
| Circular import detected | Python circular imports or Go import cycles | Report as separate finding -- circular imports are integration issues themselves |
| No implementation artifact | Running in pipeline mode but implement phase didn't checkpoint | Fall back to standalone mode using git diff to identify changed files |

## References

- [Feature State Conventions](../_feature-shared/state-conventions.md)
- [ADR-078: Integration Checker](../../adr/078-integration-checker.md)
