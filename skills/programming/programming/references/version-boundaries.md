# Language version boundaries

Use this reference only when compatibility or concurrency semantics affect the
change. Confirm versions from manifests and lockfiles before applying a row.

## Go

| Version | Boundary that changes code |
|---|---|
| 1.22+ | `for` iteration variables are per-iteration; old `x := x` closure workarounds can be removed only when the module targets 1.22+. |
| 1.24+ | `testing.T.Context`, `testing.B.Loop`, and iterator helpers such as `strings.SplitSeq` become available. |
| 1.25+ | `sync.WaitGroup.Go` can own Add/Done bookkeeping; do not use it for older module targets. |
| 1.26+ | Generic `errors.AsType[T]` is available; retain `errors.As` for older targets. |

Language availability does not override repository conventions or the `go`
directive. After changing the directive, run tests under the minimum supported
toolchain, not only the developer machine.

## Kotlin coroutines

- Broad `catch (Exception)` also intercepts `CancellationException`; rethrow it
  unless cancellation is intentionally translated at a documented boundary.
- `CoroutineExceptionHandler` handles uncaught exceptions of root `launch`
  coroutines. It does not make `async` failures disappear; those surface from
  `await`.
- `supervisorScope` prevents one child failure from cancelling siblings, but the
  caller must still observe each child’s result. Use it only when partial success
  is part of the contract.
- CPU loops must check cancellation (`ensureActive`/`isActive`). Blocking I/O
  does not become cancellable merely because it runs in a coroutine.

## PHP

Do not recommend syntax beyond the project constraint. Useful migration markers:
PHP 8.0 adds attributes, named arguments, `match`, and union types; 8.1 adds
enums, readonly properties, fibers, and intersection types; 8.2 adds readonly
classes and DNF types; 8.3 adds typed class constants and `#[Override]`; 8.4 adds
property hooks and asymmetric property visibility. Static-analysis/tooling config
may intentionally target a lower PHP version than the runtime—check both.

## Swift concurrency

- An actor is reentrant across `await`: actor state can change before the method
  resumes. Revalidate assumptions or store/deduplicate in-flight work.
- Cancellation is cooperative. Code that creates a long-lived unstructured
  `Task` owns storage and a cancellation path; loops call
  `Task.checkCancellation()` or inspect `Task.isCancelled`.
- Swift 6 language mode turns many concurrency diagnostics into errors. Check
  the package/Xcode language mode before introducing `Sendable`, isolation, or
  `@preconcurrency` changes; do not silence warnings wholesale.
- `AsyncStream` bridges must retain the producer/delegate for the stream lifetime,
  call `finish`, and release external work in `onTermination`.

Treat these as compatibility tripwires, not complete language guides.
