# Extended Patterns from SAP CC Personal Repos

Patterns extracted by the `github-profile-rules` pipeline (2026-03-11) from 20 public repos including portunus, alltag, gg, prometheus-minimum-viable-sd, and rust-jmdict, plus helm-charts and limes PR reviews. **These extend the keppel-derived patterns -- they do not replace them.**

Context difference: keppel uses go-makefile-maker which auto-generates CI, REUSE config, and licensing tooling. Personal repos configure these manually, which surfaces explicit preferences not visible in keppel.

---

## 1. Security Micro-Patterns

From portunus and alltag -- security-conscious patterns that appear consistently across personal work.

### Timing Side-Channel Avoidance

When a user lookup fails (e.g., username not found), perform the expensive operation anyway (bogus bind, dummy hash check) before returning. This prevents attackers from inferring whether a username exists from response timing.

```go
// BAD: returns immediately on user-not-found -> timing leak
if user == nil {
    return ErrInvalidCredentials
}
ldapConn.Bind(user.DN, password)

// GOOD: perform bind even for non-existent users (alltag/internal/auth/ldap.go)
// Comment: "attempt to bind anyway... This avoids a timing side-channel, where
// an attacker could infer whether a user exists based on response time"
if user != nil {
    ldapConn.Bind(user.DN, password)
} else {
    ldapConn.Bind("nonexistent", password) // bogus bind to equalize timing
}
```

### crypto/rand Only -- Never math/rand

Use `crypto/rand.Reader` for all security-sensitive randomness. Panic on failure -- a failure to generate randomness is a fundamental programming error, not a recoverable runtime error.

```go
// From portunus/internal/core/random.go
func GenerateRandomKey(length uint) []byte {
    buf := make([]byte, length)
    _, err := io.ReadFull(rand.Reader, buf) // crypto/rand
    if err != nil {
        panic(err.Error()) // "AS IT FUCKING SHOULD"
    }
    return buf
}
```

### Input Validation Against Injection

Validate input character sets for fields used in query construction (LDAP filters, SQL identifiers). Reject ASCII symbols in usernames to prevent LDAP injection. This is explicit input rejection, not sanitization.

```go
// from alltag: reject ASCII symbols in usernames to prevent LDAP injection
// character set allowlist is narrow by design
```

---

## 2. Visual Section Separators

Lines of forward slashes are used as horizontal rules to divide major logical sections within a file. This appears consistently across Go, JavaScript, and Rust files.

```go
////////////////////////////////////////////////////////////////////////////////

// This is a new logical section -- e.g., "announce" vs "collect" functions,
// or "helpers for templates" vs "general page layout"

func nextSection() {
```

Use these when a file has 2+ logically distinct groups of functions that would be clearer separated visually. Do NOT use for every function boundary -- reserve for major sections.

---

## 3. Copyright Header Format

Two formats depending on project era:

**Older projects** -- boxed comment block:
```
/******************************************************************************
* Copyright 2019 SAP SE                                                       *
* SPDX-License-Identifier: GPL-3.0-only                                      *
* Refer to the file LICENSE for details.                                      *
******************************************************************************/
```

**Newer projects** -- SPDX short form (preferred now):
```go
// SPDX-FileCopyrightText: 2025 SAP SE
// SPDX-License-Identifier: Apache-2.0
```

For keppel: go-makefile-maker handles REUSE/SPDX configuration automatically via `REUSE.toml`. Do not configure manually.

---

## 4. Kubernetes Namespace Isolation

From helm-charts PR reviews -- each service must run in its own Kubernetes namespace.

**Rule**: Never add a new service to a shared namespace (monsoon3, monsoon3global) unless it requires **direct volume access** to another service's data. API communication is not a sufficient reason to co-locate.

> "I want to hear a compelling reason why prodel absolutely has to live in the same namespace as Keystone... The only compelling reason I can think of is direct volume access." -- helm-charts review

> "we really need to kick this habit of stuffing everything into the same namespace... we will have hard requirements to pull everything out" -- helm-charts review

---

## 5. Code Hygiene in PRs

These rules appear repeatedly in PR reviews -- apply to every PR, not just the specific file being changed.

### Clean Up Orphaned Declarations

When a change removes a reference (e.g., a template variable, an import, an env var reference), remove its **declaration** too. Apply this to ALL files the PR touches, not just the one where the reference was removed.

> "Since the reference to $registry is removed, its declaration should be cleaned up. This also applies to other files where similar changes are made." -- helm-charts review

### Sort Configuration Lists

Keep allowlists, configuration lists, and similar ordered collections sorted alphabetically. Reason: cleaner diffs and easier to spot duplicates.

> "Please sort." -- helm-charts review

### Document New Config Fields in the Same PR

When adding new configuration fields or API parameters, document them in the project's `docs/` directory in the same PR. Do not add features without updating their documentation.

> "Please document newly added config fields in docs/liquids/" -- limes review

---

## 6. Changelog Format (Personal Repos)

Personal repos maintain `CHANGELOG.md` at repo root with this specific format:

```markdown
# v1.5.0 (2025-11-26)

Changes:
- Add package is.
- Extend package option to add Unwrap().

# v1.4.0 (2025-08-07)

Bugfixes:
- Fix X in case of Y.
```

Headings use `# vX.Y.Z (YYYY-MM-DD)`. Sections use `Changes:` or `Bugfixes:`, not `### Added` / `### Fixed`. One-line bullet points only.

Note: keppel changelog conventions may differ -- check keppel's existing CHANGELOG.md if applicable.

---

## 7. Test Flags (Personal Repos / Non-go-makefile-maker Projects)

Personal CI runs Go tests with two additional flags:

```yaml
# from gg/.github/workflows/checks.yaml
go test -shuffle=on -coverprofile=build/cover.out -covermode=count ./...
```

- **`-shuffle=on`**: Randomizes test execution order to detect order-dependent tests. Any test that passes in default order but fails shuffled has an implicit dependency on prior tests.
- **`-coverprofile`**: Generates coverage reports for upload to external services.

For keppel: go-makefile-maker controls test flags via `Makefile.maker.yaml`. Use `coverageTest.*` configuration instead of adding flags manually.

---

## Source

Generated by `github-profile-rules` pipeline from 20 repos + 99 PR reviews (2026-03-11).
Confidence-scored: rules in sections 1-4 are high-confidence (seen in 3+ repos or 4+ review comments).
Sections 5-7 are medium-confidence (2 repos or 2-3 review comments).

This file is a complement to `review-standards-lead.md` and the code patterns reference, not a replacement.
