# Phase 2: DISPATCH — Agent Dispatch Prompts

> **Load when**: Phase 2 (DISPATCH) begins, after Phase 1 segmentation is complete.
> **Purpose**: Per-domain agent dispatch prompts for parallel package review.

---

## Dispatch Principles

- **Read the actual code.** Agents MUST use the Read tool to read every .go file in their assigned packages. Read every file directly rather than guessing from names or grep output.
- **Use gopls MCP tools when available**: `go_workspace` to detect workspace structure, `go_file_context` after reading each .go file for intra-package dependency understanding, `go_symbol_references` to verify type usage across packages (critical for export decisions), `go_package_api` to inspect package APIs, `go_diagnostics` to verify any fixes.
- **Real review, not checklists.** The primary question for every function is: "Would this pass review?" not "does it follow a checklist." A real reviewer reads code holistically and reacts to architectural issues, not just mechanical patterns.
- **Segment by package, not by concern.** Dispatch agents by package groups, NOT by concern area. Each agent reviews its packages holistically (errors + architecture + patterns + tests together), exactly like a real PR review.
- **Code-level findings only.** Every finding MUST include the actual code snippet and a concrete fix showing what it should become.

---

## Standard Dispatch Prompt

Use this prompt verbatim for each dispatched agent, substituting `[list of packages with full paths]`:

```
You are reviewing code in an SAP Converged Cloud Go project against established
review standards. Your job is to find things that would actually be commented on
or rejected in a PR.

PACKAGES TO REVIEW: [list of packages with full paths]

Read EVERY .go file in these packages using the Read tool. For each file:

1. **Over-engineering** (Lead Reviewer's #1 Concern)
   - Interfaces with only one implementation? → "Just use the concrete type." Project convention: only create interfaces when there are 2+ real implementations.
   - Wrapper function that adds nothing? → "Delete this, call the real function"
   - Struct for one-time JSON? → "Use fmt.Sprintf + json.Marshal" (per project convention)
   - Option struct for constructor? → "Just use positional params." Project convention uses 7-8 positional params, always positional params.
   - Config file/viper? → "Use osext.MustGetenv." Project convention uses environment variables exclusively. Pure env vars only.

2. **Dead code**
   - Exported functions with no callers outside the package? Use Grep to check: `grep -r "FunctionName" --include="*.go"`. If no callers exist, flag it.
   - Interface methods unused
   - Fields set but unread
   - Entire packages imported but barely used
   - "TODO: remove" comments on code that should already be gone

3. **Error messages** (Secondary Reviewer's #1 Concern)
   - `http.Error(w, "internal error", 500)` — useless to the caller
   - Error wrapping: uses %w when caller needs errors.Is/As, %s with .Error() to intentionally break chain
   - Message format: "cannot <operation>: %w" or "while <operation>: %w" with relevant identifiers
   - Would a user/operator reading this know what to do?
   - "internal error" with no context = CRITICAL
   - Return the primary error; log secondary/cleanup errors. Primary error returned, secondary/cleanup errors logged.

4. **Constructor patterns**
   - Constructor should be `NewX(deps...) *X` — returns infallibly (no error) (construction is infallible)
   - Uses positional struct literal init: `&API{cfg, ad, fd, sd, ...}` (no field names)
   - Injects default functions for test doubles: `time.Now`, etc.
   - Override pattern for test doubles: fluent `OverrideTimeNow(fn) *T` methods

5. **Interface contracts**
   - If the package implements an interface from another package: Read the interface definition
   - Check if the implementation actually satisfies the contract
   - Does it return correct error types? Default values where errors are expected?
   - Interfaces should be defined in the consumer package, not the implementation package

6. **Copy-paste structs**
   - Two structs with the same fields (one for internal, one for API response)?
   - Handler functions that are 90% identical (extract the common pattern)
   - Duplicated validation logic

7. **HTTP handler patterns** (Must match keppel patterns)
   - Handlers: methods on *API with `handleVerbResource(w, r)` signature
   - Auth: called inline at top of handler, NOT middleware
   - JSON decode: `json.NewDecoder` + `DisallowUnknownFields()`
   - Responses: `respondwith.JSON(w, status, map[string]any{"key": val})`
   - Internal errors: `respondwith.ObfuscatedErrorText(w, err)` — hides 500s from clients
   - Route registration: one `AddTo(*mux.Router)` per API domain, composed via `httpapi.Compose`

8. **Database patterns**
   - SQL queries as package-level `var` with `sqlext.SimplifyWhitespace()`
   - PostgreSQL `$1, $2` params (always `$1, $2` (PostgreSQL syntax))
   - gorp for simple CRUD, raw SQL for complex queries
   - Transactions: `db.Begin()` + `defer sqlext.RollbackUnlessCommitted(tx)`
   - NULL: `Option[T]` (from majewsky/gg/option), not `*T` pointers

9. **Type patterns**
   - Named string types for domain concepts: `type AccountName string`
   - String enums with typed constants (NOT iota): `const CleanSeverity VulnerabilityStatus = "Clean"`
   - Model types use `db:"column"` tags; API types use `json:"field"` tags — separate types
   - Pointer receivers for all struct methods (value receivers only for tiny data-only types)

10. **Logging patterns**
    - `logg.Fatal` ONLY in cmd/ packages for startup failures
    - `logg.Error` for secondary/cleanup errors (only for secondary/cleanup errors)
    - `logg.Info` for operational events
    - Use logg package for all logging
    - Panics only for impossible states, annotated with "why was this not caught by Validate!?"

11. **Mixed approaches** (Pattern consistency)
    - Some handlers return JSON errors, others return text/plain
    - Some constructors panic on nil args, others return errors
    - Some packages use logg, others use log

For EACH finding, output:

### [MUST-FIX / SHOULD-FIX / NIT]: [One-line summary]
**File**: `path/to/file.go:LINE`
**Convention**: "[What a lead reviewer would actually write in a PR comment]"

**Current code**:
```go
[actual code from the file, 3-10 lines]
```

**Should be**:
```go
[what the code should look like after fixing]
```

**Why**: [One sentence explaining the principle]

---

SEVERITY GUIDE:
- MUST-FIX: Would block the PR (data loss, interface violation, wrong behavior)
- SHOULD-FIX: Would get a strong review comment (dead code, copy-paste, bad errors)
- NIT: Would get a comment but not block (style, naming, minor simplification)

Skip:
- Generic Go best practices (t.Parallel, DisallowUnknownFields, context.Context first)
- Things that are actually fine but could theoretically be "better"
- Suggestions that add complexity without clear benefit

Focus on:
- Real over-engineering (lead reviewer's #1 concern)
- Actually useless error messages (secondary reviewer's #1 concern)
- Dead code that should be deleted
- Interface contract bugs
- Constructor/config patterns that diverge from keppel patterns
- Inconsistent patterns within the same repo
```

---

## Dispatch Instruction

**Dispatch all agents in a single message using the Task tool with `subagent_type=golang-general-engineer`.**

Gate: All agents dispatched. Proceed to Phase 3.
