# Extended Go Error Handling Patterns

Overflow reference for the go-patterns skill (error handling section). Contains advanced patterns that do not fit in the main SKILL.md.

---

## Gopls for Error Pattern Analysis

When `gopls` is available, use it to trace error handling patterns across the codebase:

```bash
# Find all usages of a sentinel error (verify consistent handling)
$ gopls references pkg/errors/errors.go:15:5  # position of ErrNotFound

# Find all implementations of a custom error interface
$ gopls implementation internal/errors/types.go:20:6  # position of your error interface

# Trace where errors are returned from a function
$ gopls references pkg/service/handler.go:42:10  # function that returns error
```

**Note:** gopls requires files to be part of a Go module. It cannot analyze standard library files like `builtin.go` directly.

---

## HTTP Handler Error Patterns

### Standard Pattern with respondwith

```go
func handleRequest(w http.ResponseWriter, r *http.Request) {
    data, err := fetchData(r.Context())
    if respondwith.ErrorText(w, err) {
        return
    }

    result, err := processData(data)
    if respondwith.ErrorText(w, err) {
        return
    }

    respondwith.JSON(w, http.StatusOK, result)
}
```

### Middleware Error Wrapping

```go
func errorMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        defer func() {
            if rec := recover(); rec != nil {
                log.Printf("panic recovered: %v", rec)
                http.Error(w, "internal server error", http.StatusInternalServerError)
            }
        }()
        next.ServeHTTP(w, r)
    })
}
```

---

## Custom Error Type with Unwrap

When a custom error type wraps an inner error, implement `Unwrap()` to preserve the chain:

```go
type ServiceError struct {
    Op   string
    Kind ErrorKind
    Err  error
}

func (e *ServiceError) Error() string {
    if e.Err != nil {
        return fmt.Sprintf("%s: %s: %v", e.Op, e.Kind, e.Err)
    }
    return fmt.Sprintf("%s: %s", e.Op, e.Kind)
}

func (e *ServiceError) Unwrap() error {
    return e.Err
}

// Usage:
func GetUser(id string) (*User, error) {
    user, err := db.Find(id)
    if err != nil {
        return nil, &ServiceError{
            Op:   "GetUser",
            Kind: Internal,
            Err:  err,
        }
    }
    return user, nil
}

// Caller can still use errors.Is/As on the inner error:
var svcErr *ServiceError
if errors.As(err, &svcErr) {
    fmt.Println(svcErr.Op, svcErr.Kind)
}
```

---

## Error Wrapping in Deferred Cleanup

Handle errors from deferred operations without shadowing the primary error:

```go
func WriteData(path string, data []byte) (retErr error) {
    f, err := os.Create(path)
    if err != nil {
        return fmt.Errorf("create file %s: %w", path, err)
    }
    defer func() {
        if cerr := f.Close(); cerr != nil && retErr == nil {
            retErr = fmt.Errorf("close file %s: %w", path, cerr)
        }
    }()

    if _, err := f.Write(data); err != nil {
        return fmt.Errorf("write to %s: %w", path, err)
    }
    return nil
}
```

---

## Multi-Error Aggregation (Go 1.20+)

Use `errors.Join` to combine multiple errors:

```go
func ValidateConfig(cfg *Config) error {
    var errs []error

    if cfg.Host == "" {
        errs = append(errs, fmt.Errorf("host is required"))
    }
    if cfg.Port < 1 || cfg.Port > 65535 {
        errs = append(errs, fmt.Errorf("port must be 1-65535, got %d", cfg.Port))
    }
    if cfg.Timeout <= 0 {
        errs = append(errs, fmt.Errorf("timeout must be positive"))
    }

    return errors.Join(errs...)
}

// Caller can still use errors.Is on individual errors in the joined set
```

---

## Quick Reference Card

```go
// Wrap with context
return fmt.Errorf("operation X for %s: %w", id, err)

// Sentinel error
var ErrNotFound = errors.New("not found")

// Check sentinel
if errors.Is(err, ErrNotFound) { ... }

// Custom error type
type MyError struct { Field string }
func (e *MyError) Error() string { return e.Field }

// Extract custom type
var myErr *MyError
if errors.As(err, &myErr) { ... }

// Explicit ignore
_ = mayFail()

// Multi-error (Go 1.20+)
return errors.Join(err1, err2)
```
