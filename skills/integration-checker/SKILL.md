---
name: integration-checker
description: |
  Verify cross-component wiring: exports are imported AND used, real data
  flows through connections, output shapes match input expectations. Use
  after /feature-implement, before /feature-validate, or standalone on any
  codebase. Use for "check integration", "verify wiring", "are components
  connected", "integration check", or "/integration-checker". Do NOT use
  for unit test failures, linting, or single-file correctness issues.
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

## Core Principle

**Existence does not equal integration.** A component existing is implementation-level verification; a component being connected is integration-level verification. Both are necessary. Neither is sufficient alone.

This skill catches the most common class of real-world bugs in AI-generated code: components that are individually correct but not connected to each other. A function can exist, contain real logic, pass correctness verification, and never be imported or called. An API endpoint can be defined but never wired into the router. An event handler can be registered but never receive events.

## Purpose

Verify cross-component wiring using four verification techniques. Phase 3.5 of the feature lifecycle (design -> plan -> implement -> **integration check** -> validate -> release).

When used standalone (not in the feature pipeline), operates on the current working directory or a specified path.

## Operator Context

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before execution
- **Read-Only Analysis**: This skill reads and reports. It does NOT fix wiring issues. Fixes route back to feature-implement or the user.
- **Language Detection First**: Detect project language(s) before applying verification techniques. Different languages have different import/export patterns.
- **Three-State Classification**: Every export gets exactly one status: WIRED, IMPORTED_NOT_USED, or ORPHANED. No ambiguous states.
- **Structural Not Semantic**: Contract checking verifies shape and naming compatibility, not whether data is logically correct. WHY: semantic correctness requires runtime information we don't have.

### Default Behaviors (ON unless disabled)
- **Concise Reporting**: Report facts. Show the wiring map, not prose about the wiring map.
- **Feature Pipeline Integration**: When invoked within the feature pipeline, read implementation artifact from `.feature/state/implement/` for context on what was built.
- **Exclusion Patterns**: Skip `node_modules/`, `vendor/`, `.git/`, `__pycache__/`, `dist/`, `build/`, test fixtures, and generated files. WHY: these contain intentionally unused exports (library code, vendored deps) that would flood the report with false positives.
- **Severity Ordering**: Report ORPHANED (failure) before IMPORTED_NOT_USED (warning) before WIRED (pass). Users need to see failures first.

### Optional Behaviors (OFF unless enabled)
- **Requirements Map**: When a task plan exists (`.feature/state/plan/`), produce per-requirement wiring status. Only available in feature pipeline context.
- **Verbose Mode**: Show WIRED components in addition to failures and warnings. Default only shows issues.

## What This Skill CAN Do
- Build export/import maps for Go, Python, TypeScript, and JavaScript projects
- Classify exports as WIRED, IMPORTED_NOT_USED, or ORPHANED
- Detect hardcoded empty data, placeholder values, and dead parameters flowing through wired connections
- Verify output shape compatibility between connected components
- Produce per-requirement wiring status when a task plan exists
- Operate standalone or as part of the feature pipeline

## What This Skill CANNOT Do
- Fix wiring issues (route to feature-implement or the user)
- Verify runtime behavior or semantic correctness
- Analyze dynamically-loaded modules, reflection-based wiring, or plugin architectures with certainty
- Replace integration tests (this is static analysis, not execution)
- **Reason**: This skill is static structural analysis. Runtime verification and fix application require different capabilities.

---

## Instructions

### Phase 0: PRIME

**Goal**: Establish context, detect language, identify scope.

**Step 1: Detect execution context**

Determine if running within the feature pipeline or standalone:
- **Pipeline**: Check for `.feature/state/implement/` artifact. If present, load it to understand what was built and scope the check to changed/added files.
- **Standalone**: Scope to the current working directory or user-specified path. Analyze all source files.

**Step 2: Detect project language(s)**

Identify language(s) from file extensions, build files, and project structure:

| Indicator | Language |
|-----------|----------|
| `go.mod`, `*.go` | Go |
| `pyproject.toml`, `setup.py`, `*.py` | Python |
| `tsconfig.json`, `*.ts`, `*.tsx` | TypeScript |
| `package.json`, `*.js`, `*.jsx` | JavaScript |

Multiple languages may coexist. Run all applicable techniques for each.

**Step 3: Identify language-specific patterns**

| Language | Export Pattern | Import Pattern | Common Integration Failures |
|----------|---------------|----------------|----------------------------|
| Go | Capitalized identifiers at package level | `import "path/to/pkg"` then `pkg.Name` | Exported function in wrong package; interface satisfied but never used via interface type; `init()` side effects not triggered because package not imported |
| Python | Module-level definitions, `__all__`, `__init__.py` re-exports | `from module import name`, `import module` | Circular imports causing silent failures; `__init__.py` missing re-export; relative vs absolute import mismatch |
| TypeScript | `export`, `export default`, barrel files (`index.ts`) | `import { name } from './module'` | Barrel file missing re-export; type-only import where value import needed; path alias not resolving |
| JavaScript | `module.exports`, `export`, `export default` | `require()`, `import` | CommonJS/ESM mismatch; default vs named export confusion |

**Gate**: Language(s) detected. Scope established. Proceed to Phase 1.

---

### Phase 1: EXPORT/IMPORT MAP

**Goal**: For every export in scope, determine its wiring status: WIRED, IMPORTED_NOT_USED, or ORPHANED.

**Step 1: Discover exports**

Scan source files for exported symbols. Be language-aware:

- **Go**: Find all capitalized function, type, const, and var declarations at package level. Include method receivers on exported types.
- **Python**: Find all module-level function/class/variable definitions. Check `__all__` if present (it restricts the public API). Check `__init__.py` for re-exports.
- **TypeScript/JavaScript**: Find all `export` declarations, `export default`, and barrel file re-exports.

Record each export as: `{file, name, kind (function/type/const/var), line}`.

**Step 2: Discover imports and usages**

For each export found, search the codebase for:
1. **Import**: The symbol is imported (appears in an import statement referencing the exporting module)
2. **Usage**: The imported symbol is actually used (called, referenced, assigned, passed as argument) beyond the import statement itself

This two-step check is critical. WHY: An import without usage is IMPORTED_NOT_USED, which is a distinct failure mode from ORPHANED. It signals someone intended to use the component but didn't finish wiring it.

**Step 3: Classify each export**

| Condition | Status | Severity |
|-----------|--------|----------|
| Exported, imported, AND used in at least one consumer | **WIRED** | Pass |
| Exported and imported, but never used beyond the import statement | **IMPORTED_NOT_USED** | Warning |
| Exported but never imported anywhere in the project | **ORPHANED** | Failure |

**Exclusions** (do not flag as ORPHANED):
- `main()` functions and entry points
- Interface implementations that satisfy an interface (Go)
- Test helpers exported for use by `_test.go` files in other packages
- Symbols listed in public API documentation or `__all__` in library packages
- CLI command handlers wired via registration (e.g., cobra commands, click groups)
- Exports in files matching exclusion patterns (vendor, node_modules, etc.)

**Step 4: Build the export/import map**

Produce a structured map:

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

**Goal**: For WIRED components, verify that real data flows through the connections and that output shapes match input expectations.

This phase checks two things simultaneously because they both operate on the same set of WIRED connections identified in Phase 1.

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

**Important context**: Contract checking is approximate in dynamic languages. Report findings with appropriate confidence:
- **High confidence**: Explicit type annotations match/mismatch, struct/interface definitions
- **Medium confidence**: Inferred from usage patterns, variable names, JSDoc/docstrings
- **Low confidence**: Dynamic access patterns, computed property names, reflection

**Gate**: Data flow and contract findings recorded. Proceed to Phase 3.

---

### Phase 3: REPORT

**Goal**: Produce a structured integration report with actionable findings.

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
| Circular import detected | Python circular imports or Go import cycles | Report as separate finding — circular imports are integration issues themselves |
| No implementation artifact | Running in pipeline mode but implement phase didn't checkpoint | Fall back to standalone mode using git diff to identify changed files |

## Anti-Patterns

| Anti-Pattern | Why Wrong | Do Instead |
|--------------|-----------|------------|
| Checking only that imports exist | Import without usage is a distinct failure mode (IMPORTED_NOT_USED) | Verify import AND usage for each export |
| Treating all ORPHANED as bugs | Library code, plugin interfaces, and entry points are intentionally not imported internally | Apply exclusion patterns before flagging |
| Skipping data flow check because wiring exists | A component wired to always receive empty data is functionally disconnected | Check data flow for every WIRED connection |
| Running on entire monorepo in pipeline mode | Wastes time analyzing unchanged code | Scope to files changed since implementation started |
| Auto-fixing wiring issues | Integration fixes often require design decisions (which component should call which?) | Report issues, let human or feature-implement decide the fix |
| Treating low-confidence contract findings as failures | Dynamic language contract checking is approximate without runtime types | Report confidence level, only FAIL on high-confidence mismatches |

## Anti-Rationalization

| Rationalization Attempt | Why It's Wrong | Required Action |
|------------------------|----------------|-----------------|
| "The component exists and has real logic, so it's integrated" | Existence is not integration. A function that's never called is dead code. | Check import AND usage, not just existence |
| "It's imported, so it must be used" | Unused imports are a specific failure mode — someone started wiring but didn't finish | Verify the import is followed by actual usage |
| "The wiring looks right so data must flow" | Wiring to an empty array is functionally the same as no wiring | Trace actual data through each connection |
| "Contract checking is too hard in dynamic languages" | Approximate checking still catches obvious mismatches | Check what you can, report confidence levels |
| "These ORPHANED exports are for future use" | Future use is not current integration. Flag them now, exclude intentionally if confirmed. | Report all ORPHANED, let the user decide which are intentional |
| "Integration checking is overkill for a small change" | Small changes are where wiring gets forgotten — new function added but never called | Run the check. Scope narrows automatically for small changes. |

## References

- [Feature State Conventions](../_feature-shared/state-conventions.md)
- [Gate Enforcement](../shared-patterns/gate-enforcement.md)
- [Anti-Rationalization Core](../shared-patterns/anti-rationalization-core.md)
- [ADR-078: Integration Checker](../../adr/078-integration-checker.md)
