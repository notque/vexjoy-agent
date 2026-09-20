# SAPCC Go contracts

Load only when `go.mod` imports `github.com/sapcc/go-bits`. These are mined local
review and API contracts, not general Go rules. Existing code and the installed
go-bits version remain authoritative.

## HTTP and errors

- Call `httpapi.IdentifyEndpoint(r, normalizedPath)` at the start of handlers so
  middleware metrics receive the stable route, not a concrete URL.
- Authenticate and authorize before loading protected data. The ordering scanner
  is heuristic; inspect aliases and helper calls manually.
- Decode request/config JSON through a decoder with
  `DisallowUnknownFields()`; otherwise misspelled fields silently become zero
  values.
- Preserve the API surface’s error shape: Registry V2 uses
  `RegistryV2Error.WriteAsRegistryV2ResponseTo`; Keppel V1 uses
  `respondwith.ObfuscatedErrorText` so 5xx details stay server-side behind the
  returned UUID. Registry V2 responses, including errors, retain
  `Docker-Distribution-Api-Version: registry/2.0`.
- `must.Return` and `must.Succeed` terminate the process. Use them for bootstrap
  failures and their `*T` variants for test setup, never for request/runtime
  failures. In tests, `must` establishes prerequisites; `assert` checks the
  behavior under test.
- Do not automatically wrap already descriptive `strconv` or constructor
  errors. When context is needed, local wording favors `cannot ...`, `while ...`,
  or `during METHOD URL ...`, lowercase with identifying values quoted. Never
  both log and return the same primary error; log only secondary cleanup failures.

## Current library boundaries

- SAPCC uses `go-bits/logg`, `httpapi`, `respondwith`, `sqlext`, and the local
  assertion/test helpers instead of introducing parallel frameworks.
- As of go-bits commit `8b79638` (June 2026),
  `assert.HTTPRequest{}.Check` and its payload helper types are removed. Migrate
  to `go-bits/httptest`: `NewHandler(...).RespondTo(...)` followed by
  `ExpectStatus`, `ExpectBody`, `ExpectHeader`, `CaptureJSON`, or
  `CaptureHeader`. Direct `httptest.NewRecorder` bypasses this contract.
- As of commit `90af602`, `go-bits/assert` forwards to
  `go.xyrillian.de/gg/assert`; existing imports still compile. Do not confuse
  this compatibility forwarding with the hard removal above.
- `go-bits/assert.DeepEqual` uses `(t, description, actual, expected)`, unlike
  testify’s common parameter order. SAPCC DB tests use `easypg.WithTestDB` in
  `TestMain`; fixture comparisons use `easypg.AssertDBContent`.

## Persistence and testability

- Existing database migrations are immutable; append paired `up`/`down`
  migrations. PostgreSQL placeholders are `$1`, `$2`; timestamp columns use
  `TIMESTAMPTZ` when representing instants.
- Inject clock functions or use the project mock clock in testable code. Stored
  tasks and tickers need an owned cancellation/shutdown path.
- Empty JSON collections must serialize as `[]`, not `null`, where the API
  contract promises arrays.
- Preserve behavioral assertions during refactors. TODOs include the concrete
  work, a starting-point link or issue, and why it is deferred.
- `sapcc/go-bits` belongs in the external import group, not the repository-local
  group. Go files require the repository’s SPDX header, and `//nolint` names the
  linter plus a reason.

Run the repository’s own generated-code and `make check` gates. Do not add a new
framework because it is generally popular; verify the existing go-bits facility
first.
