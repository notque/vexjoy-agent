# Lead Reviewer — Detailed Review Rules

Extended rules with ALL 21 review comments verbatim, every file path, the 7 meta-rules about review style, and BAD/GOOD examples. Extracted from sapcc/keppel and sapcc/go-bits code reviews.

---

## Review Statistics

- **Total review comments**: ~38 (61% of all comments)
- **Top theme**: Simplicity / anti-over-engineering (10 comments)
- **Second theme**: API design (8 comments)
- **Third theme**: Error handling (7 comments)
- **Review style**: Directive -- makes statements, not suggestions
- **Sentiment**: Suggestions (14) + complaints (8) dominate
- **PRs with no comments**: 16 out of 25 keppel PRs got clean approvals or no review

---

## All 21 Review Comments (Verbatim)

### Comment 1: Copilot's suggestion is overengineered
- **File**: `cmd/test/main.go`
- **Category**: OVER-ENGINEERING / SIMPLICITY

Copilot suggested creating full struct types (`fsParams`, `fsConfig`) with JSON tags to safely marshal a filesystem config.

> "I agree in principle with Copilot, but I think their suggestion is overengineered. Alternative suggestion:
>
> ```go
> storageConfig = fmt.Sprintf(`{"type":"filesystem","params":{"path":%s}}`,
>   must.Return(json.Marshal(filesystemPath)))
> ```"

---

### Comment 2: Command naming must be forward-thinking
- **File**: `cmd/test/main.go`
- **Category**: CLI-DESIGN / API-DESIGN

> "This sets up the `keppel test` command to only ever test StorageDriver functions. I would like to allow for test harnesses of other drivers to be added later without having to move command names around. So this should be something like `keppel test storage`, so that e.g. we could have `keppel test federation` later for FederationDriver testing."
>
> "Also, `keppel test` is really vague. Please use `keppel test-driver`. In total, `keppel test-driver storage <driver> <method> <args...>`."

---

### Comment 3: Use Cobra subcommands, not manual dispatch
- **File**: `cmd/test/main.go`
- **Category**: CLI-DESIGN / CODE-STYLE

> "I don't like that we're manually rolling structure that usually would be represented as Cobra subcommands instead. If this was done because the driver name argument in `keppel test <driver> <operation> ...` makes it impossible to represent as subcommands, I would rather the argument order be changed to allow `<operation>` to be a `*cobra.Command`."
>
> "The discussion about where to place the driver name ties into my next note."

---

### Comment 4: Don't infer config that won't scale
- **File**: `cmd/test/main.go`
- **Category**: API-DESIGN / OVER-ENGINEERING

> "I appreciate the logic behind inferring storage driver params automatically, based on the chosen storage driver. But this will not scale beyond next month. I intend to add a multi-backend storage driver that can be configured to wrap around any number of other storage drivers..."
>
> "This `multi` storage driver will not allow predicting the storage driver params in any meaningful way, so we will need to allow providing params directly. I suggest recognizing `--driver <name> --params <json>`."
>
> "Please leave the logic to derive AuthDriver type and params as is for now. We will also need to rework that _somehow_ with the `multi` StorageDriver usecase, but I will delay the decision on how until then."

---

### Comment 5: Trust the stdlib's error messages (constructors)
- **File**: `cmd/test/main.go`
- **Category**: ERROR-HANDLING / SIMPLICITY

> "NewAuthDriver and NewStorageDriver already say 'could not initialize {driverType}' or such in their error messages, so this can be shortened:
> ```go
> ad := must.Return(keppel.NewAuthDriver(cmd.Context(), authConfig, nil))
> sd := must.Return(keppel.NewStorageDriver(storageConfig, ad, cfg))
> ```"

```go
// BAD: Redundant error context
ad, err := keppel.NewAuthDriver(cmd.Context(), authConfig, nil)
if err != nil {
    logg.Fatal("while setting up auth driver: %s", err.Error())
}

// GOOD: stdlib already provides context
ad := must.Return(keppel.NewAuthDriver(cmd.Context(), authConfig, nil))
```

---

### Comment 6: Trust strconv error messages
- **File**: `cmd/test/main.go`
- **Category**: ERROR-HANDLING / SIMPLICITY

> "ParseUint is disciplined about providing good context in its input messages:
> ```
> _, err := strconv.ParseUint("hello", 10, 64)
> fmt.Println(err.Error()) // prints: strconv.ParseUint: parsing "hello": invalid syntax
> ```
> So we can avoid boilerplate here without compromising that much clarity in the error messages:
> ```go
> chunkNumber := must.Return(strconv.ParseUint(chunkNumberStr, 10, 32))
> ```
> Same for every other number-shaped argument being parsed in this file."

```go
// BAD: Wrapping adds noise
val, err := strconv.ParseUint(chunkNumberStr, 10, 32)
if err != nil {
    return fmt.Errorf("failed to parse chunk number %q: %w", chunkNumberStr, err)
}

// GOOD: strconv says "strconv.ParseUint: parsing \"hello\": invalid syntax"
chunkNumber := must.Return(strconv.ParseUint(chunkNumberStr, 10, 32))
```

---

### Comment 7: No hidden defaults for niche use cases
- **File**: `cmd/test/main.go`
- **Category**: CLI-DESIGN / SIMPLICITY

> "This is, in effect, a default value that only applies to two specific storage drivers. These are not widely used enough to justify the undocumented quirk, so I would rather have `--account-name` and `--account-auth-tenant-id` be required always."

---

### Comment 8: Dismiss impractical concerns (repo root)
- **File**: `cmd/test/storage.go`
- **Category**: PRACTICAL-VS-THEORETICAL

Copilot flagged that hardcoding `cmd/test/policy.json` assumes running from repo root.

> "There is no practical reason to run this outside the repo root. All the alternatives are significant complications that are not worth it."

---

### Comment 9: Dismiss irrelevant contract compliance
- **File**: `cmd/test/storage.go`
- **Category**: PRACTICAL-VS-THEORETICAL / OVER-ENGINEERING

Copilot suggested closing an `io.NopCloser` to honor the ownership contract.

> "This is an irrelevant contrivance. Either `WriteTrivyReport` does it, or the operation fails and we fatal-error out, in which case it does not matter anyway."

---

### Comment 10: Dismiss stdout write error handling
- **File**: `cmd/test/storage.go`
- **Category**: PRACTICAL-VS-THEORETICAL

> "I'm going to ignore this based purely on the fact that Copilot complains about `os.Stdout.Write()`, but not about the much more numerous instances of `fmt.Println` that theoretically suffer the same problem. It is a theoretical concern, but I cannot recall when I last saw writes to stdout fail in practice."

---

### Comment 11: Documentation must be qualified correctly
- **File**: `docs/drivers/storage-swift.md`
- **Category**: DOCUMENTATION

> "This sentence now needs to be qualified. If `use_service_user_project` is true, then the service user instead only needs full write permissions on the project scope of the provided credentials (in standard Swift, this corresponds to the `swiftoperator` role)."

Review-level: _"Hah, this turned out much easier than expected. :) Only a documentation concern:"_

---

### Comment 12: Tests must verify behavior
- **File**: `internal/tasks/manifests_test.go`
- **Category**: TESTING

> "This must be reverted. We must test that `vuln_status_changed_at` works. Same on the other test."

---

### Comment 13: Question counterintuitive test results
- **File**: `internal/tasks/manifests_test.go`
- **Category**: TESTING

> "Why are more images going into status `Unsupported` here? Should this change not have the opposite effect?"

---

### Comment 14: Use proper test assertion patterns
- **File**: `internal/api/registry/replication_test.go`
- **Category**: TESTING / CODE-STYLE

Convention: Use ExpectHeader map for checking response headers:

> ```go
> ExpectHeader: map[string]string{
>     test.VersionHeaderKey: test.VersionHeaderValue,
>     // even though we return 401, no Www-Authenticate header shall be rendered
>     // because would be futile for the user performing this request to authenticate
>     "Www-Authenticate": "",
> },
> ```

---

### Comment 15: Use existing error utilities
- **File**: `internal/client/auth_challenge.go`
- **Category**: CODE-STYLE / ERROR-HANDLING

> "This produces an extra trailing `\"; \"` at the end. Please use `errext.ErrorSet` and then `errs.Join(\"; \")`."

```go
// BAD: manual concatenation with trailing separator
result := ""
for _, e := range errs {
    result += e.Error() + "; "
}

// GOOD: use existing utility
errs := errext.ErrorSet{}
// ... collect errors ...
return errs.Join("; ")
```

---

### Comment 16: Explain non-obvious test setup
- **File**: `internal/client/upload.go`
- **Category**: TESTING / DOCUMENTATION

The lead reviewer left an explanatory comment in the code itself:

> "This header must now be added manually because the testcase does not go through a real HTTP server (where it would normally be added automatically)."

---

### Comment 17: Code is moved, not deleted
- **File**: `internal/processor/manifests.go`
- **Category**: CODE-STYLE

A reviewer asked "This check is now redundant?" The lead reviewer clarified:

> "No, it's moved down to the last line of the green diff."

---

### Comment 18: Don't manually duplicate what can be marshaled
- **File**: `internal/processor/manifests.go`
- **Category**: SIMPLICITY / CODE-STYLE

> "I like that we're showing the same payload that is also relevant for the CEL expression, but I don't like that we're doing a bunch of manual footwork here, that will require updates whenever we add new expressions. Since we're compiling a `map[string]any` to give to `prg.Eval()`, I suggest to just `json.Marshal()` that for the error message."

```go
// BAD: manual field extraction (needs updating when fields change)
fmt.Sprintf("mediaType=%s, layers=%d", mt, len(layers))

// GOOD: marshal what you already have
payload, _ := json.Marshal(evalInput)
return fmt.Errorf("validation failed for payload: %s", payload)
```

---

### Comment 19: TODOs with context for library quirks
- **File**: `internal/keppel/validation.go`
- **Category**: DOCUMENTATION / CODE-STYLE

> "Please add a TODO here that we should investigate how to declare the fields of `layers` correctly. https://pkg.go.dev/github.com/google/cel-go@v0.26.1/common/types#NewObjectType appears to be the way to do it, but apparently they really hate everyone who does not use protobuf for all type declarations."

A TODO must include:
1. What needs to be done
2. A link or pointer to relevant API/docs
3. Why it wasn't done now

---

### Comment 20: Correct misconceptions about Go value semantics
- **File**: `internal/drivers/basic/ratelimit.go`
- **Category**: CODE-STYLE / ERROR-HANDLING

A reviewer said changes would be lost because the function takes a value receiver.

> "> This won't work correctly because the changes will be lost when the function returns."
>
> "Incorrect. `d.Limits` is not overwritten, we only access its payload, so copy-by-value on `d` is copy-by-reference on `d.Limits`."

Also:
> "Related to the incorrect reasoning above."

---

### Comment 21: Don't create false impressions in config
- **File**: `conformance-test/env.sh`
- **Category**: CODE-STYLE / DOCUMENTATION

A reviewer asked "Why not export?" The lead reviewer declined:

> "Because I don't want to create the impression that Keppel reads this variable. This is only used to DRY the shell script."

---

## Rules (Synthesized from Comments)

### Rule 1: SIMPLICITY OVER CEREMONY

Don't create throwaway struct types to marshal simple JSON. Use `fmt.Sprintf` with `json.Marshal` for dynamic parts. (Comment 1)

### Rule 2: TRUST THE STDLIB'S ERROR MESSAGES

Don't add error context that the called function already provides. If `strconv.ParseUint` or a well-designed constructor already includes the function name, input, and error type, use `must.Return()` and let stdlib speak for itself. (Comments 5-6)

### Rule 3: USE COBRA SUBCOMMANDS, NOT MANUAL DISPATCH

If you're parsing argument names in a switch statement, you should be using Cobra subcommands. If ordering prevents this, change the argument order. (Comment 3)

### Rule 4: CLI NAMES MUST BE SPECIFIC AND EXTENSIBLE

Command names must clearly describe what they do and leave room for siblings without renaming. `keppel test` -> `keppel test-driver storage`. (Comment 2)

### Rule 5: DON'T BUILD INFERENCE THAT WON'T SCALE

When a known design change is coming, don't build "smart" inference that will break. Use explicit parameters. But don't preemptively solve the future problem either. (Comment 4)

### Rule 6: NO HIDDEN DEFAULTS FOR NICHE CASES

If a default only applies to a subset, don't add it. Make the parameter required. Undocumented quirks are worse than explicit requirements. (Comment 7)

### Rule 7: DISMISS THEORETICAL CONCERNS

If a concern has no practical scenario, dismiss it. Apply error handling consistently. Key question: "Can you point to a concrete scenario where this fails?" (Comments 8-10)

### Rule 8: USE EXISTING ERROR UTILITIES

Don't build error strings with manual loops and separators. Use `errext.ErrorSet` and `Join()`. (Comment 15)

### Rule 9: MARSHAL STRUCTURED DATA FOR ERROR MESSAGES

If you already have a `map[string]any`, marshal it for error output rather than manually formatting each field. (Comment 18)

### Rule 10: TESTS MUST VERIFY BEHAVIOR, NOT SKIP IT

Never silently remove test assertions when refactoring. If a change produces counterintuitive results, that's a red flag. (Comments 12-13)

### Rule 11: EXPLAIN NON-OBVIOUS TEST WORKAROUNDS

When test setup requires something that wouldn't exist in production, add a comment explaining why. (Comment 16)

### Rule 12: DOCUMENTATION MUST STAY QUALIFIED

When adding features that change behavior under conditions, update docs to state those conditions. (Comment 11)

### Rule 13: TODOs MUST INCLUDE CONTEXT AND STARTING POINTS

Include: (1) what needs to be done, (2) a link to relevant API, (3) why it wasn't done now. (Comment 19)

### Rule 14: UNDERSTAND GO VALUE SEMANTICS DEEPLY

Value receivers copy the struct, but reference-type fields (slices, maps, pointers) still share underlying data. (Comment 20)

### Rule 15: VARIABLE NAMES MUST NOT MISLEAD ABOUT CONSUMERS

Don't name variables in a way that implies the application reads them if they're only for script-level DRY. (Comment 21)

---

## Meta-Rules: How the Lead Reviewer Reviews

### M1: Reads Copilot/bot suggestions critically
Agrees with the principle, proposes simpler alternatives. The lead reviewer repeatedly acknowledges Copilot's direction but then provides a 1-line fix where Copilot proposed 10 lines.

### M2: Dismisses inconsistent automated suggestions
If Copilot flags X but not equivalent Y, the concern is dismissed. "Copilot complains about `os.Stdout.Write()`, but not about the much more numerous instances of `fmt.Println`."

### M3: Thinks about forward compatibility
Command names, parameter structures, and API shapes are evaluated for what's coming next. `keppel test` -> `keppel test-driver storage` because FederationDriver testing might come later.

### M4: Values brevity when stdlib provides clarity
Consistently removes wrapper code that duplicates information already in error messages from `strconv`, constructors, and other well-designed stdlib functions.

### M5: Approves simple/low-risk PRs quickly
Many PRs got clean approvals with no inline comments. The lead reviewer doesn't manufacture concerns. Low-risk changes get "Let's give it a shot."

### M6: Corrects technical misconceptions directly
When a reviewer is wrong about Go semantics, the lead reviewer states the correct behavior clearly and without softening. "Incorrect. `d.Limits` is not overwritten..."

### M7: Pushes fixes when needed
The lead reviewer sometimes pushes commits directly to address concerns rather than waiting for another round of review: "I have pushed several commits, some of which to address the concerns I voiced in earlier reviews."

---

## PRs with No Lead Reviewer Comments (Silent Approvals)

These PRs had no inline comments from the lead reviewer (some had silent approvals):

| Title | Action |
|-------|--------|
| fix new gosec, staticcheck lints | No comments |
| Test that special account and repo names are forbidden | No comments |
| Add X-RateLimit-* header | No comments |
| Renovate: Update dependency go to 1.25 | No comments |
| Do not fail if there is no crt file | APPROVED, no inline |
| remove automaxprocs | No comments |
| fix regression introduced in earlier PR | No comments |
| update codeowners to new workgroup team | No comments |
| Link spec to magic 256 const | APPROVED, no inline |
| advance repos.next_manifest_sync_at after error | No comments |
| Improve mirror UX | APPROVED, no inline |
| improve memory usage spikiness of Trivy scan job | No comments |
| Revert "fix nolintlint" | APPROVED, no inline |
| fix nolintlint | No comments |
| Check if pathParts is nil or 0 | APPROVED, no inline |
| Replace misspell with typos | APPROVED, no inline |

**Pattern**: The lead reviewer approves straightforward, low-risk changes without discussion. Detailed review is reserved for PRs that introduce new architecture, CLI commands, or API surfaces.

---

## go-bits Review Patterns (Cross-Repository)

From go-bits code reviews:

### API Surface Protection

> "I don't like having a global variable for this that callers can mess with."

Solution: `func ForeachOptionTypeInLIQUID[T any](action func(any) T) []T` instead of mutable var. Also:

> "Needs a docstring..."

Public methods always need docstrings.

### Dependency Graph Minimization

> "This would mean that a lot of applications will pull in go-bits/audittools that previously didn't, which then pulls the amqp library dependencies into those app's vendor directories. To avoid this, please move the `GenerateUUID()` function into `package internal` and call it from both relevant places."

Also provided concrete code suggestion:
> `logg.Error("%s is: %s", uuid, err.Error())`

### Correct Technical Reasoning

A reviewer suggested: "Changing DeepEqual to == should be fine I guess."

The lead reviewer corrected:
> "We cannot change DeepEqual to use `==`. Most types are not within the `comparable` interface, and thus `==` does not work on them."

### Spec-Faithful Programming

A reviewer suggested adding "defense in depth" nil checks with error reporting.

The lead reviewer refused:
> "I don't want to error out on this. Whether these 'defense in depth' branches are taken or not depends on how you read this specific part in the spec... I could swear that, in earlier Go versions, this only matched the plain `nil` value... I'm assuming this to be undefined behavior and thus took care to make those branches behave the same."

### Status Code Range Check

> "I added a check to allow only the 400..599 range."

`respondwith.CustomStatus` panics on non-error status codes -- only 400-599 allowed.

### Public API Documentation

> "1. Since this is a public method, please add a docstring. Suggestion:
> > IsAdminProject returns whether the token is scoped to the project that is designated for cloud administrators within Keystone (if any).
> 2. This should return `bool` instead of `string`. Add a private bool member on type Token if necessary."

Later: "Upon further inspection, my previous request to add a private bool member on type Token turned out to be a bad idea, so I reverted that part and also added a warning for the future why doing so would be a bad idea."

### Test Exhaustiveness

> "Consequently, this should recurse through each request and response payload type in LIQUID, not just through ServiceInfo."

---

## Lead Reviewer Priority Summary

| Dimension | Position |
|-----------|----------|
| **Complexity** | Aggressively removes. "Irrelevant contrivance." |
| **AI suggestions** | Skeptical. Judges on merit. Often simplifies. |
| **Error handling** | Trust stdlib context. Use `must.Return()`. Less wrapping. |
| **Testing** | Tests MUST cover behavior. Never reduce coverage. |
| **API surface** | Plan for extensibility in public APIs. Immutable variables. |
| **Go type system** | Deep expertise. Cites spec. Understands value semantics. |
| **Forward thinking** | Plan extensibility in names/APIs, but don't solve future problems prematurely. |
| **Documentation** | Qualified, precise. TODOs with context. Public methods need docstrings. |
| **Dependencies** | Minimize. Move utilities to `internal` to avoid transitive dep pollution. |
