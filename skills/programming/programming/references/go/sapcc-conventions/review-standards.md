# SAP CC Review Standards — Lead + Secondary

Two complementary review styles govern sapcc code review.

---

## Part 1: Lead Reviewer

**Style**: Directive — statements, not suggestions.
**Top themes**: Simplicity/anti-over-engineering (10/38 comments), API design (8), error handling (7).

### Rules (Synthesized from 21 Review Comments)

| # | Rule | One-Line Summary | Source |
|---|------|-----------------|--------|
| 1 | Simplicity over ceremony | Don't create throwaway struct types for one-off JSON marshaling. `fmt.Sprintf` + `json.Marshal`. | Comment 1 |
| 2 | Trust stdlib error messages | Don't re-wrap errors when `strconv`, constructors already provide good context. Use `must.Return()`. | Comments 5-6 |
| 3 | Use Cobra subcommands | Don't manually roll argument dispatch that Cobra handles. Change arg order if needed. | Comment 3 |
| 4 | CLI names: specific + extensible | `keppel test-driver storage`, not `keppel test`. Leave room for siblings. | Comment 2 |
| 5 | Explicit params over inference | When a known design change is coming, use explicit `--params <json>`, don't build smart inference. | Comment 4 |
| 6 | No hidden defaults for niche cases | If a default only applies to a subset, make the parameter required. | Comment 7 |
| 7 | Dismiss theoretical concerns | Key question: "Can you point to a concrete scenario where this fails?" If not, don't handle it. | Comments 8-10 |
| 8 | Use existing error utilities | `errext.ErrorSet` and `.Join()`, not manual string concatenation with trailing separators. | Comment 15 |
| 9 | Marshal structured data for errors | If you have `map[string]any`, `json.Marshal` it rather than manually formatting fields. | Comment 18 |
| 10 | Tests must verify behavior | Never silently remove assertions during refactoring. Counterintuitive results are red flags. | Comments 12-13 |
| 11 | Explain non-obvious test workarounds | Add comments when test setup diverges from production patterns. | Comment 16 |
| 12 | Documentation must stay qualified | When behavior changes conditionally, update docs to state the conditions. | Comment 11 |
| 13 | TODOs: what + starting-point link + why-not-now | Include all three, not just `// TODO: fix later`. | Comment 19 |
| 14 | Understand Go value semantics | Value receiver copies struct, but reference-type fields share data. | Comment 20 |
| 15 | Variable names must not mislead about consumers | Don't name script vars as if the application reads them. | Comment 21 |

### Verbatim Review Examples

**Comment 1 — Copilot suggestion overengineered** (`cmd/test/main.go`):
> "I agree in principle with Copilot, but I think their suggestion is overengineered."

```go
// Anti-pattern: creating struct types for one-off JSON
storageConfig = fmt.Sprintf(`{"type":"filesystem","params":{"path":%s}}`,
  must.Return(json.Marshal(filesystemPath)))
```

**Comment 5-6 — Trust strconv/constructor error messages** (`cmd/test/main.go`):
> "ParseUint is disciplined about providing good context in its input messages... So we can avoid boilerplate here."

```go
// Anti-pattern: redundant error wrapping when stdlib provides context
chunkNumber := must.Return(strconv.ParseUint(chunkNumberStr, 10, 32))
ad := must.Return(keppel.NewAuthDriver(cmd.Context(), authConfig, nil))
```

**Comment 8-10 — Dismiss theoretical concerns** (`cmd/test/storage.go`):
> "This is an irrelevant contrivance." (on defer-closing `io.NopCloser`)
> "I'm going to ignore this based purely on the fact that Copilot complains about `os.Stdout.Write()`, but not about the much more numerous instances of `fmt.Println`."

**Comment 15 — Use errext.ErrorSet** (`internal/client/auth_challenge.go`):
> "This produces an extra trailing `\"; \"` at the end. Please use `errext.ErrorSet` and then `errs.Join(\"; \")`."

**Comment 18 — Marshal structured data** (`internal/processor/manifests.go`):
> "I like that we're showing the same payload that is also relevant for the CEL expression, but I don't like that we're doing a bunch of manual footwork here... I suggest to just `json.Marshal()` that for the error message."

**Comment 19 — TODOs with context** (`internal/keppel/validation.go`):
> "Please add a TODO here that we should investigate how to declare the fields of `layers` correctly."

### Meta-Rules: How the Lead Reviewer Reviews

| # | Rule | Pattern |
|---|------|---------|
| M1 | Reads Copilot suggestions critically | Agrees with direction, proposes simpler 1-line alternative |
| M2 | Dismisses inconsistent AI suggestions | If tool flags X but not equivalent Y, concern is invalid |
| M3 | Thinks about forward compatibility | Names, params, and API shapes evaluated for extensibility |
| M4 | Values brevity when stdlib provides clarity | Removes wrappers that duplicate error info |
| M5 | Approves simple PRs quickly | Doesn't manufacture concerns. "Let's give it a shot." |
| M6 | Corrects technical misconceptions directly | "Incorrect. `d.Limits` is not overwritten..." |
| M7 | Pushes fixes when needed | Sometimes pushes commits directly to address concerns |

### Lead Reviewer Priority Summary

| Dimension | Position |
|-----------|----------|
| Complexity | Aggressively removes. "Irrelevant contrivance." |
| AI suggestions | Skeptical. Judges on merit. Often simplifies. |
| Error handling | Trust stdlib context. `must.Return()`. Less wrapping. |
| Testing | Tests MUST cover behavior. Never reduce coverage. |
| API surface | Plan extensibility. Immutable variables. |
| Go type system | Deep expertise. Cites spec. Understands value semantics. |
| Documentation | Qualified, precise. TODOs with context. Public methods need docstrings. |
| Dependencies | Minimize. Move utilities to `internal` to avoid transitive dep pollution. |

### go-bits Review Patterns (Cross-Repository)

- **API surface protection**: No global mutable variables. Use `func ForeachX[T](action func(any) T) []T` instead.
- **Dependency graph minimization**: Move functions to `internal` to avoid pulling transitive deps.
- **Correct technical reasoning**: "We cannot change DeepEqual to use `==`. Most types are not within the `comparable` interface."
- **Spec-faithful programming**: Handle ambiguous spec behavior by making both branches behave the same.
- **Status code range check**: `respondwith.CustomStatus` panics on non-error status codes (only 400-599).
- **Public API documentation**: Exported methods must have docstrings. Return `bool` not `string` when the type fits.
- **Test exhaustiveness**: "This should recurse through each request and response payload type."

### PRs with No Comments (Silent Approvals)

Simple, low-risk PRs get clean approvals: lint fixes, dependency bumps, codeowner updates, small bug fixes, config changes. Detailed review is reserved for new architecture, CLI commands, or API surfaces.

---

## Part 2: Secondary Reviewer

**Style**: Inquisitive — questions where lead review makes statements.
**Top themes**: Error handling/migration safety (4/18 comments), testing (4), code style (3).

### Rules (Synthesized from 18 Review Comments)

| # | Rule | One-Line Summary | Source |
|---|------|-----------------|--------|
| 1 | Error messages must be actionable | "Internal Server Error" is unacceptable when the cause is knowable. | Authored PR |
| 2 | Know the spec, deviate pragmatically | Reference RFCs, but deviate when spec is impractical. | Authored PR |
| 3 | Guard against panics with clear errors | Check nil/empty before indexing. `fmt.Errorf("invalid: %q", val)`. | Authored PR |
| 4 | Strict configuration parsing | `DisallowUnknownFields()` on JSON decoders for config. | Comment 13 |
| 5 | Test ALL combinations | When changing logic with multiple inputs, test every meaningful combination. | Authored PR |
| 6 | Eliminate redundant code | "This check is now redundant?" / "This is already done above." | Comments 2-4, 10 |
| 7 | Comments explain WHY | "That should probably be a comment" — request WHY when non-obvious. | Comment 9 |
| 8 | Domain knowledge over theory | "Rate limit is not on a sub second basis." | Comment 1 |
| 9 | Smallest possible fix | 2-line PRs are fine. Keep changes focused. | Authored PR |
| 10 | Respect ownership hierarchy | "LGTM but lets wait for lead review, we are in no hurry here." | Comment 5 |
| 11 | Be honest about mistakes | Acknowledge errors quickly, propose fix direction. | Comment 6 |
| 12 | Validate migration paths | "Do we somehow check if this is still set and then abort?" | Comments 11-12 |
| 13 | Formatting: use GitHub suggestion blocks | One-click apply for small changes. | Comment 7 |
| 14 | Prefer simple over overengineered | Accept simpler alternatives when valid. | Comment 8 |

### Secondary Reviewer's Authored PR Patterns

- **Defensive testing**: Edge cases (account names starting with `-`, reserved names), regex validation
- **Spec awareness + pragmatic deviation**: References RFC drafts, deviates when impractical
- **Minimal pragmatic fixes**: 2-line changes with one-sentence PR bodies
- **Domain logic simplification**: Changed merge priority so Unsupported no longer overrides actual severity
- **Real-world error handling**: `TestReplicationFailingFromHarbor`, `TestReplicationFailingFromGHCR`
- **User-facing error quality**: Before: "500 Internal Server Error". After: actionable error with URL and cause
- **Defensive nil checks**: `if len(pathParts) < 1` before index access with clear error messages

### Lead vs Secondary: Key Differences

| Dimension | Lead | Secondary |
|-----------|------|-----------|
| Review style | Directive statements | Inquisitive questions |
| Complexity | Aggressively removes | Adds defensive checks |
| AI suggestions | Skeptical, simplifies | More accepting |
| Error handling | Trust stdlib, less wrapping | Validate inputs, more wrapping |
| Testing | Tests MUST cover behavior | Tests should not be redundant |
| Defense in depth | Handle ambiguity silently | Make problems visible |
| Focus areas | Architecture, simplicity, API design | Migration safety, config, UX |
| Dismissal style | Principled ("irrelevant contrivance") | Domain-based ("not on sub-second basis") |

### Secondary Reviewer's Key Contributions

1. Error message quality — messages must be actionable, not just technically correct
2. Migration safety — removed env vars must still be validated
3. Configuration strictness — `DisallowUnknownFields()` catches typos
4. Real-world testing — test against actual production failure modes (Harbor, ghcr.io)
5. Spec awareness — reference RFCs, link magic numbers to specs
6. Defensive programming — guard against panics with clear errors
7. Small focused PRs — 2-line fixes are fine
8. Exhaustive combinations — when changing logic, test every meaningful input pair
