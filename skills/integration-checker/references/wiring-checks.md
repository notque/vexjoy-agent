# Integration Checker Wiring Reference

Detailed patterns for language detection, export/import classification, and data flow analysis used across Phases 0-2.

---

## Language Detection Indicators

| Indicator | Language |
|-----------|----------|
| `go.mod`, `*.go` | Go |
| `pyproject.toml`, `setup.py`, `*.py` | Python |
| `tsconfig.json`, `*.ts`, `*.tsx` | TypeScript |
| `package.json`, `*.js`, `*.jsx` | JavaScript |

Multiple languages may coexist. Run all applicable techniques for each.

---

## Language-Specific Export/Import Patterns

| Language | Export Pattern | Import Pattern | Common Integration Failures |
|----------|---------------|----------------|----------------------------|
| Go | Capitalized identifiers at package level | `import "path/to/pkg"` then `pkg.Name` | Exported function in wrong package; interface satisfied but never used via interface type; `init()` side effects not triggered because package not imported |
| Python | Module-level definitions, `__all__`, `__init__.py` re-exports | `from module import name`, `import module` | Circular imports causing silent failures; `__init__.py` missing re-export; relative vs absolute import mismatch |
| TypeScript | `export`, `export default`, barrel files (`index.ts`) | `import { name } from './module'` | Barrel file missing re-export; type-only import where value import needed; path alias not resolving |
| JavaScript | `module.exports`, `export`, `export default` | `require()`, `import` | CommonJS/ESM mismatch; default vs named export confusion |

---

## Export Classification Rules

Every export gets exactly one of three states -- no ambiguous classifications.

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

**Skip during discovery**: `node_modules/`, `vendor/`, `.git/`, `__pycache__/`, `dist/`, `build/`, test fixtures, and generated files.

---

## Data Flow Failure Patterns

For each WIRED connection, check whether real data actually reaches the component.

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

---

## Contract Mismatch Patterns

For each WIRED connection where component A's output feeds into component B's input:

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

**Confidence levels for dynamic languages:**
- **High confidence**: Explicit type annotations match/mismatch, struct/interface definitions
- **Medium confidence**: Inferred from usage patterns, variable names, JSDoc/docstrings
- **Low confidence**: Dynamic access patterns, computed property names, reflection

Note: dynamically-loaded modules, reflection-based wiring, and plugin architectures cannot be analyzed with certainty through static analysis. Flag what is visible and note the limitation.

---

## Requirements Integration Map Format (Pipeline Mode Only)

| Status | Meaning |
|--------|---------|
| **WIRED** | Requirement has a complete integration path from entry point to implementation |
| **PARTIAL** | Some components exist but the path has gaps (identify the gaps) |
| **UNWIRED** | Components may exist but no integration path connects them |

Example:
```
| Requirement | Status | Integration Path |
|-------------|--------|-----------------|
| User can delete account | WIRED | DELETE /api/users/:id -> routes/api.go -> handlers.HandleUserDelete -> db.DeleteUser |
| Email notification on delete | PARTIAL | handlers.HandleUserDelete -> [GAP] -> email.SendNotification (exists but not called from handler) |
| Audit log on delete | UNWIRED | audit.LogEvent exists, but no call from any delete path |
```
