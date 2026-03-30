# SAP CC Structural Domain

Structural and design review for SAP Converged Cloud Go repositories. Checks 9 categories at the type, API surface, and dependency level -- above syntax/idiom, below full architecture.

## Required Context Loading
Always load these before reviewing:
- `skills/go-sapcc-conventions/references/library-reference.md`
- `skills/go-sapcc-conventions/references/go-bits-philosophy-detailed.md`

## Voice
Directive review tone -- statements not suggestions. "Delete this" not "consider removing this."

## Default Tools
- MUST use gopls MCP tools when available: `go_workspace` at start, `go_file_context` after reading .go files, `go_symbol_references` to trace type usage, `go_diagnostics` after edits
- Fallback to grep if gopls unavailable

## The 9 Structural Categories

### Category 1: Type Export Decisions (HIGH)
Flag exported struct types that should be unexported because only their interface is used externally.

**Check**: "Is this type only used through an interface? If yes, unexport it."

```go
// FLAGGED: type FileBackingStore struct { ... }
// CORRECT: type fileBackingStore struct { ... }
```

### Category 2: Unnecessary Wrappers/Helpers (MEDIUM)
Functions wrapping a single stdlib/go-bits call without adding value.

**Checks**: Custom `go func()` wrappers when `wg.Go()` exists, custom `mustXxx` when `must.ReturnT` exists, manual row iteration when `sqlext.ForeachRow` exists, getter methods that just return a field.

**must vs assert**: `must.SucceedT` for setup/preconditions (fatal), `assert.ErrEqual` for testing operation results (non-fatal).

### Category 3: Option[T] Resolution Timing (HIGH)
Flag `Option[T]` fields that persist beyond parse/config phase into runtime structs.

**Convention**: Resolve Options at parse time, pass concrete values to core logic. `cfg.MaxFileSize.UnwrapOr(defaultValue)` at init, not in every method.

### Category 4: Dependency/Resource Management (HIGH/MEDIUM)
Creating separate pools when shared ones should be passed. Importing heavy packages when go-bits utilities exist.

**Convention**: Move utilities to internal to avoid transitive dep pollution.

### Category 5: Anti-Over-Engineering (MEDIUM/HIGH)
Throwaway struct types for simple JSON, manual error concatenation, custom test helpers duplicating go-bits, inference that won't scale, repository patterns wrapping direct DB access, option structs for constructors.

### Category 6: Forward-Compatible Naming (MEDIUM)
Names that block future siblings without renaming. `keppel test` should be `keppel test-driver storage`.

### Category 7: go-bits Library Usage (MEDIUM/HIGH)
Manual implementations of patterns go-bits provides. Cross-reference against library-reference.md.

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

### Category 8: Test Structure (HIGH/MEDIUM)
Missing `testWithEachTypeOf` when multiple implementations exist. Production code containing `MockXxx` types. `PedanticRegistry` in production (test-only). Integration tests using table-driven format instead of sequential narrative.

### Category 9: Contract Cohesion (MEDIUM/LOW)
Constants, error sentinels, and validation functions must live in the same file as their owning interface. Flag artifacts in `util.go` or `constants.go` that belong to a specific contract.

**Test**: If you can name which interface owns an artifact, it must live in the interface's file.

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
| "The wrapper adds readability" | Delete wrapper, use the call directly |
| "Option[T] in struct is clearer" | Resolve at parse time |
| "We might need the heavy dependency" | Use go-bits alternative |
| "Manual row iteration is more flexible" | Use sqlext.ForeachRow |
| "Tests work with one implementation" | testWithEachTypeOf for all implementations |
| "The constant is fine in util.go" | Move to the interface's file |

## Detailed References

For the complete category catalog with code examples and severity levels:
- [structural-categories.md](structural-categories.md) -- Full 9-category reference with examples

## Error Handling

- **No go.mod**: Ask "Where is the go.mod for this project?"
- **Not an sapcc repo**: Note go-bits-specific categories (2, 3, 7) may have reduced findings
- **Single implementation interface**: Check for pluggable.Registry or driver semantics before requiring testWithEachTypeOf
