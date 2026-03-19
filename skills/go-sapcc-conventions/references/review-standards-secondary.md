# Secondary Reviewer — Detailed Review Rules

Extended rules with ALL PR comments, authored PR patterns, and full examples. Extracted from sapcc/keppel and sapcc/go-bits code reviews.

---

## Review Statistics

- **Total review comments**: ~18 (29% of all comments)
- **Top theme**: Error handling (4 comments) -- migration safety and validation
- **Second theme**: Testing (4 comments) -- redundancy and completeness
- **Third theme**: Code style (3 comments) -- formatting and consistency
- **Review style**: Inquisitive -- asks questions where the lead reviewer makes statements
- **Sentiment**: Questions (5) + suggestions (5) dominate
- **Approval rate**: High. Most lead reviewer PRs get clean approval
- **Total PRs reviewed**: 25 (14 reviewed others' code, 11 authored)

---

## All Review Comments (Verbatim)

### Comment 1: Sub-second rounding is irrelevant
- **File**: `internal/api/utils.go`
- **Category**: PRECISION / DOMAIN-KNOWLEDGE

Copilot suggested rounding up sub-second values.

> "rate limit is not on a sub second basis."

Dismisses theoretical concern with domain knowledge.

### Comment 2: Test already covers this
- **File**: `internal/api/registry/ratelimit_test.go`
- **Category**: TESTING / REDUNDANCY

Copilot suggested adding X-RateLimit-Action header to 429 response expectations.

> "This is already done in the test requests a few lines above."

### Comments 3-4: See above
- **File**: `internal/api/registry/ratelimit_test.go`

> "see above"

Two more instances dismissed with reference to earlier answer. Concise, doesn't repeat himself.

### Comment 5: Defer to primary maintainer
- **Category**: PROCESS / PRAGMATISM

> "LGTM but lets wait for the lead reviewer, we are in no hurry here"

Approves but defers to the lead reviewer for final merge. Respects ownership hierarchy.

### Comment 6: Honest self-assessment
- **File**: `internal/tasks/manifests_test.go`
- **Category**: TESTING / SELF-AWARENESS

The lead reviewer asked why more images were going into Unsupported status. The secondary reviewer responded:

> "I changed the default when no vuln_status is put into the function which caused the Clean to Unsupported change here. I probably need to fix the test and use an explicit default."

Acknowledges own mistake quickly, proposes fix direction.

### Comment 7: Formatting suggestion
- **File**: `cmd/test/main.go`
- **Category**: CODE-STYLE / FORMATTING

```suggestion
Example: "keppel test swift read-manifest repo sha256:abc123 --account-name my-account",
```

Uses GitHub suggestion block for easy one-click apply.

### Comment 8: Accept simpler approach
- **File**: `cmd/test/main.go`
- **Category**: PRAGMATISM

After the contributor explained indentation was intentional for cobra help output:

> "I think that's fine here"

Accepts explanations, doesn't nitpick when there's a valid reason.

### Comment 9: Request explanatory comment
- **File**: `internal/client/upload.go`
- **Category**: DOCUMENTATION

The lead reviewer added a `Content-Length` header without comment. The secondary reviewer:

> "That should probably be a comment"

Wants to know WHY something was added, not just WHAT.

### Comment 10: Check for redundant code
- **File**: `internal/processor/manifests.go`
- **Category**: SIMPLICITY / REDUNDANCY

> "This check is now redundant?"

The lead reviewer clarified: "No, it's moved down to the last line of the green diff."

### Comment 11: Migration safety (env var removal)
- **File**: `internal/drivers/openstack/keystone.go`
- **Category**: EDGE-CASES / SAFETY

Reviewing removal of `osext.MustGetenv("KEPPEL_OSLO_POLICY_PATH")`:

> "Do we somehow check if this is still set and then abort?"

Concern: prevent silent misconfiguration during migration.

### Comment 12: Migration safety (same pattern)
- **File**: `internal/drivers/trivial/auth.go`

> "same here?"

Same concern about `KEPPEL_USERNAME` and `KEPPEL_PASSWORD` env vars.

### Comment 13: Strict JSON parsing
- **File**: `internal/keppel/config.go`

> "How about setting disallowUnknownFields?"

Suggests `json.Decoder.DisallowUnknownFields()` to catch typos in configuration. The lead reviewer implemented it: "done".

### Comment 14: Question variable scope
- **File**: `conformance-test/env.sh`

> "Why not export?"

Questions why variable was changed from `export` to local. The lead reviewer explained it shouldn't look like Keppel reads it.

### Comment 15: Defense in depth nil checks (go-bits)
- **File**: `assert/assert.go`

Suggested adding explicit nil checks with error reporting as "defense in depth". The lead reviewer refused: "I don't want to error out on this... assuming this to be undefined behavior."

### Comment 16: Simplify DeepEqual (go-bits)
- **File**: `assert/assert.go`

> "Changing DeepEqual to == should be fine I guess."

The lead reviewer corrected: "We cannot change DeepEqual to use `==`. Most types are not within the `comparable` interface."

### Comment 17: Partial review
- **Review body**

> "Only could look at the first commit"

Communicates review limitations honestly.

### Comment 18: Performance-oriented suggestion (go-bits)
- **File**: `liquidapi/liquidapi.go`

> "We probably want to use https://pkg.go.dev/github.com/google/go-cmp/cmp#Equal to not generate the human readable diff"

Suggests `cmp.Equal` over `cmp.Diff` for performance when diff output isn't needed.

---

## Rules (Synthesized from Comments)

### Rule 1: ERROR MESSAGES MUST BE ACTIONABLE

The secondary reviewer authored a PR specifically to improve error messages:

**Before** (useless):
```
received unexpected HTTP status: 500 Internal Server Error
```

**After** (actionable):
```
denied: auth token request to "https://ghcr.io/token?..." did return: "requested access to the resource is denied"
```

Self-comment:
> "I would be open to add something here to hint that the URL might be wrong but the error is already a mouthful."

A 500 "Internal Server Error" is unacceptable when the actual cause is knowable. But balance information with readability.

### Rule 2: KNOW THE SPEC, DEVIATE PRAGMATICALLY

References RFC draft:
> "see https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-ratelimit-headers-02"

But chose `X-RateLimit-*` over standard `RateLimit-*` because newer RFC "changed the headers to lists which is harder to parse and implement in client applications."

Another PR added a spec reference comment to a magic number constant (256), linking to the exact OCI distribution spec section.

### Rule 3: GUARD AGAINST PANICS WITH CLEAR ERRORS

```go
// BEFORE (panics on empty input)
accountName := pathParts[0]

// AFTER (returns descriptive error)
if len(pathParts) < 1 {
    return fmt.Errorf("invalid image reference: %q", imageURL.Path)
}
accountName := pathParts[0]
```

Also added comprehensive regex tests with table-driven approach in the same PR.

### Rule 4: STRICT CONFIGURATION PARSING

Comment 1 (on removed `osext.MustGetenv`):
> "Do we somehow check if this is still set and then abort?"

Comment 2 (same pattern):
> "same here?"

Comment 3 (on JSON config):
> "How about setting disallowUnknownFields?"

The lead reviewer accepted all three. This shows the secondary reviewer catches migration and config safety issues consistently.

### Rule 5: TEST ALL COMBINATIONS, NOT JUST HAPPY PATHS

Exhaustive merge tests:
- Clean + Low, Clean + Medium, Low + Medium
- Multiple Unsupported + actual severity
- Error overriding everything
- Pending with various combinations

Edge case name testing:
- Account names starting with `-`, reserved names like `_blobs`, `_chunks`
- Table-driven: `for _, account := range []string{"_blobs", "_chunks", "-invalid"}`
- Comment: "Just to be sure that this does not regress with any refactors in the future"

Real-world failure modes:
- `TestReplicationFailingFromHarbor` (non-standard error codes)
- `TestReplicationFailingFromGHCR` (specific auth flow)
- Mock HTTP handlers simulating exact upstream behavior

### Rule 6: ELIMINATE REDUNDANT CODE AND CHECKS

> "This check is now redundant?"

Dismissing Copilot:
> "This is already done in the test requests a few lines above."
> "see above" (twice)

Keep reviews DRY too.

### Rule 7: COMMENTS EXPLAIN WHY, NOT WHAT

> "That should probably be a comment"

Another PR was just 2 lines linking a magic constant to its spec source.

### Rule 8: DOMAIN KNOWLEDGE OVER THEORETICAL CORRECTNESS

Copilot suggests sub-second rounding:
> "rate limit is not on a sub second basis."

Know your system's actual constraints.

### Rule 9: SMALLEST POSSIBLE FIX

One PR changed 2 lines, 2 files. Body: "update-ca-certificates will just ignore the copied README.md"

PRs should be focused. Don't bundle unrelated changes.

### Rule 10: RESPECT OWNERSHIP HIERARCHY

> "LGTM but lets wait for the lead reviewer, we are in no hurry here"

Approve but defer merge to primary maintainer. Don't rush external contributor PRs.

### Rule 11: BE HONEST ABOUT YOUR OWN MISTAKES

> "I changed the default when no vuln_status is put into the function which caused the Clean to Unsupported change here. I probably need to fix the test and use an explicit default."

Acknowledge errors quickly. Propose fix direction. Don't defend broken code.

### Rule 12: FORMATTING SUGGESTIONS USE GITHUB SUGGESTION BLOCKS

Use ````suggestion` syntax for easy one-click apply. Keep suggestions minimal and focused.

### Rule 13: PREFER SIMPLE OVER OVERENGINEERED

After the lead reviewer proposed a simpler alternative to Copilot's approach:
> "I think that's fine here"

Accept simpler solutions when they work.

### Rule 14: SHELL SCRIPTS: PREFER CONSISTENCY

> "Why not export?"

Question deviations from patterns. Accept explanations when valid.

---

## Secondary Reviewer's Authored PR Patterns

### Defensive Testing
- Tests for edge cases: account names starting with `-`, reserved names `_blobs`, `_chunks`
- Regex validation: `[a-z0-9][a-z0-9-]{0,47}` rejects invalid inputs
- Comment: "Just to be sure that this does not regress with any refactors in the future"

### Spec Awareness + Pragmatic Deviation
- References RFC draft explicitly in PR body
- Deviates when spec is impractical (list headers harder to parse)
- Updated ALL test assertions to include new headers
- Added `timeElapsedDuringRequests` tracking for correct calculations

### Minimal Pragmatic Fix
- 2 lines changed, 2 files
- One-sentence PR body: "update-ca-certificates will just ignore the copied README.md"

### Domain Logic Simplification
- Changed merge priority: Unsupported no longer overrides actual severity
- Key insight: "When uploading a manifest with attestations or sboms, we do not want to downgrade the vulnerability status to unsupported just because of those extra things"
- Added exhaustive test combinations for all severity pairings

### Real-World Error Handling
- `TestReplicationFailingFromHarbor` simulates actual Harbor failure modes
- `TestReplicationFailingFromGHCR` simulates ghcr.io auth flow failures
- Mock HTTP handlers reproduce exact upstream behavior

### User-Facing Error Quality
- Shows exact before/after error messages from `podman pull`
- Before: `received unexpected HTTP status: 500 Internal Server Error` (useless)
- After: `denied: auth token request to "https://ghcr.io/token?..." did return: "requested access to the resource is denied"` (actionable)
- Changed 500 errors to proper Registry V2 errors so clients display actual message
- Self-comment: "Not ideal but at least something to work with"

### Documentation-as-Code
- 2 lines linking magic constant 256 to OCI distribution spec section

### Defensive Nil Checks
- Added `if len(pathParts) < 1` check before array index access
- Returns clear error: `fmt.Errorf("invalid image reference: %q", imageURL.Path)`
- Added comprehensive regex tests with table-driven approach

### Extensible Validation
- Extended CEL validation environment with `layers` and `media_type` variables
- Added real-world test case: in-toto provenance manifests with SLSA attestation predicates
- TODO comment: `// TODO: remove DynType and properly declare this`

### Tooling Upgrades
- Replaced misspell with typos (better alternative)
- Small, focused change

---

## Secondary Reviewer's Interaction with Copilot

A notable pattern emerges:

1. Copilot suggests sub-second rounding. The secondary reviewer dismisses with domain knowledge: "rate limit is not on a sub second basis."

2. Copilot suggests adding headers already tested. The secondary reviewer dismisses: "This is already done in the test requests a few lines above." Also: "see above" (twice more).

3. Copilot suggests complex JSON marshaling for test CLI. The lead reviewer counter-suggests a simpler approach. The secondary reviewer says: "I think that's fine here" (accepting the simpler explanation).

**Pattern**: The secondary reviewer evaluates Copilot against domain knowledge and existing coverage. Accepts simpler alternatives from teammates. Concise in dismissals -- references earlier answers rather than repeating.

---

## Secondary Reviewer vs Lead Reviewer: Key Differences

| Dimension | Lead Reviewer | Secondary Reviewer |
|-----------|---------------|-------------------|
| **Review style** | Directive statements | Inquisitive questions |
| **Complexity** | Aggressively removes | Adds defensive checks |
| **AI suggestions** | Skeptical, often simplifies | More accepting |
| **Error handling** | Trust stdlib, less wrapping | Validate inputs, more wrapping |
| **Testing** | Tests MUST cover behavior | Tests should not be redundant |
| **Defense in depth** | Handle ambiguity silently | Make problems visible |
| **Spec compliance** | Pragmatic when needed | References spec, deviates explicitly |
| **Focus areas** | Architecture, simplicity, API design | Migration safety, config, UX |
| **Dismissal style** | Principled ("irrelevant contrivance") | Domain-based ("not on sub-second basis") |

---

## Secondary Reviewer's Key Contribution Themes

1. **Error message quality** -- Messages must be actionable, not just technically correct
2. **Migration safety** -- Removed env vars must still be validated
3. **Configuration strictness** -- `DisallowUnknownFields()` catches typos
4. **Real-world testing** -- Test against actual production failure modes (Harbor, ghcr.io)
5. **Spec awareness** -- Reference RFCs, link magic numbers to specs
6. **Defensive programming** -- Guard against panics with clear errors
7. **Small focused PRs** -- 2-line fixes are fine
8. **Exhaustive combinations** -- When changing logic, test every meaningful input pair
