# Language-Specific Checks Catalog

Complete check catalogs for Go, Python, and TypeScript. Load after detecting the language from file extensions.

## Go (when reviewing .go files)

**Modern stdlib (Go 1.21+, Go 1.22+)**:
- `slices.SortFunc` instead of `sort.Slice`
- `slices.Contains` instead of manual loop search
- `strings.CutPrefix`/`strings.CutSuffix` instead of `HasPrefix`+`TrimPrefix`
- `min`/`max` builtins instead of custom helpers (Go 1.21+)
- `for range N` loop syntax (Go 1.22+)
- Loop variable capture fix (Go 1.22+): flag `v := v` or `item := item` inside `for range` loops — these are unnecessary since Go 1.22 and are an LLM tell
- Loop variable capture fix (Go 1.22+): flag `go func(x Type) { ... }(x)` capture patterns — since Go 1.22, loop variables are per-iteration so the closure argument is unnecessary
- `maps.Clone`, `maps.Keys` instead of manual map operations
- `log/slog` instead of `log.Printf` for structured logging

**Go idioms**:
- Error wrapping with `%w` and checking with `errors.Is`/`errors.As`
- Receiver type consistency (all pointer or all value, not mixed)
- Package naming conventions (lowercase, single-word, no underscores)
- Unexported types with exported constructors (`NewFoo()`)
- Blank identifier only with explicit justification

**Concurrency**:
- Goroutine leaks: goroutines without shutdown path
- Context cancellation: functions accepting `context.Context` must respect cancellation
- Mutex per resource, not per struct (fine-grained locking)
- `sync.Once` for initialization, not `init()` with flags
- Channel direction in function signatures

**Resources**:
- `defer Close()` must come AFTER the error check on the open call
- Connection pool sharing (reuse shared clients across requests)
- `http.DefaultClient` reuse vs creating new clients
- File descriptor limits awareness

**Anti-patterns**:
- Premature interface abstraction (interface with one implementation)
- Over-engineered error types (custom error types for simple errors)
- Unnecessary channels when a mutex suffices
- `init()` for non-trivial work (side effects, I/O, network calls)
- Returning concrete types but accepting interfaces at boundaries
- `MockXxx` types in production (non-test) files — test doubles belong in `_test.go` files
- Creating separate `*sql.DB` connection pools when a shared pool should be injected

**LLM tells**:
- Functional options pattern on types with 2-3 fields (a simple struct literal suffices)
- Table-driven tests everywhere, even for single-case scenarios
- Excessive interface segregation (one-method interfaces for everything)
- Config validation layers with reflection when a simple `if` works
- Overly verbose error messages repeating the function name
- Builder pattern for structs with few fields
- Loop variable shadowing (`v := v`) in Go 1.22+ projects — LLMs trained on older Go generate this
- `defer rows.Close()` without checking `rows.Err()` after the iteration loop — LLMs miss the error check
- Verbose `if err != nil { return fmt.Errorf("failed to X: %w", err) }` wrapping errors that already have good context (e.g., `strconv.ParseUint` already says what it was parsing)

## Python (when reviewing .py files)

**Modern Python (3.10+, 3.11+, 3.12+)**:
- Walrus operator `:=` for assignment expressions in conditions
- `match` statement for structural pattern matching (3.10+)
- `type` statement for type aliases (3.12+)
- `tomllib` for TOML parsing (3.11+)
- `TaskGroup` for structured concurrency (3.11+)
- `ExceptionGroup` and `except*` syntax (3.11+)
- Generic syntax `def foo[T](x: T)` (3.12+)

**Python idioms**:
- List/dict/set comprehensions over `map`/`filter` with lambdas
- Context managers (`with`) for resource management
- Generators and `yield` for large dataset processing
- `pathlib.Path` over `os.path` for path manipulation
- `collections.defaultdict` over manual key-existence checks
- F-strings over `format()` or `%` formatting
- `dataclasses` or `attrs` over manual `__init__` boilerplate

**Concurrency**:
- `asyncio` patterns: proper `async with`, `async for`
- `TaskGroup` structured concurrency over `gather` with manual cancellation
- Proper cleanup in async context managers
- Thread safety when mixing sync and async code

**Resources**:
- Context managers (`with`) for file handles, connections, locks
- `atexit` handlers for global cleanup
- Signal handling for graceful shutdown
- `contextlib.suppress` over empty except blocks

**Anti-patterns**:
- Mutable default arguments (`def foo(items=[])`)
- Bare `except:` or `except Exception:` without re-raise
- `import *` polluting namespace
- Global mutable state
- Monkey patching in production code
- String concatenation in loops (use `join`)

**LLM tells**:
- Overly verbose type hints on obvious types (`x: int = 5` when `x = 5` is clear)
- Unnecessary docstrings on self-documenting simple functions
- Java-style getter/setter methods instead of properties or direct access
- Abstract base classes for single implementations
- Excessive use of `typing.Optional` when `| None` syntax exists (3.10+)
- Over-engineered class hierarchies for simple data transformations

## TypeScript (when reviewing .ts/.tsx files)

**Modern TypeScript (5.0+, 5.2+)**:
- `satisfies` operator for type checking without widening
- `const` type parameters for literal type inference
- `using` declarations for resource management (5.2+)
- Template literal types for string pattern types
- `NoInfer<T>` utility type (5.4+)

**TypeScript idioms**:
- Discriminated unions over type casting for type narrowing
- `Zod` or similar for runtime validation matching TypeScript types
- Proper generic constraints (`extends`) over `any`
- Mapped types and conditional types for type-level programming
- `as const` for literal type inference

**React (when reviewing .tsx)**:
- React 19 patterns: no `forwardRef` (ref is a regular prop), `useActionState`, `useOptimistic`
- Proper hook dependency arrays (exhaustive deps)
- `memo` only with measured performance justification
- Server Components vs Client Components distinction
- Use framework data loading instead of `useEffect` for data fetching

**Anti-patterns**:
- `any` overuse instead of proper types or `unknown`
- Type assertions (`as`) over type narrowing with guards
- Barrel file bloat causing circular dependencies
- Circular dependencies between modules
- Enum overuse when union types suffice
- `namespace` in modern code

**LLM tells**:
- Overly abstract factory patterns for simple object creation
- Unnecessary class-based components in modern React
- Redundant null checks when TypeScript strict mode already narrows
- Over-engineered dependency injection frameworks
- Excessive abstraction layers (repository pattern wrapping simple fetch calls)
- Generic utility types that reimplement built-in ones
