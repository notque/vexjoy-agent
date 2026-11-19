# Writing Modern Go (Go 1.27)

Load this file before you write or edit any Go code. Each rule below fixes a failure measured in generated code: code that built and passed its tests but used outdated or weak idioms. Rules marked with a version need that version or later in `go.mod`; check the `go` line first.

```bash
grep '^go ' go.mod   # "go 1.27" unlocks every rule here; lower versions: see go-version-idioms.md
```

## 1. Doc comments on every exported name

Every exported type, function, method, constant block, and variable block gets a comment that starts with its name. Exactly one non-test file per package starts with a package comment directly above the `package` line; `package main` gets one too. Measured: 10 of 12 unguided outputs skipped doc comments; 6 of 14 guided outputs still skipped the package comment.

```go
// BAD
package userrepo

type Repo struct{ db *sql.DB }

func New(db *sql.DB) *Repo { return &Repo{db: db} }

// GOOD
// Package userrepo stores users in SQLite through database/sql.
package userrepo

// Repo stores users in SQLite. It is safe for concurrent use.
type Repo struct{ db *sql.DB }

// New returns a Repo that uses db. The caller owns db and closes it.
func New(db *sql.DB) *Repo { return &Repo{db: db} }
```

State concurrency safety, ownership, and zero-value behavior when they matter.

## 2. Errors

| Do | Not | Since |
|----|-----|-------|
| `errors.Is(err, io.EOF)`, `errors.Is(err, flag.ErrHelp)`, `errors.Is(err, sql.ErrNoRows)` | `err == io.EOF`, `err == flag.ErrHelp` | 1.13 |
| `if e, ok := errors.AsType[*http.MaxBytesError](err); ok {` | `var e *http.MaxBytesError; if errors.As(err, &e) {` | 1.26 |
| Sentinels prefixed with the package: `errors.New("userrepo: not found")` | `errors.New("not found")` | - |
| Name the package once per message: `fmt.Errorf("create user %q: %w", email, ErrDuplicateEmail)` | `fmt.Errorf("userrepo: create: %w", ErrDuplicateEmail)` (prints `userrepo: create: userrepo: duplicate email`) | - |
| Named constants from the driver: `sqlite3.SQLITE_CONSTRAINT_UNIQUE` | Magic numbers: `e.Code() == 2067` | - |
| Match a driver's typed error or code | `strings.Contains(err.Error(), "UNIQUE constraint failed")` | - |

Tests use `errors.AsType` too:

```go
se, ok := errors.AsType[*filter.SyntaxError](err)
if !ok {
	t.Fatalf("error %T is not *SyntaxError", err)
}
```

Typed driver errors: find the type in the module cache, then match it. Example for `modernc.org/sqlite` (verified in v1.59.0 source: `*sqlite.Error` has `Code() int`; codes live in `modernc.org/sqlite/lib`):

```go
import (
	"modernc.org/sqlite"
	sqlite3 "modernc.org/sqlite/lib"
)

func isUniqueViolation(err error) bool {
	e, ok := errors.AsType[*sqlite.Error](err)
	return ok && e.Code() == sqlite3.SQLITE_CONSTRAINT_UNIQUE
}
```

For other drivers, read the source first: `grep -rn 'func (e \*Error)' $(go env GOMODCACHE)/<driver>@<version>/`.

Wrap with context that names the operation and the input: `fmt.Errorf("create user %q: %w", email, err)`. Return an error unchanged when the callee already says enough.

## 3. Context

- Tests: `ctx := t.Context()`. Never `context.Background()` or `context.TODO()` in a test (1.24). Measured: 8 of 12 unguided outputs used `context.Background()` in tests.
- Library code: accept `ctx` as the first parameter. Never create `context.Background()` inside a library function.
- Cleanup that must outlive a canceled ctx (HTTP shutdown, rollback): `context.WithoutCancel(ctx)` keeps values and drops cancellation (1.21).
- First-error cancellation: `context.WithCancelCause` + `context.Cause(ctx)` (1.20) carries the real error; no extra mutex or error box needed.
- `main`: `signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)` is the one place `context.Background()` belongs.

`os.Exit` skips deferred calls. Never `defer` in a function that calls `os.Exit`; move the work into a function that returns an exit code. Measured: every unguided CLI `main` did this.

```go
// BAD: stop never runs
func main() {
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	os.Exit(wordfreq.Run(ctx, os.Args[1:], os.Stdin, os.Stdout, os.Stderr))
}

// GOOD
func main() {
	os.Exit(run())
}

func run() int {
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	return wordfreq.Run(ctx, os.Args[1:], os.Stdin, os.Stdout, os.Stderr)
}
```

## 4. Goroutines and bounded concurrency

`wg.Go(f)` replaces `wg.Add(1); go func() { defer wg.Done(); ... }()` (1.25). Use it in library code and in tests. `for range n` replaces `for i := 0; i < n; i++` when `i` is unused (1.22). Loop variables are per-iteration since 1.22: delete `i := i` and `tt := tt` copies and closure parameters that only pass the loop variable.

Canonical bounded worker pool. Results go straight into a preallocated slice by index; no results channel, no dispatcher goroutine, at most `workers` goroutines:

```go
// Map calls fn for every item with at most workers calls in flight and
// returns the results in input order.
func Map[T, R any](ctx context.Context, items []T, workers int, fn func(context.Context, T) (R, error)) ([]R, error) {
	if workers < 1 {
		return nil, errors.New("pool: workers must be >= 1")
	}
	ctx, cancel := context.WithCancelCause(ctx)
	defer cancel(nil)

	out := make([]R, len(items))
	var next atomic.Int64
	var wg sync.WaitGroup
	for range min(workers, len(items)) {
		wg.Go(func() {
			for ctx.Err() == nil {
				i := int(next.Add(1) - 1)
				if i >= len(items) {
					return
				}
				r, err := fn(ctx, items[i])
				if err != nil {
					cancel(fmt.Errorf("item %d: %w", i, err)) // first call wins
					return
				}
				out[i] = r // each index written by one goroutine: no race
			}
		})
	}
	wg.Wait()
	if err := context.Cause(ctx); err != nil { // fn error, or parent's context.Canceled
		return nil, err
	}
	return out, nil
}
```

Every goroutine you start has an owner that waits for it (`wg.Wait`) or a ctx that stops it. With the standard library only, this beats `errgroup`; use `golang.org/x/sync/errgroup` with `SetLimit` when the module already depends on it.

## 5. HTTP servers

Routing (1.22 patterns). Let the mux answer 405: when a path matches a pattern with a different method, `http.ServeMux` replies 405 with the required `Allow` header (plain-text body). A hand-written 405 handler that omits `Allow` breaks RFC 9110. Measured: 3 of 4 unguided outputs wrote 405 handlers without `Allow`.

```go
mux := http.NewServeMux()
mux.HandleFunc("POST /items", s.createItem)
mux.HandleFunc("GET /items/{id}", s.getItem) // r.PathValue("id"); GET also matches HEAD
mux.HandleFunc("GET /healthz", health)
```

When the API contract says every error body is JSON, add a method-less fallback per path. The method pattern is more specific, so it still wins for its method:

```go
mux.HandleFunc("/items/{id}", methodNotAllowed(logger, "GET, HEAD"))

func methodNotAllowed(logger *slog.Logger, allow string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Allow", allow)
		writeError(w, logger, http.StatusMethodNotAllowed, "method not allowed")
	}
}
```

A type that wraps `http.ResponseWriter` (logging, status capture) must also define `Unwrap() http.ResponseWriter`, so `http.NewResponseController` can still reach `Flush` and deadlines (1.20).

IDs: the standard `uuid` package (1.27) generates RFC 9562 UUIDs. Never hand-roll UUID formatting from `crypto/rand` bytes. Measured: 4 of 4 outputs hand-rolled it.

```go
import "uuid"

id := uuid.NewV7().String() // time-ordered; uuid.New() picks a general-purpose version
```

Request bodies: cap size, reject unknown fields, map the size error with `errors.AsType`:

```go
r.Body = http.MaxBytesReader(w, r.Body, 1<<20)
dec := json.NewDecoder(r.Body)
dec.DisallowUnknownFields()
if err := dec.Decode(&in); err != nil {
	if _, ok := errors.AsType[*http.MaxBytesError](err); ok {
		writeError(w, http.StatusRequestEntityTooLarge, "request body too large")
		return
	}
	writeError(w, http.StatusBadRequest, "invalid JSON")
	return
}
```

Response writes: log the encode error; the status line is already sent, so you cannot change the response.

```go
func writeJSON(w http.ResponseWriter, logger *slog.Logger, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(v); err != nil {
		logger.Warn("write response", "err", err)
	}
}
```

Canonical graceful serve. `Shutdown` waits for in-flight requests; if it times out, `Close` force-closes the remaining connections so no handler outlives `Serve`. Measured: 4 of 4 outputs skipped the `Close` fallback.

```go
// Serve serves h on ln until ctx is done, then shuts down gracefully.
func Serve(ctx context.Context, ln net.Listener, h http.Handler, shutdownTimeout time.Duration) error {
	srv := &http.Server{
		Handler:           h,
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       30 * time.Second,
		WriteTimeout:      30 * time.Second,
		IdleTimeout:       120 * time.Second,
	}
	errc := make(chan error, 1)
	go func() { errc <- srv.Serve(ln) }()

	select {
	case err := <-errc:
		return fmt.Errorf("serve: %w", err) // never ErrServerClosed here: Shutdown not yet called
	case <-ctx.Done():
	}

	sctx, cancel := context.WithTimeout(context.WithoutCancel(ctx), shutdownTimeout)
	defer cancel()
	if err := srv.Shutdown(sctx); err != nil {
		return errors.Join(fmt.Errorf("shutdown: %w", err), srv.Close())
	}
	if err := <-errc; !errors.Is(err, http.ErrServerClosed) {
		return err
	}
	return nil
}
```

Bind development servers to `127.0.0.1`, never `0.0.0.0` or `:port`.

HTTP tests: `httptest.NewServer(h)` for real sockets. Inside `synctest.Test`, use `httptest.NewTestServer(t, h)` (1.27): an in-memory network so fake time works, cleaned up by `t`.

## 6. JSON

- `encoding/json` (v1 API) is still the default choice; in 1.27 it runs on the v2 engine. Keep using it unless the project already uses v2.
- `encoding/json/v2` is standard from 1.27 (`json.Marshal`, `json.UnmarshalRead(r, &v, json.RejectUnknownMembers(true))`). Do not mix v1 and v2 in one package.
- Use `omitzero` for struct, `time.Time`, and `time.Duration` fields (1.24); `omitempty` does not omit them.

## 7. CLIs

Shape: `func Run(ctx context.Context, args []string, stdin io.Reader, stdout, stderr io.Writer) int`, and `main` is three lines. Never use `flag.CommandLine`, `os.Exit`, or `os.Std*` inside `Run`.

```go
fs := flag.NewFlagSet("wordfreq", flag.ContinueOnError)
fs.SetOutput(stderr)
n := fs.Int("n", 10, "print the top `N` words")
if err := fs.Parse(args); err != nil {
	if errors.Is(err, flag.ErrHelp) {
		return 0
	}
	return 2 // flag already printed the error and usage
}

level := slog.LevelInfo
if *verbose {
	level = slog.LevelDebug
}
logger := slog.New(slog.NewTextHandler(stderr, &slog.HandlerOptions{Level: level}))
// A logger that drops everything: slog.New(slog.DiscardHandler)  (1.24)
// Never: slog.New(slog.NewTextHandler(io.Discard, nil))
```

Sorting with a tie-break: `slices.SortFunc` + `cmp.Or` (1.22). `go fix` does not rewrite `sort.Slice` calls with custom less functions, so do it yourself.

```go
// BAD
sort.Slice(rs, func(i, j int) bool {
	if rs[i].Count != rs[j].Count {
		return rs[i].Count > rs[j].Count
	}
	return rs[i].Word < rs[j].Word
})

// GOOD
slices.SortFunc(rs, func(a, b entry) int {
	return cmp.Or(cmp.Compare(b.Count, a.Count), strings.Compare(a.Word, b.Word))
})
```

Collect sorted map keys with `slices.Sorted(maps.Keys(m))` (1.23).

## 8. Iterators and generics

- Return `iter.Seq[V]` / `iter.Seq2[K, V]` (1.23). Check every `yield` result: `if !yield(k, v) { return }`.
- Write the traversal once. `Keys` and `Values` delegate to `All`:

```go
// Keys returns an iterator over the keys in insertion order.
func (m *Map[K, V]) Keys() iter.Seq[K] {
	return func(yield func(K) bool) {
		for k := range m.All() {
			if !yield(k) {
				return
			}
		}
	}
}
```

- Streaming rows as `iter.Seq2[T, error]`: `defer rows.Close()` inside the iterator function so an early `break` releases the connection; yield `rows.Err()` at the end.
- Consume with `slices.Collect`, `maps.Collect`, `slices.Backward` (1.23).
- Generic methods (1.27): a method may declare its own type parameters, `func (b Box[T]) Map[U any](f func(T) U) Box[U]`. Interface methods cannot, and a generic method cannot satisfy an interface method. Use them for type-specific helpers that previously had to be package-level functions.

## 9. Standard-library helpers to reach for

| Need | Use | Since |
|------|-----|-------|
| UUID | `uuid.New()`, `uuid.NewV7()`, `uuid.Parse` | 1.27 |
| Split at last separator | `strings.CutLast(s, ".")` / `bytes.CutLast`, not `LastIndex` + slicing | 1.27 |
| Split at first separator | `strings.Cut`, `strings.CutPrefix` | 1.18/1.20 |
| Loop over split parts | `for p := range strings.SplitSeq(s, ",")` | 1.24 |
| Copy a URL or query | `u.Clone()`, `vals.Clone()` | 1.27 |
| Min, max, fallback | `min`, `max`, `cmp.Or(a, b, "default")` | 1.21/1.22 |
| Search, sort, dedupe | `slices.Contains`, `slices.Index`, `slices.SortFunc`, `slices.Compact` | 1.21 |
| Pointer to a value | `new(expr)`, e.g. `new(30)` is a `*int` | 1.26 |
| File access confined to a dir | `root, err := os.OpenRoot(dir)` | 1.24 |
| Leaked-goroutine profile | `pprof.Lookup("goroutineleak")`, `/debug/pprof/goroutineleak` | 1.27 |

## 10. Tests

- `ctx := t.Context()`; `dir := t.TempDir()`; `t.Cleanup(...)`; `for range n`; `wg.Go` (see rules above).
- Anything with goroutines, timers, timeouts, or `time.After`: wrap in `synctest.Test` (1.25) instead of `time.Sleep`. Time is fake and only advances when every goroutine in the bubble is blocked, so an hour-long timeout runs instantly and deterministically. If a bubble goroutine never exits, `synctest.Test` reports a deadlock, so leaks fail the test. `synctest.Sleep(d)` (1.27) sleeps and then waits for the bubble to settle. Measured: 0 of 12 unguided outputs used synctest; 6 used `time.Sleep`.

Import path: `"testing/synctest"`. There is no top-level `synctest` package; `import "synctest"` fails with `package synctest is not in std`. Measured: 1 of 10 guided outputs broke its build this way. Top-level std packages new in 1.27 are only `uuid` and `simd` (experimental).

```go
// BAD: slow and flaky
go func() { time.Sleep(10 * time.Millisecond); cancel() }()

// GOOD
import (
	"context"
	"errors"
	"testing"
	"testing/synctest"
	"time"
)

func TestMapCancel(t *testing.T) {
	synctest.Test(t, func(t *testing.T) {
		ctx, cancel := context.WithCancel(t.Context())
		go func() {
			time.Sleep(10 * time.Millisecond) // fake clock inside the bubble
			cancel()
		}()
		_, err := pool.Map(ctx, items, 3, slowFn)
		if !errors.Is(err, context.Canceled) {
			t.Fatalf("err = %v, want context.Canceled", err)
		}
	})
}
```

Limits inside a bubble: no real network (use `httptest.NewTestServer`), no goroutines started outside the bubble, and I/O on real files or sockets does not count as durably blocked.

- Table-driven tests with `t.Run(tt.name, ...)`; compare with `==`, `slices.Equal`, `maps.Equal`, or `reflect.DeepEqual`; report `got` then `want`.
- Benchmarks: `for b.Loop() { ... }` (1.24), not `for i := 0; i < b.N; i++`.
- In `package x_test`, give helpers distinctive names (`newTestRepo`, not `run`); other test files in the package can collide.

## 11. database/sql

- Every call takes ctx: `QueryContext`, `QueryRowContext`, `ExecContext`, `BeginTx`.
- `errors.Is(err, sql.ErrNoRows)` maps to your `ErrNotFound`.
- After a `rows.Next()` loop: `return out, rows.Err()`; `defer rows.Close()` right after the error check.
- Transactions: `tx, err := db.BeginTx(ctx, nil)`; `defer tx.Rollback()` (a no-op after Commit); return `tx.Commit()`'s error.
- UPDATE or DELETE on a missing row: check `res.RowsAffected()` and return `ErrNotFound` when it is 0.
- Enforce uniqueness with a UNIQUE constraint and map the driver's constraint error (section 2). Never check-then-insert.

## 12. Pre-handoff checklist

Run each command when you have tools. Without tools, read your code against each line before you answer.

```bash
gofmt -l .                                            # must print nothing
go vet ./...                                          # 1.27: go test also runs the stdversion check
go fix -diff ./...                                    # modernizers; must print nothing
go run honnef.co/go/tools/cmd/staticcheck@latest ./...
go test -race -count=1 ./...
```

- [ ] Every package, including `package main`, has one `// Package x ...` comment; every exported name has a doc comment that starts with the name.
- [ ] No `interface{}`, `wg.Add(1)`, `sort.Slice`, `errors.As(`, `err ==` against a sentinel, `i := i`, or 3-clause `for` with an unused index.
- [ ] No function both defers and calls `os.Exit`.
- [ ] Each error message names the package at most once; driver codes use named constants.
- [ ] No `context.Background()` or `context.TODO()` in tests or library code.
- [ ] No `time.Sleep` in tests; timing and goroutine tests use `synctest.Test`, imported as `"testing/synctest"`.
- [ ] Every import path is real: `"uuid"`, `"iter"`, `"testing/synctest"`, `"encoding/json/v2"`, `"log/slog"`.
- [ ] No hand-rolled UUIDs, no string matching on error text, and every 405 carries an `Allow` header.
- [ ] Every goroutine has an owner that waits for it; every `rows`, `resp.Body`, and file is closed.
- [ ] Servers bind `127.0.0.1` by default and shut down with `Shutdown`, then `Close` on timeout.
