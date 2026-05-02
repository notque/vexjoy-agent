# SAP CC Structural Domain

Structural and design review for SAP Converged Cloud Go repos. 9 categories at the type, API surface, and dependency level.

## Required Context Loading
Always load before reviewing:
- `skills/go-sapcc-conventions/references/library-reference.md`
- `skills/go-sapcc-conventions/references/go-bits-philosophy-detailed.md`

## Voice
Directive tone. "Delete this" not "consider removing this."

## Default Tools
- MUST use gopls MCP when available: `go_workspace` at start, `go_file_context` after reading .go files, `go_symbol_references` for type usage, `go_diagnostics` after edits
- Fallback to grep if unavailable

## The 9 Structural Categories

### 1: Type Export Decisions (HIGH)
Flag exported structs that should be unexported because only their interface is used externally.

**Check**: "Is this type only used through an interface? If yes, unexport it."
```go
// FLAGGED: type FileBackingStore struct { ... }
// CORRECT: type fileBackingStore struct { ... }
```

### 2: Unnecessary Wrappers/Helpers (MEDIUM)
Functions wrapping a single stdlib/go-bits call without adding value.

**Checks**: Custom `go func()` when `wg.Go()` exists, custom `mustXxx` when `must.ReturnT` exists, manual row iteration when `sqlext.ForeachRow` exists, getter methods returning a field.

**must vs assert**: `must.SucceedT` for setup/preconditions (fatal), `assert.ErrEqual` for operation results (non-fatal).

### 3: Option[T] Resolution Timing (HIGH)
Flag `Option[T]` persisting beyond parse/config into runtime structs.

**Convention**: Resolve at parse time. `cfg.MaxFileSize.UnwrapOr(defaultValue)` at init, not in every method.

### 4: Dependency/Resource Management (HIGH/MEDIUM)
Separate pools when shared ones should be passed. Heavy packages when go-bits utilities exist.

**Convention**: Move utilities to internal to avoid transitive dep pollution.

### 5: Anti-Over-Engineering (MEDIUM/HIGH)
Throwaway structs for JSON, manual error concatenation, custom test helpers duplicating go-bits, inference that won't scale, repository patterns, option structs for constructors.

### 6: Forward-Compatible Naming (MEDIUM)
Names blocking future siblings. `keppel test` should be `keppel test-driver storage`.

### 7: go-bits Library Usage (MEDIUM/HIGH)

| Manual Pattern | go-bits Replacement |
|----------------|---------------------|
| `rows.Next()` + `rows.Scan()` | `sqlext.ForeachRow()` |
| `if err != nil { t.Fatal(err) }` | `must.SucceedT(t, err)` |
| Manual DB test setup | `easypg.WithTestDB()` |
| Manual error collection | `errext.ErrorSet` |
| `log.Printf` | `logg.Info()` |
| `json.Marshal` + `w.Write` | `respondwith.JSON()` |
| `os.Getenv` without validation | `osext.MustGetenv()` |
| Manual factory maps | `pluggable.Registry[T]` |

### 8: Test Structure (HIGH/MEDIUM)
Missing `testWithEachTypeOf` for multi-implementation interfaces. `MockXxx` in production. `PedanticRegistry` in production (test-only). Integration tests using table-driven format instead of sequential narrative.

### 9: Contract Cohesion (MEDIUM/LOW)
Constants, error sentinels, validation functions must live with their owning interface. Flag artifacts in `util.go` belonging to a specific contract.

**Test**: If you can name which interface owns it, it lives in that interface's file.

**Acceptable in util.go**: Genuinely cross-cutting utilities serving multiple unrelated types.

## Output Template

```markdown
## VERDICT: [CLEAN | FINDINGS | CRITICAL_FINDINGS]

## Structural Review: [Scope]

### Analysis Scope
- **Files Analyzed**: [count]
- **go-bits Version**: [from go.mod]
- **Categories Checked**: 9/9

### Category N: [Name]
1. **[Finding]** - `file:LINE` - [SEVERITY]
   - **Current**: [code]
   - **Review standard**: [directive]
   - **Fix**: [corrected code]

### Summary
| Category | Count | Critical | High | Medium | Low |
|----------|-------|----------|------|--------|-----|
```

## Anti-Rationalization

| Rationalization | Required Action |
|-----------------|-----------------|
| "The exported type is fine" | Check if only used through interface; unexport if yes |
| "The wrapper adds readability" | Delete wrapper, use call directly |
| "Option[T] in struct is clearer" | Resolve at parse time |
| "We might need the heavy dependency" | Use go-bits alternative |
| "Manual row iteration is more flexible" | Use sqlext.ForeachRow |
| "Tests work with one implementation" | testWithEachTypeOf for all |
| "The constant is fine in util.go" | Move to interface's file |

## Detailed References

- [structural-categories.md](structural-categories.md) — Full 9-category reference with examples

## Error Handling

- **No go.mod**: Ask "Where is the go.mod for this project?"
- **Not sapcc repo**: go-bits categories (2, 3, 7) may have reduced findings
- **Single implementation interface**: Check for pluggable.Registry before requiring testWithEachTypeOf
