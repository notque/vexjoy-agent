# SAPCC ten-specialist review

Dispatch ten parallel specialists; each scans every Go package for one domain:

1. API design and over-engineering.
2. Error handling and operator-facing messages.
3. HTTP handlers, inline auth, JSON decoding, and response helpers.
4. Constructors, dependency injection, and interfaces.
5. Database access and migrations.
6. Tests and security-sensitive assertion depth.
7. Package organization, imports, comments, and contract cohesion.
8. modern Go, concurrency, startup, and shutdown.
9. observability, HTTP clients, and background jobs.
10. SAPCC divergences and LLM-default patterns.

Every worker receives the repository's SAPCC pattern source and returns severity, `file:line`, current snippet, replacement, rationale, and whether the rule is non-negotiable (4+ repositories), strong (2–3), or contextual (1).

High-value local conventions:

- concrete types until at least two real implementations; consumer owns the interface;
- positional constructors, pure environment configuration, inline handler auth, sequential scenario tests;
- `option.Option[T]` for optional values; `respondwith.ObfuscatedErrorText` for internal handler failures;
- package SQL via `sqlext.SimplifyWhitespace`, PostgreSQL `$1` placeholders, and `RollbackUnlessCommitted`;
- no removed `assert.HTTPRequest`; use `httptest.Handler.RespondTo()`;
- domain artifacts live beside their owning interface rather than generic `types.go`/`util.go`;
- an extracted helper must inherit all guards previously supplied by its caller;
- repeated “A must always be followed by B” is an abstraction-boundary defect: merge B into A.
