# SAPCC audit dispatch contract

Partition by package, not concern. Assign 5–15 Go files per generalist and require direct reading of every assigned file. Use gopls context/references/diagnostics when available. Findings must be code-level and include severity, `file:line`, current snippet, replacement, and rationale.

Each package review covers these SAPCC-specific deviations:

- reject single-implementation interfaces, no-op wrappers, functional options, config files/Viper, and speculative validation layers;
- constructors are normally infallible `NewX(deps...) *X` with positional dependencies; environment comes from `osext.MustGetenv`;
- errors start lowercase and use `cannot <operation>`; preserve wrapping only when callers use `errors.Is/As`;
- auth occurs at the top of handlers, not middleware; decode with `DisallowUnknownFields`; obfuscate internal HTTP errors;
- SQL is a package-level `sqlext.SimplifyWhitespace` variable with PostgreSQL placeholders; transactions defer `sqlext.RollbackUnlessCommitted`; migrations are immutable;
- optional DB/domain values use `option.Option[T]`, not pointers;
- tests favor sequential scenarios, go-bits `must`/assert helpers, and value assertions for auth/tenant boundaries;
- Prometheus names carry the application prefix; counters are initialized; background work follows the repository's jobloop pattern.

Also flag dead exports, duplicated structures/handlers, contract violations, inconsistent approaches, and extraction that lost guards. Verify callers before declaring an export dead.
